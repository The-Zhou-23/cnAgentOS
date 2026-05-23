# 程序的主入口
import os
import tornado.ioloop
import tornado.web
from tornado.httpserver import HTTPServer

from app.controllers.auth import LoginHandler, LogoutHandler
from app.controllers.home import IndexHandler
from app.controllers.admin import (
    AdminLoginHandler,
    AdminLogoutHandler,
    AdminUserListHandler,
    AdminUserCreateHandler,
    AdminUserUpdateHandler,
    AdminUserDeleteHandler,
    AdminUserBatchDeleteHandler,
)
from app.models.db import init_db


def make_app():
    base_url = os.path.dirname(os.path.abspath(__file__))
    settings = dict(
        template_path=os.path.join(base_url, "app", "templates"),
        static_path=os.path.join(base_url, "app", "static"),
        cookie_secret="demo-cookie-secret-change-me",
        login_url="/admin/login",
        xsrf_cookies=True,
        debug=True,
        autoreload=True,
    )
    return tornado.web.Application(
        [
            (r"/", IndexHandler),
            (r"/auth/login", LoginHandler),
            (r"/auth/logout", LogoutHandler),
            (r"/admin/login", AdminLoginHandler),
            (r"/admin/logout", AdminLogoutHandler),
            (r"/admin/users", AdminUserListHandler),
            (r"/admin/users/create", AdminUserCreateHandler),
            (r"/admin/users/update/(\d+)", AdminUserUpdateHandler),
            (r"/admin/users/delete/(\d+)", AdminUserDeleteHandler),
            (r"/admin/users/batch-delete", AdminUserBatchDeleteHandler),
        ],
        **settings,
    )


if __name__ == "__main__":
    init_db()
    app = make_app()
    server = HTTPServer(app)
    server.bind(10086)
    server.start()
    print("====== Server 启动成功 ======== 端口：10086 ======")
    tornado.ioloop.IOLoop.current().start()
