"""QQ邮箱 IMAP 抓取模块"""
import imaplib
import email
import re
import time
import hashlib
from email.header import decode_header
from datetime import datetime, timedelta
from src.logger import get_logger

logger = get_logger("qqmail_fetcher")

DATE_PATTERNS = [
    re.compile(r"截止(?:日期|时间)[：:\s]*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?)"),
    re.compile(r"([\d]{4}[-/年][\d]{1,2}[-/月][\d]{1,2}日?)\s*(?:截止|到期|前|之前)"),
    re.compile(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})"),
    re.compile(r"时间[：:\s]*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?)"),
]


def decode_email_header(header_value):
    """解码邮件头中的中文（=?UTF-8?B?...?= 格式）"""
    if header_value is None:
        return ""
    parts = decode_header(header_value)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            try:
                result.append(part.decode(charset or "utf-8", errors="replace"))
            except (LookupError, UnicodeDecodeError):
                result.append(part.decode("utf-8", errors="replace"))
        else:
            result.append(str(part))
    return "".join(result)


def extract_date_from_text(text: str) -> str:
    """从文本中提取日期，返回 ISO 格式字符串或空"""
    for pattern in DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            date_str = match.group(1)
            date_str = date_str.replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-")
            try:
                parsed = datetime.strptime(date_str, "%Y-%m-%d")
                return parsed.strftime("%Y-%m-%d")
            except ValueError:
                continue
    return ""


class QQMailFetcher:
    """QQ邮箱IMAP抓取器"""

    def __init__(self, config):
        self.config = config
        self.imap = None

    def _connect(self):
        """连接并登录IMAP服务器（含重试）"""
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                self.imap = imaplib.IMAP4_SSL(self.config.imap_server, self.config.imap_port)
                self.imap.login(self.config.email, self.config.auth_code)
                logger.info("IMAP 登录成功")
                return
            except imaplib.IMAP4.error as e:
                logger.error(f"IMAP 认证失败 (第{attempt}次): {e}")
                if attempt == max_retries:
                    raise
                time.sleep(2 ** attempt)
            except OSError as e:
                logger.error(f"IMAP 连接失败 (第{attempt}次): {e}")
                if attempt == max_retries:
                    raise
                time.sleep(2 ** attempt)

    def _disconnect(self):
        """断开IMAP连接"""
        if self.imap:
            try:
                self.imap.close()
            except Exception:
                pass
            try:
                self.imap.logout()
            except Exception:
                pass
            self.imap = None

    def fetch(self) -> list:
        """获取匹配关键词的邮件列表"""
        items = []
        try:
            self._connect()
            self.imap.select("INBOX", readonly=True)

            # 仅按日期搜索（纯 ASCII，避免中文编码问题）
            since_date = (datetime.now() - timedelta(days=self.config.lookback_days)).strftime("%d-%b-%Y")
            search_criteria = f'(SINCE "{since_date}")'
            logger.info(f"IMAP 搜索: {search_criteria}")

            status, data = self.imap.uid("SEARCH", None, search_criteria)
            if status != "OK":
                logger.error(f"IMAP 搜索失败: {status}")
                return items

            uid_list = data[0].split()
            logger.info(f"找到 {len(uid_list)} 封近期邮件")

            if not uid_list:
                return items

            # 批量获取邮件头部 + 正文前800字符
            batch_size = 20
            allowed_lower = [s.lower() for s in getattr(self.config, 'allowed_senders', [])]
            exclude_lower = [s.lower() for s in self.config.exclude_senders]

            for i in range(0, len(uid_list), batch_size):
                batch = uid_list[i : i + batch_size]
                uid_range = b",".join(batch)
                try:
                    status, msg_data = self.imap.uid(
                        "FETCH", uid_range, "(BODY.PEEK[HEADER] BODY.PEEK[TEXT]<0.800>)"
                    )
                    if status != "OK":
                        continue

                    for part in msg_data:
                        if isinstance(part, tuple):
                            response_bytes = part[0]
                            data_bytes = part[1]
                            uid_match = re.search(rb"UID (\d+)", response_bytes)
                            if not uid_match:
                                continue
                            uid = uid_match.group(1).decode()
                            item = self._parse_email_response(
                                uid, data_bytes, allowed_lower, exclude_lower
                            )
                            if item:
                                items.append(item)
                except Exception as e:
                    logger.error(f"批量获取邮件失败: {e}")
                    continue

                time.sleep(0.3)

        except Exception as e:
            logger.error(f"QQ邮箱抓取异常: {e}")
            raise
        finally:
            self._disconnect()

        logger.info(f"QQ邮箱解析完成: {len(items)} 条匹配通知")
        return items

    def _parse_email_response(self, uid: str, data_bytes, allowed_lower, exclude_lower) -> dict | None:
        """解析单封邮件——白名单发件人匹配"""
        try:
            msg = email.message_from_bytes(data_bytes)
        except Exception as e:
            logger.debug(f"解析邮件数据失败: {e}")
            return None

        subject = decode_email_header(msg.get("Subject", ""))
        if not subject:
            return None

        sender = decode_email_header(msg.get("From", ""))
        sender_lower = sender.lower()

        # 排除发件人
        for ex in exclude_lower:
            if ex in sender_lower:
                return None

        # 白名单匹配
        if allowed_lower:
            if not any(a in sender_lower for a in allowed_lower):
                return None

        # Message-ID
        message_id = msg.get("Message-ID", "")
        if not message_id:
            raw_id = f"{msg.get('Date', '')}{subject}"
            message_id = hashlib.sha256(raw_id.encode()).hexdigest()[:32]

        # 邮件日期
        date_str = msg.get("Date", "")
        try:
            parsed_date = email.utils.parsedate_to_datetime(date_str)
            event_date = parsed_date.strftime("%Y-%m-%d")
        except Exception:
            event_date = datetime.now().strftime("%Y-%m-%d")

        # 正文摘要
        text_content = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            text_content = payload.decode(charset, errors="replace")
                            break
                    except Exception:
                        continue
        else:
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or "utf-8"
                    text_content = payload.decode(charset, errors="replace")
            except Exception:
                pass

        summary = text_content.strip()[:200] if text_content else ""
        summary = re.sub(r"<[^>]+>", "", summary)

        # 尝试提取截止日期
        extracted_date = extract_date_from_text(subject + " " + text_content[:500])
        if extracted_date:
            event_date = extracted_date

        return {
            "source": "qqmail",
            "source_id": message_id.strip("<>"),
            "title": subject,
            "summary": summary,
            "url": "",
            "event_date": event_date,
            "sender": sender,
        }
