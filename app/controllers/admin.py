import math

import tornado.web

from app.controllers.base import BaseHandler
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
        username = (self.get_body_argument("username", "") or "").strip()
        password = self.get_body_argument("password", "")
        role_id = self.get_body_argument("role_id", None)
        role_id = int(role_id) if role_id else None
        UserRepository.update_user(int(user_id), username, password or None, role_id)
        self.redirect("/admin/users")


class AdminUserDeleteHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self, user_id):
        UserRepository.delete_user(int(user_id))
        self.redirect("/admin/users")


class AdminUserBatchDeleteHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self):
        ids = self.get_body_arguments("user_ids")
        UserRepository.batch_delete_users([int(i) for i in ids])
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
