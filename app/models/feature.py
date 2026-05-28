import sqlite3

from app.models.db import get_connection
from app.models.rbac import RBACRepository

# 功能菜单：与侧栏一一对应，绑定 permission_code
FEATURE_DEFINITIONS = [
    ("用户管理", "feature.users", "系统管理", "/admin/users", "system.user", "fas fa-users", "users", 10),
    ("角色管理", "feature.roles", "系统管理", "/admin/roles", "system.role", "fas fa-user-shield", "roles", 20),
    ("权限管理", "feature.permissions", "系统管理", "/admin/permissions", "system.permission", "fas fa-sitemap", "permissions", 30),
    ("功能菜单", "feature.features", "系统管理", "/admin/features", "system.feature", "fas fa-th-large", "features", 40),
    ("接口管理", "feature.api", "业务管理", "/admin/api-interfaces", "system.api", "fas fa-plug", "api_interfaces", 50),
    ("数字员工", "feature.digital", "业务管理", "/admin/digital-employees", "system.digital_employee", "fas fa-user-astronaut", "digital_employees", 60),
    ("模型引擎", "feature.models", "业务管理", "/admin/models", "system.model", "fas fa-microchip", "models", 70),
    ("智能瞭望采集", "feature.watch", "业务管理", "/admin/watch-sources", "system.watch", "fas fa-satellite-dish", "watch_sources", 80),
    ("采集结果", "feature.watch_records", "业务管理", "/admin/watch-records", "system.watch_record", "fas fa-database", "watch_records", 90),
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
                conn.execute(
                    """
                    UPDATE features SET
                        name=?, menu_group=?, route_path=?, permission_code=?,
                        icon=?, active_page=?, sort_no=?
                    WHERE code=?
                    """,
                    (name, menu_group, route_path, permission_code, icon, active_page, sort_no, code),
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
                "select * from features order by menu_group, sort_no asc, id asc"
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
        features = FeatureRepository.list_features()
        visible = []
        for feature in features:
            if not feature["is_enabled"]:
                continue
            perm_code = feature["permission_code"]
            if not perm_code:
                continue
            if RBACRepository.role_has_permission(role_id, role_code, perm_code):
                visible.append(feature)
        return visible

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
