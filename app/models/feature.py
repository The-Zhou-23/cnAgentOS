import sqlite3

from app.models.db import get_connection
from app.models.rbac import RBACRepository

# 功能菜单：与侧栏一一对应，绑定 permission_code
FEATURE_DEFINITIONS = [
    ("用户管理", "feature.users", "系统管理", "/admin/users", "system.user", "fas fa-users", "users", 10),
    ("角色管理", "feature.roles", "系统管理", "/admin/roles", "system.role", "fas fa-user-shield", "roles", 20),
    ("权限管理", "feature.permissions", "系统管理", "/admin/permissions", "system.permission", "fas fa-sitemap", "permissions", 30),
    ("功能菜单", "feature.features", "系统管理", "/admin/features", "system.feature", "fas fa-th-large", "features", 40),
    ("数据库配置", "feature.database", "系统管理", "/admin/database", "system.database", "fas fa-database", "database", 45),
    ("接口管理", "feature.api", "业务管理", "/admin/api-interfaces", "system.api", "fas fa-plug", "api_interfaces", 50),
    ("数字员工", "feature.digital", "业务管理", "/admin/digital-employees", "system.digital_employee", "fas fa-user-astronaut", "digital_employees", 60),
    ("模型引擎", "feature.models", "业务管理", "/admin/models", "system.model", "fas fa-microchip", "models", 70),
    ("智能瞭望采集", "feature.watch", "业务管理", "/admin/watch-sources", "system.watch", "fas fa-satellite-dish", "watch_sources", 80),
    ("采集结果", "feature.watch_records", "业务管理", "/admin/watch-records", "system.watch_record", "fas fa-database", "watch_records", 90),
    ("聊天群管理", "feature.chat_groups", "业务管理", "/admin/chat/groups", "system.chat_group", "fas fa-users", "chat_groups", 100),
    ("聊天文件", "feature.chat_files", "业务管理", "/admin/chat/files", "system.chat_file", "fas fa-folder-open", "chat_files", 110),
    ("聊天服务器", "feature.chat_servers", "业务管理", "/admin/chat/servers", "system.chat_server", "fas fa-server", "chat_servers", 120),
    ("工具集管理", "feature.tools", "业务管理", "/admin/tools", "system.ai_tool", "fas fa-toolbox", "tools", 130),
    ("自动化调度", "feature.automation", "业务管理", "/admin/automation", "system.automation", "fas fa-robot", "automation", 140),
]


class FeatureRepository:
    @staticmethod
    def ensure_defaults():
        with get_connection() as conn:
            for (
                name,
                code,
                menu_group,
                route_path,
                permission_code,
                icon,
                active_page,
                sort_no,
            ) in FEATURE_DEFINITIONS:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO features(
                        name, code, menu_group, route_path, permission_code,
                        icon, active_page, sort_no, is_enabled
                    ) VALUES(?,?,?,?,?,?,?,?,1)
                    """,
                    (name, code, menu_group, route_path, permission_code, icon, active_page, sort_no),
                )
                # 仅同步开发侧字段，不覆盖用户在「功能菜单」中改的排序/名称/分组
                conn.execute(
                    """
                    UPDATE features SET
                        route_path=?, permission_code=?, icon=?, active_page=?
                    WHERE code=?
                    """,
                    (route_path, permission_code, icon, active_page, code),
                )

            valid_codes = {item[1] for item in FEATURE_DEFINITIONS}
            rows = conn.execute("select id, code from features").fetchall()
            for row in rows:
                if row["code"] not in valid_codes:
                    conn.execute("delete from features where id = ?", (row["id"],))

    @staticmethod
    def list_features():
        with get_connection() as conn:
            return conn.execute(
                "select * from features order by sort_no asc, menu_group asc, id asc"
            ).fetchall()

    @staticmethod
    def get_feature(feature_id: int):
        with get_connection() as conn:
            return conn.execute("select * from features where id = ?", (feature_id,)).fetchone()

    @staticmethod
    def get_permission_code_for_route(route_path: str) -> str | None:
        path = (route_path or "").rstrip("/") or "/"
        with get_connection() as conn:
            row = conn.execute(
                """
                select permission_code from features
                where is_enabled = 1 and (
                    route_path = ? or ? like route_path || '/%'
                )
                order by length(route_path) desc
                limit 1
                """,
                (path, path),
            ).fetchone()
        if not row:
            return None
        return row["permission_code"]

    @staticmethod
    def list_sidebar_features(role_id: int | None, role_code: str | None):
        visible = []
        for feature in FeatureRepository.list_features():
            if not feature["is_enabled"]:
                continue
            perm_code = feature["permission_code"]
            if not perm_code:
                continue
            if RBACRepository.role_has_permission(role_id, role_code, perm_code):
                visible.append(feature)
        # 与功能菜单页一致：全局按 sort_no，再按 id
        return sorted(visible, key=lambda f: (int(f["sort_no"] or 0), int(f["id"])))

    @staticmethod
    def update_feature(feature_id: int, data: dict) -> bool:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    update features set
                        name=?, menu_group=?, route_path=?, sort_no=?,
                        is_enabled=?, updated_at=datetime('now')
                    where id=?
                    """,
                    (
                        data.get("name"),
                        data.get("menu_group"),
                        data.get("route_path"),
                        int(data.get("sort_no", 0)),
                        int(data.get("is_enabled", 1)),
                        feature_id,
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def toggle_feature(feature_id: int, enabled: bool) -> bool:
        with get_connection() as conn:
            conn.execute(
                "update features set is_enabled=?, updated_at=datetime('now') where id=?",
                (1 if enabled else 0, feature_id),
            )
        return True
