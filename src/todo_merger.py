"""通知合并与去重模块"""
from datetime import datetime, timedelta
from src.db_manager import DBManager
from src.logger import get_logger

logger = get_logger("todo_merger")

PAST_CUTOFF_DAYS = 7   # 超过7天前的跳过（已过期）
FUTURE_CUTOFF_DAYS = 35  # 超过35天后的跳过（太远）


class TodoMerger:
    """合并来自不同源的通知，去重后返回新增项"""

    def __init__(self, db: DBManager):
        self.db = db

    def merge(self, items: list) -> list:
        """对通知列表去重、时间过滤，返回新增的通知"""
        new_items = []
        skipped_db = 0
        skipped_time = 0

        today = datetime.now().date()
        past_cutoff = today - timedelta(days=PAST_CUTOFF_DAYS)
        future_cutoff = today + timedelta(days=FUTURE_CUTOFF_DAYS)

        for item in items:
            source = item.get("source", "")
            source_id = item.get("source_id", "")

            if not source or not source_id:
                skipped_db += 1
                continue

            if self.db.is_processed(source, source_id):
                skipped_db += 1
                continue

            # 时间过滤
            event_date_str = item.get("event_date", "")
            if event_date_str:
                try:
                    event_date = datetime.strptime(event_date_str, "%Y-%m-%d").date()
                    if event_date < past_cutoff:
                        skipped_time += 1
                        continue
                    if event_date > future_cutoff:
                        skipped_time += 1
                        continue
                except ValueError:
                    pass

            if self.db.mark_processed(item):
                new_items.append(item)
            else:
                skipped_db += 1

        logger.info(f"合并结果: {len(new_items)} 条新增, {skipped_db} 条跳过(重复), {skipped_time} 条跳过(时间)")
        return new_items

    def preprocess_item(
        self,
        source: str,
        source_id: str,
        title: str,
        summary: str = "",
        url: str = "",
        event_date: str = "",
        **extra,
    ) -> dict:
        """标准化通知格式"""
        # 截断过长标题
        if len(title) > 80:
            title = title[:77] + "..."

        # 如果没有明确日期，使用当天日期
        if not event_date:
            event_date = datetime.now().strftime("%Y-%m-%d")

        return {
            "source": source,
            "source_id": str(source_id),
            "title": title,
            "summary": summary,
            "url": url,
            "event_date": event_date,
            **extra,
        }
