# 程序的主入口
import os
import tornado.ioloop
import tornado.web
from tornado.httpserver import HTTPServer

from app.controllers.admin import (
    AdminAPIInterfaceCreateHandler,
    AdminAPIInterfaceDeleteHandler,
    AdminAPIInterfaceListHandler,
    AdminAPIInterfaceUpdateHandler,
    AdminDigitalEmployeeChatHandler,
    AdminDigitalEmployeeCreateHandler,
    AdminDigitalEmployeeDeleteHandler,
    AdminDigitalEmployeeListHandler,
    AdminDigitalEmployeeUpdateHandler,
    AdminLoginHandler,
    AdminLogoutHandler,
    AdminModelCreateHandler,
    AdminModelDeleteHandler,
    AdminModelListHandler,
    AdminModelSystemHandler,
    AdminModelTestHandler,
    AdminModelUpdateHandler,
    AdminPermissionCreateHandler,
    AdminPermissionDeleteHandler,
    AdminPermissionListHandler,
    AdminPermissionUpdateHandler,
    AdminRoleCreateHandler,
    AdminRoleDeleteHandler,
    AdminRoleListHandler,
    AdminRolePermissionUpdateHandler,
    AdminRoleUpdateHandler,
    AdminUserBatchDeleteHandler,
    AdminUserCreateHandler,
    AdminUserDeleteHandler,
    AdminUserListHandler,
    AdminUserResetPasswordHandler,
    AdminUserUpdateHandler,
    AdminWatchCollectHandler,
    AdminWatchRecordBatchDeleteHandler,
    AdminWatchRecordDeleteHandler,
    AdminWatchRecordListHandler,
    AdminWatchSourceCreateHandler,
    AdminWatchSourceDeleteHandler,
    AdminWatchSourceListHandler,
    AdminWatchSourceUpdateHandler,
)
from app.controllers.auth import LoginHandler, LogoutHandler
from app.controllers.home import IndexHandler
from app.models.db import init_db
from app.models.model_service import ModelServiceRepository
from app.models.digital_employee import DigitalEmployeeRepository


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
            (r"/admin/users/reset-password/(\d+)", AdminUserResetPasswordHandler),
            (r"/admin/users/batch-delete", AdminUserBatchDeleteHandler),
            (r"/admin/roles", AdminRoleListHandler),
            (r"/admin/roles/create", AdminRoleCreateHandler),
            (r"/admin/roles/update/(\d+)", AdminRoleUpdateHandler),
            (r"/admin/roles/delete/(\d+)", AdminRoleDeleteHandler),
            (r"/admin/roles/permissions/(\d+)", AdminRolePermissionUpdateHandler),
            (r"/admin/permissions", AdminPermissionListHandler),
            (r"/admin/permissions/create", AdminPermissionCreateHandler),
            (r"/admin/permissions/update/(\d+)", AdminPermissionUpdateHandler),
            (r"/admin/permissions/delete/(\d+)", AdminPermissionDeleteHandler),
            (r"/admin/api-interfaces", AdminAPIInterfaceListHandler),
            (r"/admin/api-interfaces/create", AdminAPIInterfaceCreateHandler),
            (r"/admin/api-interfaces/update/(\d+)", AdminAPIInterfaceUpdateHandler),
            (r"/admin/api-interfaces/delete/(\d+)", AdminAPIInterfaceDeleteHandler),
            (r"/admin/digital-employees", AdminDigitalEmployeeListHandler),
            (r"/admin/digital-employees/create", AdminDigitalEmployeeCreateHandler),
            (r"/admin/digital-employees/update/(\d+)", AdminDigitalEmployeeUpdateHandler),
            (r"/admin/digital-employees/delete/(\d+)", AdminDigitalEmployeeDeleteHandler),
            (r"/admin/digital-employees/chat", AdminDigitalEmployeeChatHandler),
            (r"/admin/models", AdminModelListHandler),
            (r"/admin/models/create", AdminModelCreateHandler),
            (r"/admin/models/update/(\d+)", AdminModelUpdateHandler),
            (r"/admin/models/delete/(\d+)", AdminModelDeleteHandler),
            (r"/admin/models/system/(\d+)", AdminModelSystemHandler),
            (r"/admin/models/test", AdminModelTestHandler),
            (r"/admin/watch-sources", AdminWatchSourceListHandler),
            (r"/admin/watch-sources/create", AdminWatchSourceCreateHandler),
            (r"/admin/watch-sources/update/(\d+)", AdminWatchSourceUpdateHandler),
            (r"/admin/watch-sources/delete/(\d+)", AdminWatchSourceDeleteHandler),
            (r"/admin/watch-collect", AdminWatchCollectHandler),
            (r"/admin/watch-records", AdminWatchRecordListHandler),
            (r"/admin/watch-records/delete/(\d+)", AdminWatchRecordDeleteHandler),
            (r"/admin/watch-records/batch-delete", AdminWatchRecordBatchDeleteHandler),
        ],
        **settings,
    )


if __name__ == "__main__":
    init_db()
    ModelServiceRepository.ensure_default_model()
    DigitalEmployeeRepository.ensure_defaults()
    app = make_app()
    server = HTTPServer(app)
    server.bind(10087)
    server.start()
    print("====== Server 启动成功 ======== 端口：10087 ======")
    tornado.ioloop.IOLoop.current().start()
