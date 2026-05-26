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
from app.models.watchtower import WatchtowerRepository


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
        password = (self.get_body_argument("password", "") or "").strip()
        if password:
            UserRepository.update_user_password_only(int(user_id), password)
        self.redirect("/admin/users")

class AdminUserBatchDeleteHandler(AdminBaseHandler):
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

class AdminWatchSourceListHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        sources = WatchtowerRepository.list_sources()
        if not sources:
            WatchtowerRepository.create_source({"name": "百度新闻", "source_code": "baidu_news", "entry_urls": ["https://www.baidu.com/s?ie=utf-8&bsst=1&rsv_dl=news_t_sk&tn=news&cl=2&medium=0&rtt=1&wd={关键词}", "https://www.baidu.com/s?ie=utf-8&bsst=1&rsv_dl=news_b_pn&tn=news&cl=2&medium=0&rtt=1&wd={关键词}&pn={分页步进}"], "headers": {}, "keywords_label": "关键词", "page_param_name": "pn", "page_step": 10, "collect_limit": 10, "is_enabled": 1, "note": "百度新闻专用采集源，仅需填写关键词与起始页数"})
            sources = WatchtowerRepository.list_sources()
        self.render("admin/watch_sources.html", title="百度新闻采集", username=self.current_user, sources=sources)

class AdminWatchSourceCreateHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        data = {"name": "百度新闻", "source_code": "baidu_news", "entry_urls": ["https://www.baidu.com/s?ie=utf-8&bsst=1&rsv_dl=news_t_sk&tn=news&cl=2&medium=0&rtt=1&wd={关键词}", "https://www.baidu.com/s?ie=utf-8&bsst=1&rsv_dl=news_b_pn&tn=news&cl=2&medium=0&rtt=1&wd={关键词}&pn={分页步进}"], "headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7", "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6"}, "keywords_label": "关键词", "page_param_name": "pn", "page_step": 10, "collect_limit": 10, "is_enabled": 1, "note": "百度新闻专用采集源，仅需填写关键词与起始页数"}
        exists = any(source["source_code"] == "baidu_news" for source in WatchtowerRepository.list_sources())
        if not exists:
            WatchtowerRepository.create_source(data)
        self.redirect("/admin/watch-sources")

class AdminWatchSourceUpdateHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self, source_id):
        source = WatchtowerRepository.get_source(int(source_id))
        if source and source["source_code"] == "baidu_news":
            data = {"name": "百度新闻", "source_code": "baidu_news", "entry_urls": json.loads(source["entry_urls_json"] or "[]"), "headers": json.loads(source["headers_json"] or "{}"), "keywords_label": "关键词", "page_param_name": "pn", "page_step": 10, "collect_limit": 10, "is_enabled": 1 if self.get_body_argument("is_enabled", "1") == "1" else 0, "note": "百度新闻专用采集源，仅需填写关键词与起始页数"}
            WatchtowerRepository.update_source(int(source_id), data)
        self.redirect("/admin/watch-sources")

class AdminWatchSourceDeleteHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self, source_id):
        WatchtowerRepository.delete_source(int(source_id))
        self.redirect("/admin/watch-sources")

class AdminWatchCollectHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        source_id = int(self.get_body_argument("source_id")); keyword = (self.get_body_argument("keyword", "") or "").strip(); start_page = int(self.get_body_argument("start_page", 0) or 0); item_count = int(self.get_body_argument("item_count", 1) or 1)
        records = WatchtowerRepository.collect(source_id, keyword, start_page, item_count)
        WatchtowerRepository.save_records(records)
        self.redirect("/admin/watch-records")

class AdminWatchRecordListHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        page = max(1, int(self.get_argument("page", 1)))
        total, records = WatchtowerRepository.list_records(page=page, page_size=20)
        total_pages = max(1, math.ceil(total / 20))
        sources = WatchtowerRepository.list_sources()
        start_no = total - (page - 1) * 20
        self.render("admin/watch_records.html", title="数据仓库", username=self.current_user, records=records, sources=sources, page=page, total=total, total_pages=total_pages, has_prev=page > 1, has_next=page < total_pages, start_no=start_no)

class AdminWatchRecordDeleteHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self, record_id):
        WatchtowerRepository.delete_record(int(record_id)); self.redirect("/admin/watch-records")

class AdminWatchRecordBatchDeleteHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        ids = [int(i) for i in self.get_body_arguments("record_ids")]; WatchtowerRepository.batch_delete_records(ids); self.redirect("/admin/watch-records")

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
