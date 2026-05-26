import json
import math

import tornado.web

from app.controllers.base import AdminBaseHandler, BaseHandler
from app.models.api_interface import APIInterfaceRepository
from app.models.digital_employee import DigitalEmployeeRepository
from app.models.feature import FeatureRepository
from app.models.model_service import ModelServiceRepository
from app.models.rbac import RBACRepository
from app.models.user import UserRepository


class AdminLoginHandler(BaseHandler):
    def get(self):
        self.redirect("/auth/login?type=admin")

    def post(self):
        self.redirect("/auth/login?type=admin")


class AdminLogoutHandler(BaseHandler):
    def post(self):
        self.clear_cookie("username")
        self.redirect("/auth/login?type=admin")


class AdminUserListHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        page = max(1, int(self.get_argument("page", 1)))
        page_size = 20
        search_username = (self.get_argument("username", "") or "").strip()
        search_role_name = (self.get_argument("role_name", "") or "").strip()
        total, users = UserRepository.list_users(page=page, page_size=page_size, username=search_username, role_name=search_role_name)
        roles = RBACRepository.list_roles()
        total_pages = max(1, math.ceil(total / page_size))
        current_user_record = UserRepository.get_user_by_username(self.current_user)
        current_role_code = UserRepository.get_role_code(current_user_record)
        self.render("admin/users.html", title="用户管理", username=self.current_user, users=users, roles=roles, page=page, page_size=page_size, total=total, total_pages=total_pages, has_prev=page > 1, has_next=page < total_pages, current_role_code=current_role_code, current_user_id=current_user_record["id"] if current_user_record else None, search_username=search_username, search_role_name=search_role_name)

class AdminUserCreateHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        username = (self.get_body_argument("username", "") or "").strip()
        password = self.get_body_argument("password", "")
        role_id = self.get_body_argument("role_id", None)
        role_id = int(role_id) if role_id else None
        if username and password:
            UserRepository.create_user(username, password, role_id)
        self.redirect("/admin/users")

class AdminUserUpdateHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self, user_id):
        user_id = int(user_id)
        username = (self.get_body_argument("username", "") or "").strip()
        password = self.get_body_argument("password", "")
        role_id = self.get_body_argument("role_id", None)
        role_id = int(role_id) if role_id else None
        is_disabled_raw = self.get_body_argument("is_disabled", "")
        user = UserRepository.get_user_by_id(user_id)
        current_user_record = UserRepository.get_user_by_username(self.current_user)
        current_role_code = UserRepository.get_role_code(current_user_record)
        target_user_data = {"id": user_id, "role_code": user["role_code"] if user else None}
        perms = UserRepository.can_manage_user(current_role_code, target_user_data, current_user_record["id"])
        if user and user["username"] == "admin":
            UserRepository.update_user_password_only(user_id, password)
        else:
            if perms["can_edit"]:
                UserRepository.update_user(user_id, username, password or None, role_id)
            if is_disabled_raw in ("0", "1") and perms["can_disable"]:
                UserRepository.disable_user(user_id, int(is_disabled_raw))
        self.redirect("/admin/users")

class AdminUserDeleteHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self, user_id):
        user = UserRepository.get_user_by_id(int(user_id))
        current_user_record = UserRepository.get_user_by_username(self.current_user)
        current_role_code = UserRepository.get_role_code(current_user_record)
        target_user_data = {"id": int(user_id), "role_code": user["role_code"] if user else None}
        perms = UserRepository.can_manage_user(current_role_code, target_user_data, current_user_record["id"])
        if perms["can_delete"] and not (user and user["username"] == "admin"):
            UserRepository.delete_user(int(user_id))
        self.redirect("/admin/users")

class AdminUserResetPasswordHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self, user_id):
        user_id = int(user_id)
        password = (self.get_body_argument("password", "") or "").strip()
        if not password:
            self.redirect("/admin/users")
            return
        user = UserRepository.get_user_by_id(user_id)
        if not user:
            self.redirect("/admin/users")
            return
        current_user_record = UserRepository.get_user_by_username(self.current_user)
        current_role_code = UserRepository.get_role_code(current_user_record)
        target_data = {"id": user_id, "role_code": user["role_code"] if user else None}
        perms = UserRepository.can_manage_user(current_role_code, target_data, current_user_record["id"])
        if perms["can_edit"] or (user["username"] == "admin" and current_role_code == "super_admin"):
            UserRepository.update_user_password_only(user_id, password)
        self.redirect("/admin/users")

class AdminUserBatchDeleteHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        ids = self.get_body_arguments("user_ids")
        current_user_record = UserRepository.get_user_by_username(self.current_user)
        current_role_code = UserRepository.get_role_code(current_user_record)
        filtered_ids = []
        for raw_id in ids:
            user = UserRepository.get_user_by_id(int(raw_id))
            if not user:
                continue
            target_data = {"id": user["id"], "role_code": user["role_code"] if user else None}
            perms = UserRepository.can_manage_user(current_role_code, target_data, current_user_record["id"])
            if perms["can_delete"] and user["username"] != "admin":
                filtered_ids.append(int(raw_id))
        UserRepository.batch_delete_users(filtered_ids)
        self.redirect("/admin/users")

class AdminRoleListHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        roles = RBACRepository.list_roles()
        permissions = RBACRepository.list_permissions()
        role_permissions = {role["id"]: RBACRepository.get_role_permissions(role["id"]) for role in roles}
        current_user_record = UserRepository.get_user_by_username(self.current_user)
        current_role_code = UserRepository.get_role_code(current_user_record)
        self.render("admin/roles.html", title="角色管理", username=self.current_user, roles=roles, permissions=permissions, role_permissions=role_permissions, current_role_code=current_role_code)

class AdminRoleCreateHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        current_user_record = UserRepository.get_user_by_username(self.current_user)
        current_role_code = UserRepository.get_role_code(current_user_record)
        if current_role_code != "super_admin":
            self.redirect("/admin/roles")
            return
        name = (self.get_body_argument("name", "") or "").strip()
        code = (self.get_body_argument("code", "") or "").strip()
        if name and code:
            RBACRepository.create_role(name, code)
        self.redirect("/admin/roles")

class AdminRoleUpdateHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self, role_id):
        current_user_record = UserRepository.get_user_by_username(self.current_user)
        current_role_code = UserRepository.get_role_code(current_user_record)
        if current_role_code != "super_admin":
            self.redirect("/admin/roles")
            return
        RBACRepository.update_role(int(role_id), (self.get_body_argument("name", "") or "").strip(), (self.get_body_argument("code", "") or "").strip())
        self.redirect("/admin/roles")

class AdminRoleDeleteHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self, role_id):
        current_user_record = UserRepository.get_user_by_username(self.current_user)
        current_role_code = UserRepository.get_role_code(current_user_record)
        if current_role_code != "super_admin":
            self.redirect("/admin/roles")
            return
        RBACRepository.delete_role(int(role_id))
        self.redirect("/admin/roles")

class AdminRolePermissionUpdateHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self, role_id):
        current_user_record = UserRepository.get_user_by_username(self.current_user)
        current_role_code = UserRepository.get_role_code(current_user_record)
        if current_role_code != "super_admin":
            self.redirect("/admin/roles")
            return
        permission_ids = [int(i) for i in self.get_body_arguments("permission_ids")]
        RBACRepository.set_role_permissions(int(role_id), permission_ids)
        self.redirect("/admin/roles")

class AdminPermissionListHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        permissions = RBACRepository.list_permissions()
        roles = RBACRepository.list_roles()
        current_user_record = UserRepository.get_user_by_username(self.current_user)
        current_role_code = UserRepository.get_role_code(current_user_record)
        self.render("admin/permissions.html", title="权限管理", username=self.current_user, permissions=permissions, roles=roles, current_role_code=current_role_code)

class AdminPermissionCreateHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        current_user_record = UserRepository.get_user_by_username(self.current_user)
        current_role_code = UserRepository.get_role_code(current_user_record)
        if current_role_code != "super_admin":
            self.redirect("/admin/permissions")
            return
        menu_group = (self.get_body_argument("menu_group", "") or "").strip()
        name = (self.get_body_argument("name", "") or "").strip()
        code = (self.get_body_argument("code", "") or "").strip()
        sort_no = int(self.get_body_argument("sort_no", 0) or 0)
        if menu_group and name and code:
            RBACRepository.create_permission(menu_group, name, code, sort_no)
        self.redirect("/admin/permissions")

class AdminPermissionUpdateHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self, permission_id):
        current_user_record = UserRepository.get_user_by_username(self.current_user)
        current_role_code = UserRepository.get_role_code(current_user_record)
        if current_role_code != "super_admin":
            self.redirect("/admin/permissions")
            return
        RBACRepository.update_permission(int(permission_id), (self.get_body_argument("menu_group", "") or "").strip(), (self.get_body_argument("name", "") or "").strip(), (self.get_body_argument("code", "") or "").strip(), int(self.get_body_argument("sort_no", 0) or 0))
        self.redirect("/admin/permissions")

class AdminPermissionDeleteHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self, permission_id):
        current_user_record = UserRepository.get_user_by_username(self.current_user)
        current_role_code = UserRepository.get_role_code(current_user_record)
        if current_role_code != "super_admin":
            self.redirect("/admin/permissions")
            return
        RBACRepository.delete_permission(int(permission_id))
        self.redirect("/admin/permissions")

# 接口管理 / 数字员工 / 模型引擎 相关 Handler 已迁出至
# app/controllers/admin_ai.py（成员 D 独占），本文件不再保留。

class AdminFeatureListHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        features = FeatureRepository.list_features()
        current_user_record = UserRepository.get_user_by_username(self.current_user)
        current_role_code = UserRepository.get_role_code(current_user_record)
        self.render("admin/features.html", title="功能管理", username=self.current_user, features=features, current_role_code=current_role_code)

class AdminFeatureUpdateHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self, feature_id):
        data = {
            "name": (self.get_body_argument("name", "") or "").strip(),
            "route_path": (self.get_body_argument("route_path", "") or "").strip(),
            "sort_no": int(self.get_body_argument("sort_no", 0) or 0),
            "is_enabled": int(self.get_body_argument("is_enabled", "1") or 1),
        }
        FeatureRepository.update_feature(int(feature_id), data)
        self.redirect("/admin/features")
