import sqlite3

from app.models.db import get_connection


class APIInterfaceRepository:
    @staticmethod
    def list_interfaces():
        with get_connection() as conn:
            return conn.execute("select * from api_interfaces order by id asc").fetchall()

    @staticmethod
    def get_interface(interface_id: int):
        with get_connection() as conn:
            return conn.execute("select * from api_interfaces where id = ?", (interface_id,)).fetchone()

    @staticmethod
    def create_interface(data: dict) -> bool:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    insert into api_interfaces(name, api_url, response_format, request_method, request_example, qps_limit, note)
                    values(?,?,?,?,?,?,?)
                    """,
                    (
                        data.get("name"),
                        data.get("api_url"),
                        data.get("response_format", "JSON"),
                        data.get("request_method", "GET"),
                        data.get("request_example", data.get("api_url")),
                        data.get("qps_limit", "每2秒最多4次，携带Token可无视限制"),
                        data.get("note", ""),
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def update_interface(interface_id: int, data: dict) -> bool:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    update api_interfaces set
                        name=?, api_url=?, response_format=?, request_method=?, request_example=?, qps_limit=?, note=?, updated_at=datetime('now')
                    where id=?
                    """,
                    (
                        data.get("name"),
                        data.get("api_url"),
                        data.get("response_format", "JSON"),
                        data.get("request_method", "GET"),
                        data.get("request_example", data.get("api_url")),
                        data.get("qps_limit", "每2秒最多4次，携带Token可无视限制"),
                        data.get("note", ""),
                        interface_id,
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def delete_interface(interface_id: int) -> None:
        with get_connection() as conn:
            conn.execute("delete from api_interfaces where id = ?", (interface_id,))
