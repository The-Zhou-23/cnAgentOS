import json
import math

import tornado.web

from app.controllers.base import BaseHandler
from app.models.model_service import ModelServiceRepository
from app.models.rbac import RBACRepository
from app.models.user import UserRepository


class AdminLoginHandler(BaseHandler):
    def get(self):
        self.render("admin/login.html", title="管理员登录", error=None)

    def post(self):
        username = (self.get_body_argument("username", "") or "").strip()
        password = self.get_body_argument("password", "")

        if not username or not password:
            self.set_status(400)
            return self.render("admin/login.html", title="管理员登录", error="用户名或密码不能为空")

        if username != "admin" or password != "admin888":
            self.set_status(401)
            return self.render("admin/login.html", title="管理员登录", error="管理员账号或密码错误")

        self.set_secure_cookie("username", username)
        self.redirect("/admin/users")


class AdminLogoutHandler(BaseHandler):
    def post(self):
        self.clear_cookie("username")
        self.redirect("/admin/login")


class AdminUserListHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        page = max(1, int(self.get_argument("page", 1)))
        page_size = 20
        total, users = UserRepository.list_users(page=page, page_size=page_size)
        roles = RBACRepository.list_roles()
        total_pages = max(1, math.ceil(total / page_size))
        self.render(
            "admin/users.html",
            title="用户管理",
            username=self.current_user,
            users=users,
            roles=roles,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
            has_prev=page > 1,
            has_next=page < total_pages,
        )


class AdminUserCreateHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self):
        username = (self.get_body_argument("username", "") or "").strip()
        password = self.get_body_argument("password", "")
        role_id = self.get_body_argument("role_id", None)
        role_id = int(role_id) if role_id else None
        if not username or not password:
            return self.redirect("/admin/users")
        UserRepository.create_user(username, password, role_id)
        self.redirect("/admin/users")


class AdminUserUpdateHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self, user_id):
        user_id = int(user_id)
        username = (self.get_body_argument("username", "") or "").strip()
        password = self.get_body_argument("password", "")
        role_id = self.get_body_argument("role_id", None)
        role_id = int(role_id) if role_id else None
        user = UserRepository.get_user_by_id(user_id)
        if user and user["username"] == "admin":
            UserRepository.update_user_password_only(user_id, password)
        else:
            UserRepository.update_user(user_id, username, password or None, role_id)
        self.redirect("/admin/users")


class AdminUserDeleteHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self, user_id):
        user_id = int(user_id)
        user = UserRepository.get_user_by_id(user_id)
        if user and user["username"] == "admin":
            self.redirect("/admin/users")
            return
        UserRepository.delete_user(user_id)
        self.redirect("/admin/users")


class AdminUserBatchDeleteHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self):
        ids = self.get_body_arguments("user_ids")
        filtered_ids = []
        for raw_id in ids:
            user = UserRepository.get_user_by_id(int(raw_id))
            if user and user["username"] != "admin":
                filtered_ids.append(int(raw_id))
        UserRepository.batch_delete_users(filtered_ids)
        self.redirect("/admin/users")


class AdminRoleListHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        roles = RBACRepository.list_roles()
        permissions = RBACRepository.list_permissions()
        role_permissions = {role["id"]: RBACRepository.get_role_permissions(role["id"]) for role in roles}
        self.render(
            "admin/roles.html",
            title="角色管理",
            username=self.current_user,
            roles=roles,
            permissions=permissions,
            role_permissions=role_permissions,
        )


class AdminRoleCreateHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self):
        name = (self.get_body_argument("name", "") or "").strip()
        code = (self.get_body_argument("code", "") or "").strip()
        if name and code:
            RBACRepository.create_role(name, code)
        self.redirect("/admin/roles")


class AdminRoleUpdateHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self, role_id):
        name = (self.get_body_argument("name", "") or "").strip()
        code = (self.get_body_argument("code", "") or "").strip()
        RBACRepository.update_role(int(role_id), name, code)
        self.redirect("/admin/roles")


class AdminRoleDeleteHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self, role_id):
        RBACRepository.delete_role(int(role_id))
        self.redirect("/admin/roles")


class AdminRolePermissionUpdateHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self, role_id):
        permission_ids = [int(i) for i in self.get_body_arguments("permission_ids")]
        RBACRepository.set_role_permissions(int(role_id), permission_ids)
        self.redirect("/admin/roles")


class AdminPermissionListHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        permissions = RBACRepository.list_permissions()
        roles = RBACRepository.list_roles()
        self.render(
            "admin/permissions.html",
            title="权限管理",
            username=self.current_user,
            permissions=permissions,
            roles=roles,
        )


class AdminPermissionCreateHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self):
        menu_group = (self.get_body_argument("menu_group", "") or "").strip()
        name = (self.get_body_argument("name", "") or "").strip()
        code = (self.get_body_argument("code", "") or "").strip()
        sort_no = int(self.get_body_argument("sort_no", 0) or 0)
        if menu_group and name and code:
            RBACRepository.create_permission(menu_group, name, code, sort_no)
        self.redirect("/admin/permissions")


class AdminPermissionUpdateHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self, permission_id):
        menu_group = (self.get_body_argument("menu_group", "") or "").strip()
        name = (self.get_body_argument("name", "") or "").strip()
        code = (self.get_body_argument("code", "") or "").strip()
        sort_no = int(self.get_body_argument("sort_no", 0) or 0)
        RBACRepository.update_permission(int(permission_id), menu_group, name, code, sort_no)
        self.redirect("/admin/permissions")


class AdminPermissionDeleteHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self, permission_id):
        RBACRepository.delete_permission(int(permission_id))
        self.redirect("/admin/permissions")


class AdminModelListHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        page = max(1, int(self.get_argument("page", 1)))
        total, models = ModelServiceRepository.list_models(page=page, page_size=6)
        total_pages = max(1, math.ceil(total / 6))
        self.render(
            "admin/models.html",
            title="模型引擎",
            username=self.current_user,
            models=models,
            page=page,
            total=total,
            total_pages=total_pages,
            has_prev=page > 1,
            has_next=page < total_pages,
        )


class AdminModelCreateHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self):
        data = {k: self.get_body_argument(k, "") for k in ["name", "model_name", "base_url", "api_key", "conversation_prompt"]}
        data["is_system"] = 1 if self.get_body_argument("is_system", "0") == "1" else 0
        ModelServiceRepository.create_model(data)
        self.redirect("/admin/models")


class AdminModelUpdateHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self, model_id):
        data = {k: self.get_body_argument(k, "") for k in ["name", "model_name", "base_url", "api_key", "conversation_prompt"]}
        data["is_system"] = 1 if self.get_body_argument("is_system", "0") == "1" else 0
        ModelServiceRepository.update_model(int(model_id), data)
        self.redirect("/admin/models")


class AdminModelDeleteHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self, model_id):
        ModelServiceRepository.delete_model(int(model_id))
        self.redirect("/admin/models")


class AdminModelSystemHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self, model_id):
        ModelServiceRepository.set_system_model(int(model_id))
        self.redirect("/admin/models")
