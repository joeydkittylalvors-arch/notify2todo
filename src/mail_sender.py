"""邮件发送模块 —— 通过QQ邮箱SMTP发送ICS附件"""
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from src.logger import get_logger

logger = get_logger("mail_sender")


class MailSender:
    """通过SMTP发送邮件（带ICS附件）"""

    def __init__(self, config, ics_config):
        self.config = config
        self.ics_config = ics_config

    def send_ics(self, ics_file_path: str, new_count: int) -> bool:
        """发送带ICS附件的通知邮件"""
        if not os.path.exists(ics_file_path):
            logger.error(f"ICS 文件不存在: {ics_file_path}")
            return False

        subject = f"[通知待办] {datetime.now().strftime('%Y-%m-%d')} - {new_count} 条新通知"

        body = f"""<html>
<body>
<h2>通知待办摘要</h2>
<p>本次共发现 <strong>{new_count}</strong> 条新通知。</p>
<p>ICS 日历文件已作为附件，请在手机上打开此附件导入日历。</p>
<hr>
<p style="color:#888;font-size:12px;">
此邮件由 notify2todo 自动生成<br>
导入方式：手机打开附件 → 选择「日历」→ 确认导入
</p>
</body>
</html>"""

        msg = MIMEMultipart()
        msg["From"] = self.config.email
        msg["To"] = self.config.email  # 发给自己
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html", "utf-8"))

        # 添加 ICS 附件
        with open(ics_file_path, "rb") as f:
            ics_data = f.read()

        attachment = MIMEBase("text", "calendar", method="REQUEST", name="todo_events.ics")
        attachment.add_header("Content-Type", "text/calendar; charset=utf-8; method=REQUEST")
        attachment.add_header("Content-Disposition", "attachment", filename="todo_events.ics")
        attachment.set_payload(ics_data)
        encoders.encode_base64(attachment)
        msg.attach(attachment)

        try:
            with smtplib.SMTP_SSL(self.config.smtp_server, self.config.smtp_port) as smtp:
                smtp.login(self.config.email, self.config.auth_code)
                smtp.sendmail(self.config.email, self.config.email, msg.as_string())
            logger.info(f"邮件已发送到 {self.config.email}")
            return True
        except smtplib.SMTPAuthenticationError:
            logger.error("SMTP 认证失败，请检查授权码是否正确")
            return False
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            return False
