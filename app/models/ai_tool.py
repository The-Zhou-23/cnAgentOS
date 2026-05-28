"""AI 工具集管理（Task3：绑定数字员工）。"""

import json
import sqlite3

from app.models.db import get_connection


class AIToolRepository:
    @staticmethod
    def init_schema():
        with get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_tools(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    tool_type TEXT NOT NULL DEFAULT 'http',
                    description TEXT NOT NULL DEFAULT '',
                    config_json TEXT NOT NULL DEFAULT '{}',
                    is_enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT(datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT(datetime('now'))
                )
                """
            )

    @staticmethod
    def list_tools():
        with get_connection() as conn:
            return conn.execute(
                "select * from ai_tools order by is_enabled desc, id desc"
            ).fetchall()

    @staticmethod
    def get_tool(tool_id: int):
        with get_connection() as conn:
            return conn.execute("select * from ai_tools where id=?", (tool_id,)).fetchone()

    @staticmethod
    def create_tool(data: dict) -> bool:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    insert into ai_tools(name, tool_type, description, config_json, is_enabled)
                    values(?,?,?,?,?)
                    """,
                    (
                        data["name"],
                        data.get("tool_type", "http"),
                        data.get("description", ""),
                        data.get("config_json", "{}"),
                        int(data.get("is_enabled", 1)),
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def update_tool(tool_id: int, data: dict) -> bool:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    update ai_tools set name=?, tool_type=?, description=?, config_json=?,
                        is_enabled=?, updated_at=datetime('now')
                    where id=?
                    """,
                    (
                        data["name"],
                        data.get("tool_type", "http"),
                        data.get("description", ""),
                        data.get("config_json", "{}"),
                        int(data.get("is_enabled", 1)),
                        tool_id,
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def delete_tool(tool_id: int):
        with get_connection() as conn:
            conn.execute("delete from ai_tools where id=?", (tool_id,))

    @staticmethod
    def bind_tools_to_employee(employee_id: int, tool_ids: list[int]):
        from app.models.digital_employee import DigitalEmployeeRepository

        emp = DigitalEmployeeRepository.get_employee(employee_id)
        if not emp:
            return False
        try:
            config = json.loads(emp["config_json"] or "{}")
        except Exception:
            config = {}
        config["tool_ids"] = [int(x) for x in tool_ids]
        with get_connection() as conn:
            conn.execute(
                "update digital_employees set config_json=?, updated_at=datetime('now') where id=?",
                (json.dumps(config, ensure_ascii=False), employee_id),
            )
        return True

    @staticmethod
    def get_employee_tool_ids(employee_id: int) -> list[int]:
        from app.models.digital_employee import DigitalEmployeeRepository

        emp = DigitalEmployeeRepository.get_employee(employee_id)
        if not emp:
            return []
        try:
            config = json.loads(emp["config_json"] or "{}")
            return [int(x) for x in config.get("tool_ids", [])]
        except Exception:
            return []

    @staticmethod
    def ensure_defaults():
        defaults = [
            ("天气查询", "http", "调用天气 API 获取城市天气", '{"api":"天气 API"}'),
            ("新闻检索", "internal", "从智能瞭望读取最近新闻", '{"kind":"news"}'),
            ("随机音乐", "http", "调用音乐 API", '{"api":"音乐 API"}'),
        ]
        with get_connection() as conn:
            for name, ttype, desc, cfg in defaults:
                conn.execute(
                    """
                    insert or ignore into ai_tools(name, tool_type, description, config_json)
                    values(?,?,?,?)
                    """,
                    (name, ttype, desc, cfg),
                )
