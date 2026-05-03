"""学习通通知抓取 — 通过ADB+uiautomator从模拟器提取收件箱"""
import subprocess, tempfile, os, re, time, xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from src.logger import get_logger

logger = get_logger("chaoxing_fetcher")

ADB_PATH = r"C:\Program Files\Netease\MuMu\nx_device\12.0\shell\adb.exe"
DEVICE = "127.0.0.1:7555"

# 排除的消息（广告/无关内容关键词）
EXCLUDE_MSG = ["拿0元", "现金应用", "直播预约", "广告"]


class ChaoxingFetcher:
    """通过ADB从MuMu模拟器提取学习通收件箱"""

    def __init__(self, config):
        self.config = config
        self.adb = ADB_PATH
        self.device = DEVICE

    def _adb(self, *args, timeout=15):
        """执行ADB命令"""
        cmd = [self.adb, "-s", self.device] + list(args)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout, result.stderr

    def _check_adb(self) -> bool:
        """检查ADB连接"""
        stdout, _ = self._adb("shell", "echo", "ok")
        return "ok" in stdout

    def _dump_ui(self) -> str | None:
        """导出当前界面UI树并返回XML内容"""
        try:
            self._adb("shell", "uiautomator", "dump", "/sdcard/ui.xml")
            self._adb("pull", "/sdcard/ui.xml", os.path.join(tempfile.gettempdir(), "cx_ui.xml"))
            path = os.path.join(tempfile.gettempdir(), "cx_ui.xml")
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"UI导出失败: {e}")
            return None

    def fetch(self) -> list:
        """主入口：从收件箱获取通知（多屏滚动抓取）"""
        items = []
        if not self.config.username or not self.config.password:
            logger.info("学习通未配置，跳过")
            return items

        try:
            # 检查ADB连接
            if not self._check_adb():
                logger.warning("ADB未连接，尝试连接...")
                self._adb("connect", self.device)
                time.sleep(2)
                if not self._check_adb():
                    logger.error("ADB连接失败，跳过学习通")
                    return items

            # 多屏滚动抓取（每次向上滑动半屏，抓5次覆盖更多消息）
            for scroll in range(5):
                if scroll > 0:
                    # 向上滑动（从中间滑到顶部）
                    self._adb("shell", "input", "swipe", "540", "1200", "540", "400", "300")
                    time.sleep(1.5)

                ui_xml = self._dump_ui()
                if ui_xml:
                    batch = self._parse_messages(ui_xml)
                    items.extend(batch)
                    logger.debug(f"  第{scroll+1}屏: {len(batch)} 条")

            # 去重
            seen = set()
            unique = []
            for item in items:
                if item["source_id"] not in seen:
                    seen.add(item["source_id"])
                    unique.append(item)
            items = unique

            logger.info(f"从收件箱提取 {len(items)} 条有效通知（多屏滚动）")

        except Exception as e:
            logger.error(f"学习通抓取异常: {e}")

        return items

    def _parse_messages(self, ui_xml: str) -> list:
        """从UI XML解析收件箱消息 — 提取有效消息内容"""
        items = []
        seen = set()

        # 已知的UI元素/发件人/标签（非消息内容）
        SKIP_TEXTS = {
            "消息", "通知", "通讯录", "收件箱", "首页", "笔记", "我",
            "课程通知", "学习通校园", "学习通活动通知", "超星教师论坛",
            "学习通通知", "回复我的", "验证信息", "小助手", "其他", "教务通知",
            "已加载全部", "全部",
        }

        try:
            root = ET.fromstring(ui_xml)
            all_texts = []
            for elem in root.iter():
                text = (elem.get("text") or "").strip()
                if text and len(text) >= 3:
                    all_texts.append(text)

            for text in all_texts:
                # 跳过UI标签、发件人、日期、数字
                if text in SKIP_TEXTS:
                    continue
                if re.match(r"^\d{1,2}$", text):  # 纯数字(徽章)
                    continue
                if re.match(r"^\d{2,4}[-/]\d{2}", text):  # 日期格式
                    continue
                if re.match(r"^\d+$", text):  # 纯数字
                    continue

                # 至少10个字符才算有效消息内容
                if len(text) < 10:
                    continue

                # 过滤广告
                if not self._should_include("", text):
                    continue

                msg_id = f"inbox_{abs(hash(text)) & 0xFFFFFFFF:08x}"
                if msg_id not in seen:
                    seen.add(msg_id)
                    items.append({
                        "source": "chaoxing",
                        "source_id": msg_id,
                        "title": text[:80],
                        "summary": "",
                        "url": "",
                        "event_date": datetime.now().strftime("%Y-%m-%d"),
                        "type": self._classify(text),
                        "sender": "",
                    })

        except Exception as e:
            logger.error(f"解析UI失败: {e}")

        return items

    def _is_message_item(self, sender: str, title: str, date_str: str) -> bool:
        """判断三个连续的text是否是收件箱消息项"""
        if not sender or not title:
            return False
        # 发件人：通常2-8个中文字符
        if len(sender) < 2 or len(sender) > 20:
            return False
        # 标题：通常有意义的中文
        if len(title) < 3:
            return False
        # 日期格式检查
        if date_str and not re.match(r"\d{2}-\d{2}", date_str):
            return False
        # 排除UI元素标题
        if sender in ("首页", "消息", "笔记", "我", "收件箱", "通讯录"):
            return False
        return True

    def _should_include(self, sender: str, title: str) -> bool:
        """判断消息是否值得收录"""
        for ex in EXCLUDE_MSG:
            if ex in sender or ex in title:
                return False
        return True

    def _classify(self, title: str) -> str:
        """分类消息类型"""
        if "作业" in title:
            return "homework"
        elif "考试" in title or "测验" in title:
            return "exam"
        elif "通知" in title:
            return "notice"
        elif "截止" in title or "到期" in title:
            return "deadline"
        return "other"

    def _parse_date(self, date_str: str) -> str:
        """解析日期，返回ISO格式"""
        date_str = date_str.strip() if date_str else ""
        if not date_str:
            return datetime.now().strftime("%Y-%m-%d")

        # 格式: "04-20" 或 "04-20 20:35"
        match = re.match(r"(\d{2})-(\d{2})", date_str)
        if match:
            month, day = int(match.group(1)), int(match.group(2))
            year = datetime.now().year
            # 如果月份比当前月份大，说明是去年的
            if month > datetime.now().month:
                year -= 1
            try:
                return datetime(year, month, day).strftime("%Y-%m-%d")
            except ValueError:
                pass

        return datetime.now().strftime("%Y-%m-%d")
