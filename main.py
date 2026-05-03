"""notify2todo 主入口 —— 通知转待办"""
import sys
import os
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.logger import setup_logging, get_logger
from src.config_loader import load_config, ConfigurationError
from src.db_manager import DBManager
from src.todo_merger import TodoMerger
from src.qqmail_fetcher import QQMailFetcher
from src.ics_exporter import ICSExporter
from src.mail_sender import MailSender

logger = get_logger("main")


def main():
    logger.info("===== notify2todo 开始运行 =====")

    # 1. 加载配置
    try:
        config = load_config("config.yaml")
    except ConfigurationError as e:
        logger.error(f"配置错误: {e}")
        return 1

    setup_logging(config.logging)

    # 2. 初始化数据库
    db = DBManager(config.database.path)

    # 3. 获取所有通知
    all_items = []

    # 3a. QQ邮箱
    try:
        qqmail = QQMailFetcher(config.qqmail)
        qqmail_items = qqmail.fetch()
        all_items.extend(qqmail_items)
        logger.info(f"QQ邮箱: 获取 {len(qqmail_items)} 条")
    except Exception as e:
        logger.error(f"QQ邮箱抓取失败: {e}")

    # 3b. 学习通（可选，如果未配置则跳过）
    if config.chaoxing.username and config.chaoxing.password:
        try:
            from src.chaoxing_fetcher import ChaoxingFetcher

            chaoxing = ChaoxingFetcher(config.chaoxing)
            chaoxing_items = chaoxing.fetch()
            all_items.extend(chaoxing_items)
            logger.info(f"学习通: 获取 {len(chaoxing_items)} 条")
        except ImportError:
            logger.warning("学习通模块未实现，跳过")
        except Exception as e:
            logger.error(f"学习通抓取失败: {e}")
    else:
        logger.info("学习通未配置，跳过")

    # 4. 去重合并
    merger = TodoMerger(db)
    new_items = merger.merge(all_items)
    logger.info(f"去重后: {len(new_items)} 条新通知")

    # 5. 导出 ICS
    if new_items:
        exporter = ICSExporter(config.ics)
        ics_path = exporter.export(new_items)

        # 6. 发送邮件
        sender = MailSender(config.qqmail, config.ics)
        if sender.send_ics(ics_path, len(new_items)):
            logger.info("邮件发送成功")
        else:
            logger.warning("邮件发送失败，ICS文件已保存到本地 output/ 目录")
    else:
        logger.info("没有新通知，跳过发送")

    # 7. 定期清理旧记录
    db.cleanup_old_items(90)

    # 8. 写成功标记
    success_file = os.path.join(config.ics.output_dir, "last_run.txt")
    with open(success_file, "w", encoding="utf-8") as f:
        f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    logger.info("===== notify2todo 运行结束 =====")
    return 0


if __name__ == "__main__":
    sys.exit(main())
