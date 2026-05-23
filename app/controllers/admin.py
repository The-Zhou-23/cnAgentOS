import math

import tornado.web

from app.controllers.base import BaseHandler
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
        page = int(self.get_argument("page", 1))
        page_size = 20
        total, users = UserRepository.list_users(page=page, page_size=page_size)
        total_pages = max(1, math.ceil(total / page_size))
        self.render(
            "admin/users.html",
            title="用户管理",
            username=self.current_user,
            users=users,
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
        if not username or not password:
            return self.redirect("/admin/users")
        UserRepository.create_user(username, password)
        self.redirect("/admin/users")


class AdminUserUpdateHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self, user_id):
        username = (self.get_body_argument("username", "") or "").strip()
        password = self.get_body_argument("password", "")
        UserRepository.update_user(int(user_id), username, password)
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
