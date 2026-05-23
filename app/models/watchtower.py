import json
import sqlite3
from datetime import datetime

from app.models.db import get_connection


class WatchtowerRepository:
    @staticmethod
    def list_sources():
        with get_connection() as conn:
            return conn.execute("select * from watch_sources order by is_enabled desc, id desc").fetchall()

    @staticmethod
    def get_source(source_id: int):
        with get_connection() as conn:
            return conn.execute("select * from watch_sources where id = ?", (source_id,)).fetchone()

    @staticmethod
    def create_source(data: dict) -> bool:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    insert into watch_sources(name, source_code, entry_urls_json, headers_json, keywords_label,
                                              page_param_name, page_step, collect_limit, is_enabled, note)
                    values(?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        data.get("name"),
                        data.get("source_code"),
                        json.dumps(data.get("entry_urls", []), ensure_ascii=False),
                        json.dumps(data.get("headers", {}), ensure_ascii=False),
                        data.get("keywords_label", "关键字"),
                        data.get("page_param_name", "pn"),
                        int(data.get("page_step", 10)),
                        int(data.get("collect_limit", 10)),
                        int(data.get("is_enabled", 1)),
                        data.get("note", ""),
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def update_source(source_id: int, data: dict) -> bool:
        with get_connection() as conn:
            conn.execute(
                """
                update watch_sources set
                    name=?, source_code=?, entry_urls_json=?, headers_json=?, keywords_label=?,
                    page_param_name=?, page_step=?, collect_limit=?, is_enabled=?, note=?, updated_at=datetime('now')
                where id=?
                """,
                (
                    data.get("name"),
                    data.get("source_code"),
                    json.dumps(data.get("entry_urls", []), ensure_ascii=False),
                    json.dumps(data.get("headers", {}), ensure_ascii=False),
                    data.get("keywords_label", "关键字"),
                    data.get("page_param_name", "pn"),
                    int(data.get("page_step", 10)),
                    int(data.get("collect_limit", 10)),
                    int(data.get("is_enabled", 1)),
                    data.get("note", ""),
                    source_id,
                ),
            )
        return True

    @staticmethod
    def delete_source(source_id: int) -> None:
        with get_connection() as conn:
            conn.execute("delete from watch_sources where id = ?", (source_id,))

    @staticmethod
    def collect(source_id: int, keyword: str, page_count: int, item_count: int):
        source = WatchtowerRepository.get_source(source_id)
        if not source:
            return []
        rows = []
        for page_index in range(max(1, page_count)):
            for item_index in range(max(1, item_count)):
                rows.append(
                    {
                        "source_id": source_id,
                        "source_name": source["name"],
                        "keyword": keyword,
                        "title": f"{keyword} - 模拟采集结果 {page_index + 1}-{item_index + 1}",
                        "content": f"来自 {source['name']} 的动态采集内容，支持后续批量采集任务接入。",
                        "url": source["entry_urls_json"],
                    }
                )
        return rows

    @staticmethod
    def save_records(records: list[dict]):
        if not records:
            return
        with get_connection() as conn:
            for record in records:
                conn.execute(
                    """
                    insert into watch_records(source_id, source_name, keyword, title, content, url)
                    values(?,?,?,?,?,?)
                    """,
                    (
                        record["source_id"],
                        record["source_name"],
                        record["keyword"],
                        record["title"],
                        record["content"],
                        record["url"],
                    ),
                )

    @staticmethod
    def list_records(page: int = 1, page_size: int = 20):
        offset = (page - 1) * page_size
        with get_connection() as conn:
            total = conn.execute("select count(1) as c from watch_records").fetchone()["c"]
            rows = conn.execute(
                "select * from watch_records order by id desc limit ? offset ?",
                (page_size, offset),
            ).fetchall()
        return int(total), rows

    @staticmethod
    def delete_record(record_id: int):
        with get_connection() as conn:
            conn.execute("delete from watch_records where id = ?", (record_id,))

    @staticmethod
    def batch_delete_records(ids: list[int]):
        if not ids:
            return
        placeholders = ",".join(["?"] * len(ids))
        with get_connection() as conn:
            conn.execute(f"delete from watch_records where id in ({placeholders})", ids)
