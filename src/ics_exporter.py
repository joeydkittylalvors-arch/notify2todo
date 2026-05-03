"""ICS 日历文件生成模块"""
import os
from datetime import datetime, timedelta
from icalendar import Calendar, Event, Alarm
from src.logger import get_logger

logger = get_logger("ics_exporter")


class ICSExporter:
    """将通知列表导出为 ICS 日历文件"""

    def __init__(self, config):
        self.config = config
        self.output_path = os.path.join(config.output_dir, config.filename)

    def export(self, items: list) -> str:
        """导出通知为 ICS 文件，返回文件路径"""
        cal = Calendar()
        cal.add("prodid", "-//notify2todo//CN")
        cal.add("version", "2.0")
        cal.add("x-wr-calname", self.config.calendar_name)
        cal.add("x-wr-caldesc", "自动生成的待办日历 - notify2todo")

        for item in items:
            event = self._create_event(item)
            cal.add_component(event)

        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        with open(self.output_path, "wb") as f:
            f.write(cal.to_ical())

        logger.info(f"ICS 文件已写入: {self.output_path} ({len(items)} 个事件)")
        return self.output_path

    def _create_event(self, item: dict) -> Event:
        """为单条通知创建日历事件"""
        event = Event()

        # 唯一标识（避免重复导入）
        uid = f"{item['source']}-{item['source_id']}@notify2todo"
        event.add("uid", uid)

        # 标题：加来源标签
        source_label = {"qqmail": "[邮件]", "chaoxing": "[学习通]"}.get(item["source"], "")
        event.add("summary", f"{source_label} {item['title']}")

        # 描述
        desc_parts = []
        if item.get("summary"):
            desc_parts.append(item["summary"])
        if item.get("url"):
            desc_parts.append(f"\n原文链接: {item['url']}")
        if item.get("sender"):
            desc_parts.append(f"发件人: {item['sender']}")
        if item.get("course_name"):
            desc_parts.append(f"课程: {item['course_name']}")
        event.add("description", "\n".join(desc_parts))

        # 日期时间
        event_date_str = item.get("event_date", "")
        try:
            event_date = datetime.strptime(event_date_str, "%Y-%m-%d")
            event.add("dtstart", event_date.date())
            event.add("dtend", event_date.date() + timedelta(days=1))
        except ValueError:
            # 日期无效时使用今天
            today = datetime.now().date()
            event.add("dtstart", today)
            event.add("dtend", today + timedelta(days=1))

        # 分类标签
        if "type" in item:
            event.add("categories", item["type"])

        # 提醒（提前N分钟）
        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("description", f"待办提醒: {item['title']}")
        alarm.add("trigger", timedelta(minutes=-self.config.default_alarm_minutes))
        event.add_component(alarm)

        return event
