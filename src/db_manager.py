"""SQLite 数据库管理模块"""
import sqlite3
import os
from src.logger import get_logger

logger = get_logger("db_manager")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS processed_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    url TEXT,
    event_date TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(source, source_id)
);
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_source_id ON processed_items(source, source_id);
"""


class DBManager:
    """管理已处理通知的数据库"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        conn = None
        try:
            conn = self._get_conn()
            conn.execute(CREATE_TABLE_SQL)
            conn.execute(CREATE_INDEX_SQL)
            conn.commit()
            logger.debug("数据库初始化完成")
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def is_processed(self, source: str, source_id: str) -> bool:
        """检查通知是否已处理"""
        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.execute(
                "SELECT 1 FROM processed_items WHERE source = ? AND source_id = ?",
                (source, source_id),
            )
            return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"查询去重失败: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def mark_processed(self, item: dict) -> bool:
        """标记通知为已处理，返回 True 表示新增，False 表示已存在"""
        conn = None
        try:
            conn = self._get_conn()
            conn.execute(
                """INSERT OR IGNORE INTO processed_items
                   (source, source_id, title, summary, url, event_date)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    item["source"],
                    item["source_id"],
                    item["title"],
                    item.get("summary", ""),
                    item.get("url", ""),
                    item.get("event_date", ""),
                ),
            )
            conn.commit()
            return conn.total_changes > 0
        except Exception as e:
            logger.error(f"标记已处理失败: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def cleanup_old_items(self, days: int = 90) -> int:
        """清理N天前的旧记录"""
        conn = None
        try:
            conn = self._get_conn()
            cursor = conn.execute(
                f"DELETE FROM processed_items WHERE created_at < datetime('now', 'localtime', '-{days} days')"
            )
            conn.commit()
            deleted = cursor.rowcount
            if deleted > 0:
                logger.info(f"清理了 {deleted} 条旧记录")
            return deleted
        except Exception as e:
            logger.error(f"清理旧记录失败: {e}")
            return 0
        finally:
            if conn:
                conn.close()
