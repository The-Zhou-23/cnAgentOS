import sqlite3

from app.models.db import get_connection


class RBACRepository:
    @staticmethod
    def list_roles():
        with get_connection() as conn:
            return conn.execute("select * from roles order by is_system desc, id asc").fetchall()

    @staticmethod
    def create_role(name: str, code: str) -> bool:
        try:
            with get_connection() as conn:
                conn.execute(
                    "insert into roles(name, code, is_system) values(?,?,0)",
                    (name, code),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def update_role(role_id: int, name: str, code: str) -> bool:
        with get_connection() as conn:
            role = conn.execute("select is_system from roles where id = ?", (role_id,)).fetchone()
            if not role or role["is_system"]:
                return False
            try:
                conn.execute("update roles set name = ?, code = ? where id = ?", (name, code, role_id))
                return True
            except sqlite3.IntegrityError:
                return False

    @staticmethod
    def delete_role(role_id: int) -> bool:
        with get_connection() as conn:
            role = conn.execute("select is_system from roles where id = ?", (role_id,)).fetchone()
            if not role or role["is_system"]:
                return False
            conn.execute("delete from role_permissions where role_id = ?", (role_id,))
            conn.execute("delete from roles where id = ?", (role_id,))
            return True

    @staticmethod
    def list_permissions():
        with get_connection() as conn:
            return conn.execute("select * from permissions order by menu_group, sort_no, id").fetchall()

    @staticmethod
    def create_permission(menu_group: str, name: str, code: str, sort_no: int = 0) -> bool:
        try:
            with get_connection() as conn:
                conn.execute(
                    "insert into permissions(menu_group, name, code, sort_no) values(?,?,?,?)",
                    (menu_group, name, code, sort_no),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def update_permission(permission_id: int, menu_group: str, name: str, code: str, sort_no: int = 0) -> bool:
        try:
            with get_connection() as conn:
                conn.execute(
                    "update permissions set menu_group=?, name=?, code=?, sort_no=? where id=?",
                    (menu_group, name, code, sort_no, permission_id),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def delete_permission(permission_id: int) -> None:
        with get_connection() as conn:
            conn.execute("delete from role_permissions where permission_id = ?", (permission_id,))
            conn.execute("delete from permissions where id = ?", (permission_id,))

    @staticmethod
    def get_role_permissions(role_id: int):
        with get_connection() as conn:
            rows = conn.execute(
                "select permission_id from role_permissions where role_id = ?",
                (role_id,),
            ).fetchall()
        return {row["permission_id"] for row in rows}

    @staticmethod
    def set_role_permissions(role_id: int, permission_ids: list[int]):
        with get_connection() as conn:
            conn.execute("delete from role_permissions where role_id = ?", (role_id,))
            for permission_id in permission_ids:
                conn.execute(
                    "insert or ignore into role_permissions(role_id, permission_id) values(?,?)",
                    (role_id, permission_id),
                )
