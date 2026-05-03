"""配置加载与校验模块"""
import os
import yaml
from dataclasses import dataclass, field


@dataclass
class QQMailConfig:
    imap_server: str
    imap_port: int
    email: str
    auth_code: str
    smtp_server: str
    smtp_port: int
    keywords: list
    exclude_senders: list = field(default_factory=list)
    lookback_days: int = 7


@dataclass
class ChaoxingConfig:
    username: str
    password: str
    school_name: str
    lookback_days: int = 7


@dataclass
class ICSConfig:
    output_dir: str = "./output"
    filename: str = "todo_events.ics"
    default_alarm_minutes: int = 30
    calendar_name: str = "通知待办"


@dataclass
class DatabaseConfig:
    path: str = "./db/todo.db"


@dataclass
class AppConfig:
    qqmail: QQMailConfig
    chaoxing: ChaoxingConfig
    ics: ICSConfig
    database: DatabaseConfig
    logging: dict = field(default_factory=dict)


class ConfigurationError(Exception):
    """配置错误异常"""
    pass


def load_config(config_path: str) -> AppConfig:
    """加载并校验配置文件"""
    if not os.path.exists(config_path):
        raise ConfigurationError(
            f"配置文件不存在: {config_path}\n"
            f"请复制 config.example.yaml 为 config.yaml 并填写你的信息。"
        )

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if raw is None:
        raise ConfigurationError("配置文件为空")

    # 校验 qqmail
    qqmail_raw = raw.get("qqmail", {})
    if not qqmail_raw.get("email") or qqmail_raw.get("email") == "your_email@qq.com":
        raise ConfigurationError("请在 config.yaml 中填写 QQ邮箱地址")
    if not qqmail_raw.get("auth_code") or qqmail_raw.get("auth_code") == "xxxxxxxxxxxxxx":
        raise ConfigurationError("请在 config.yaml 中填写 QQ邮箱授权码")

    qqmail = QQMailConfig(
        imap_server=qqmail_raw.get("imap_server", "imap.qq.com"),
        imap_port=qqmail_raw.get("imap_port", 993),
        email=qqmail_raw["email"],
        auth_code=qqmail_raw["auth_code"],
        smtp_server=qqmail_raw.get("smtp_server", "smtp.qq.com"),
        smtp_port=qqmail_raw.get("smtp_port", 465),
        keywords=qqmail_raw.get("keywords", ["通知", "作业", "考试", "重要", "截止"]),
        exclude_senders=qqmail_raw.get("exclude_senders", []),
        lookback_days=qqmail_raw.get("lookback_days", 7),
    )

    # 校验 chaoxing（非必填，可以只使用QQ邮箱）
    chaoxing_raw = raw.get("chaoxing", {})
    chaoxing = ChaoxingConfig(
        username=chaoxing_raw.get("username", ""),
        password=chaoxing_raw.get("password", ""),
        school_name=chaoxing_raw.get("school_name", ""),
        lookback_days=chaoxing_raw.get("lookback_days", 7),
    )

    # ICS
    ics_raw = raw.get("ics", {})
    ics = ICSConfig(
        output_dir=ics_raw.get("output_dir", "./output"),
        filename=ics_raw.get("filename", "todo_events.ics"),
        default_alarm_minutes=ics_raw.get("default_alarm_minutes", 30),
        calendar_name=ics_raw.get("calendar_name", "通知待办"),
    )
    os.makedirs(ics.output_dir, exist_ok=True)

    # Database
    db_raw = raw.get("database", {})
    db_path = db_raw.get("path", "./db/todo.db")
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    database = DatabaseConfig(path=db_path)

    # Logging
    logging_cfg = raw.get("logging", {})

    return AppConfig(
        qqmail=qqmail,
        chaoxing=chaoxing,
        ics=ics,
        database=database,
        logging=logging_cfg,
    )
