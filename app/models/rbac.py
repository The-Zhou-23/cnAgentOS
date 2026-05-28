import sqlite3

from app.models.db import get_connection


# 权限项：控制能否访问对应后台模块
PERMISSION_DEFINITIONS = [
    ("系统管理", "用户管理", "system.user", 10),
    ("系统管理", "角色管理", "system.role", 20),
    ("系统管理", "权限管理", "system.permission", 30),
    ("系统管理", "功能菜单", "system.feature", 40),
    ("系统管理", "数据库配置", "system.database", 45),
    ("业务管理", "接口管理", "system.api", 50),
    ("业务管理", "数字员工", "system.digital_employee", 60),
    ("业务管理", "模型引擎", "system.model", 70),
    ("业务管理", "智能瞭望", "system.watch", 80),
    ("业务管理", "采集结果", "system.watch_record", 90),
    ("业务管理", "聊天群管理", "system.chat_group", 100),
    ("业务管理", "聊天文件", "system.chat_file", 110),
    ("业务管理", "聊天服务器", "system.chat_server", 120),
    ("业务管理", "工具集管理", "system.ai_tool", 130),
]

# 普通管理员默认拥有的业务权限（不含角色/权限/功能菜单配置）
NORMAL_ADMIN_PERMISSION_CODES = [
    "system.user",
    "system.database",
    "system.api",
    "system.digital_employee",
    "system.model",
    "system.watch",
    "system.watch_record",
    "system.chat_group",
    "system.chat_file",
    "system.chat_server",
    "system.ai_tool",
]

OBSOLETE_PERMISSION_CODES = ("system.menu",)


class RBACRepository:
    @staticmethod
    def list_roles():
        with get_connection() as conn:
            return conn.execute("select * from roles order by is_system desc, id asc").fetchall()

    @staticmethod
    def get_role_by_code(code: str):
        with get_connection() as conn:
            return conn.execute("select * from roles where code = ?", (code,)).fetchone()

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
    def list_permissions_grouped():
        grouped: dict[str, list] = {}
        for row in RBACRepository.list_permissions():
            grouped.setdefault(row["menu_group"], []).append(row)
        return grouped

    @staticmethod
    def get_permission_by_code(code: str):
        with get_connection() as conn:
            return conn.execute("select * from permissions where code = ?", (code,)).fetchone()

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
    def get_role_permission_codes(role_id: int) -> set[str]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                select p.code
                from role_permissions rp
                join permissions p on p.id = rp.permission_id
                where rp.role_id = ?
                """,
                (role_id,),
            ).fetchall()
        return {row["code"] for row in rows}

    @staticmethod
    def set_role_permissions(role_id: int, permission_ids: list[int]):
        with get_connection() as conn:
            conn.execute("delete from role_permissions where role_id = ?", (role_id,))
            for permission_id in permission_ids:
                conn.execute(
                    "insert or ignore into role_permissions(role_id, permission_id) values(?,?)",
                    (role_id, permission_id),
                )

    @staticmethod
    def role_has_permission(role_id: int | None, role_code: str | None, permission_code: str) -> bool:
        if role_code == "super_admin":
            return True
        if not role_id or not permission_code:
            return False
        return permission_code in RBACRepository.get_role_permission_codes(role_id)

    @staticmethod
    def ensure_default_permissions():
        with get_connection() as conn:
            for menu_group, name, code, sort_no in PERMISSION_DEFINITIONS:
                conn.execute(
                    "INSERT OR IGNORE INTO permissions(menu_group, name, code, sort_no) VALUES(?,?,?,?)",
                    (menu_group, name, code, sort_no),
                )
                conn.execute(
                    "UPDATE permissions SET menu_group=?, name=?, sort_no=? WHERE code=?",
                    (menu_group, name, sort_no, code),
                )

            for obsolete_code in OBSOLETE_PERMISSION_CODES:
                row = conn.execute("select id from permissions where code = ?", (obsolete_code,)).fetchone()
                if row:
                    conn.execute("delete from role_permissions where permission_id = ?", (row["id"],))
                    conn.execute("delete from permissions where id = ?", (row["id"],))

    @staticmethod
    def ensure_default_role_permissions():
        with get_connection() as conn:
            super_role = conn.execute("select id from roles where code = 'super_admin'").fetchone()
            normal_role = conn.execute("select id from roles where code = 'normal_admin'").fetchone()
            if not super_role:
                return

            all_perm_rows = conn.execute("select id, code from permissions").fetchall()
            for perm in all_perm_rows:
                conn.execute(
                    "INSERT OR IGNORE INTO role_permissions(role_id, permission_id) VALUES(?, ?)",
                    (super_role["id"], perm["id"]),
                )

            if not normal_role:
                return

            for perm in all_perm_rows:
                if perm["code"] in NORMAL_ADMIN_PERMISSION_CODES:
                    conn.execute(
                        "INSERT OR IGNORE INTO role_permissions(role_id, permission_id) VALUES(?, ?)",
                        (normal_role["id"], perm["id"]),
                    )
