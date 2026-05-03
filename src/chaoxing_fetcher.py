"""学习通通知抓取 — 通过ADB+uiautomator从模拟器提取收件箱"""
import subprocess, tempfile, os, re, time, xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from src.logger import get_logger

logger = get_logger("chaoxing_fetcher")

ADB_PATH = r"C:\Program Files\Netease\MuMu\nx_device\12.0\shell\adb.exe"
DEVICE = "127.0.0.1:7555"

# 只收录的消息类型关键词
INCLUDE_TYPES = ["作业", "考试", "测验", "课程通知", "课程到期", "截止"]


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
        """从UI XML解析收件箱消息 — 基于Y坐标提取有效消息内容"""
        items = []
        seen = set()

        SKIP_TOP = {"消息", "通知", "课程通知", "通讯录", "收件箱", "首页", "笔记", "我"}
        SKIP_SENDERS = {
            "学习通校园", "学习通活动通知", "超星教师论坛",
            "学习通通知", "回复我的", "验证信息", "小助手", "其他", "教务通知",
            "已加载全部", "全部",
        }

        try:
            root = ET.fromstring(ui_xml)
            rows = {}  # Y坐标 -> [text]
            for elem in root.iter():
                text = (elem.get("text") or "").strip()
                bounds = elem.get("bounds", "")
                if text and len(text) >= 2 and bounds:
                    try:
                        y = int(bounds.split("][")[0].split(",")[1])
                    except:
                        continue
                    if y < 250:  # 顶部UI元素跳过
                        continue
                    if y not in rows:
                        rows[y] = []
                    rows[y].append(text)

            # 按Y坐标处理：每行可能包含 [sender, date] 或 [title] 或 [sender]
            sorted_rows = sorted(rows.items())
            for y, texts in sorted_rows:
                for text in texts:
                    if text in SKIP_TOP or text in SKIP_SENDERS:
                        continue
                    if re.match(r"^\d{1,3}$", text):
                        continue
                    if re.match(r"^\d{2,4}[-/]\d{2}", text):
                        continue
                    if len(text) < 4:
                        continue
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
        """只收录包含作业/考试/课程通知关键字的有效消息"""
        for kw in INCLUDE_TYPES:
            if kw in title:
                return True
        return False

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
