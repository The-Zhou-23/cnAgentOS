# Controller 公共基础类（BaseHandler）
"""
在tornado中
- 每一个Url对应一个RequestHandler 可以理解为Controller
- RequestHandler 提供 post / get 等方法来处理http请求

本程序可以提供一个统一的基础类，用于处理一些公共业务,如登录态的处理或获得逻辑，供其他Handler继承使用
"""
import tornado.web

from app.models.user import UserRepository
from app.models.rbac import RBACRepository
from app.models.feature import FeatureRepository

# 不绑定功能菜单的后台子路由，继承父模块权限
ADMIN_ROUTE_PERMISSION_FALLBACK = {
    "/admin/users/create": "system.user",
    "/admin/users/batch-delete": "system.user",
    "/admin/roles/create": "system.role",
    "/admin/roles/permissions": "system.role",
    "/admin/permissions/create": "system.permission",
    "/admin/features/update": "system.feature",
    "/admin/watch-collect": "system.watch",
    "/admin/watch-records/batch-delete": "system.watch_record",
}


class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        username = self.get_secure_cookie("username")
        if not username:
            return None
        return username.decode("utf-8")

    def get_current_user_record(self):
        username = self.get_current_user()
        if not username:
            return None
        return UserRepository.get_user_by_username(username)

    def get_current_role_name(self) -> str:
        user = self.get_current_user_record()
        if not user:
            return "访客"
        role_code = UserRepository.get_role_code(user)
        if UserRepository.is_admin_role(role_code):
            return "管理员"
        if UserRepository.is_normal_user_role(role_code):
            return "普通用户"
        return "用户"

    def _get_admin_context(self):
        user = self.get_current_user_record()
        if not user:
            return None, "", []
        role_code = UserRepository.get_role_code(user)
        sidebar_features = FeatureRepository.list_sidebar_features(user["role_id"], role_code)
        return user, role_code, sidebar_features

    def render(self, template_name, **kwargs):
        kwargs.setdefault("portal_message", None)
        kwargs.setdefault("portal_message_type", None)
        kwargs.setdefault("active_nav", "")
        if "current_role_code" not in kwargs:
            try:
                user = self.get_current_user_record()
                kwargs["current_role_code"] = (
                    UserRepository.get_role_code(user) if user else ""
                )
            except Exception:
                kwargs["current_role_code"] = ""
        kwargs.setdefault("active_page", "")
        if "role_name" not in kwargs and self.get_current_user():
            kwargs.setdefault("role_name", self.get_current_role_name())
        if template_name.startswith("admin/") and "sidebar_features" not in kwargs:
            _, _, sidebar_features = self._get_admin_context()
            kwargs.setdefault("sidebar_features", sidebar_features)
        super().render(template_name, **kwargs)


class AdminBaseHandler(BaseHandler):
    def _resolve_required_permission(self, path: str) -> str | None:
        path = path.rstrip("/") or "/"
        perm = FeatureRepository.get_permission_code_for_route(path)
        if perm:
            return perm
        for prefix, code in ADMIN_ROUTE_PERMISSION_FALLBACK.items():
            if path == prefix or path.startswith(prefix + "/"):
                return code
        return None

    def prepare(self):
        if self.request.path.rstrip("/") == "/admin/login":
            return
        username = self.get_current_user()
        if not username:
            return
        user = UserRepository.get_user_by_username(username)
        if not user:
            return
        role_code = UserRepository.get_role_code(user)
        if not UserRepository.is_admin_role(role_code):
            self.redirect("/")
            raise tornado.web.Finish()

        if role_code == "super_admin":
            return

        path = self.request.path.split("?")[0].rstrip("/") or "/"
        required = self._resolve_required_permission(path)
        if required and not RBACRepository.role_has_permission(user["role_id"], role_code, required):
            self.set_status(403)
            self.render(
                "admin/forbidden.html",
                title="无访问权限",
                username=username,
                required_permission=required,
            )
            raise tornado.web.Finish()
