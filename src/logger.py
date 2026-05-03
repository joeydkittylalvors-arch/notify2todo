"""日志配置模块"""
import logging
import os
from logging.handlers import RotatingFileHandler

_logger_initialized = False


def setup_logging(config=None):
    """初始化日志系统，同时输出到控制台和文件"""
    global _logger_initialized
    if _logger_initialized:
        return

    log_level = logging.INFO
    log_dir = "./logs"
    max_bytes = 10 * 1024 * 1024
    backup_count = 5

    if config:
        log_level = getattr(logging, config.get("level", "INFO"), logging.INFO)
        max_bytes = config.get("max_bytes", max_bytes)
        backup_count = config.get("backup_count", backup_count)

    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "notify2todo.log")

    root_logger = logging.getLogger("notify2todo")
    root_logger.setLevel(log_level)

    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_fmt)
    root_logger.addHandler(console_handler)

    # 文件输出（按大小轮转）
    file_handler = RotatingFileHandler(
        log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setLevel(log_level)
    file_fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_fmt)
    root_logger.addHandler(file_handler)

    _logger_initialized = True


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的logger"""
    return logging.getLogger(f"notify2todo.{name}")
