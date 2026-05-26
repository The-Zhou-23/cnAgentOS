# 程序的主入口
import os
import tornado.ioloop
import tornado.web
from tornado.httpserver import HTTPServer

from app.controllers.admin import (
    AdminFeatureListHandler,
    AdminFeatureUpdateHandler,
    AdminLoginHandler,
    AdminLogoutHandler,
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
)
from app.controllers.admin_watch import (
    AdminWatchCollectHandler,
    AdminWatchRecordBatchDeleteHandler,
    AdminWatchRecordDeleteHandler,
    AdminWatchRecordListHandler,
    AdminWatchSourceCreateHandler,
    AdminWatchSourceDeleteHandler,
    AdminWatchSourceListHandler,
    AdminWatchSourceUpdateHandler,
)
# 成员 D 独占：模型 + 接口 + 数字员工
from app.controllers.admin_ai import (
    AdminAPIInterfaceCreateHandler,
    AdminAPIInterfaceDeleteHandler,
    AdminAPIInterfaceListHandler,
    AdminAPIInterfaceTestHandler,
    AdminAPIInterfaceUpdateHandler,
    AdminDigitalEmployeeChatHandler,
    AdminDigitalEmployeeCreateHandler,
    AdminDigitalEmployeeDeleteHandler,
    AdminDigitalEmployeeListHandler,
    AdminDigitalEmployeeUpdateHandler,
    AdminModelConnectivityHandler,
    AdminModelCreateHandler,
    AdminModelDeleteHandler,
    AdminModelListHandler,
    AdminModelSystemHandler,
    AdminModelTestHandler,
    AdminModelUpdateHandler,
)
from app.controllers.portal_digital import (
    PortalDigitalEmployeeChatHandler,
    PortalDigitalEmployeeListHandler,
)
from app.controllers.auth import LoginHandler, LogoutHandler, RegisterHandler
from app.controllers.home import IndexHandler
from app.controllers._temp_a_portal_stubs import (
    TempPortalDigitalEmployeeHandler,
    TempPortalQueryHandler,
)
from app.controllers.portal_watch import PortalWatchListHandler, PortalWatchDetailHandler
from app.models.db import get_connection, init_db
from app.models.model_service import ModelServiceRepository
from app.models.digital_employee import DigitalEmployeeRepository
from app.models.user import UserRepository


def ensure_demo_users():
    with get_connection() as conn:
        # 创建默认管理员账号
        admin_role = conn.execute("select id from roles where code = 'super_admin'").fetchone()
        if admin_role and not UserRepository.get_user_by_username("admin"):
            UserRepository.create_user("admin", "123456", admin_role["id"])
        
        # 创建默认普通用户
        user_role = conn.execute("select id from roles where code = 'normal_user'").fetchone()
        if user_role and not UserRepository.get_user_by_username("user"):
            UserRepository.create_user("user", "123456", user_role["id"])


def make_app():
    base_url = os.path.dirname(os.path.abspath(__file__))
    settings = dict(
        template_path=os.path.join(base_url, "app", "templates"),
        static_path=os.path.join(base_url, "app", "static"),
        cookie_secret="demo-cookie-secret-change-me",
        login_url="/auth/login",
        xsrf_cookies=True,
        debug=True,
        autoreload=True,
    )
    return tornado.web.Application(
        [
            (r"/", IndexHandler),
            (r"/auth/login", LoginHandler),
            (r"/auth/register", RegisterHandler),
            (r"/auth/logout", LogoutHandler),
            # 【临时路由 - 成员 A】待 D/E 实现正式页面后删除
            (r"/portal/query", TempPortalQueryHandler),
            # 成员 C：智能瞭望用户侧路由
            (r"/portal/watch", PortalWatchListHandler),
            (r"/portal/watch/(\d+)", PortalWatchDetailHandler),
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
            (r"/admin/api-interfaces/test/(\d+)", AdminAPIInterfaceTestHandler),
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
            (r"/admin/models/connectivity/(\d+)", AdminModelConnectivityHandler),
            # 用户侧数字员工大厅（成员 D）
            (r"/portal/digital-employee", PortalDigitalEmployeeListHandler),
            (r"/portal/digital-employee/chat", PortalDigitalEmployeeChatHandler),
            (r"/admin/watch-sources", AdminWatchSourceListHandler),
            (r"/admin/watch-sources/create", AdminWatchSourceCreateHandler),
            (r"/admin/watch-sources/update/(\d+)", AdminWatchSourceUpdateHandler),
            (r"/admin/watch-sources/delete/(\d+)", AdminWatchSourceDeleteHandler),
            (r"/admin/watch-collect", AdminWatchCollectHandler),
            (r"/admin/watch-records", AdminWatchRecordListHandler),
            (r"/admin/watch-records/delete/(\d+)", AdminWatchRecordDeleteHandler),
            (r"/admin/watch-records/batch-delete", AdminWatchRecordBatchDeleteHandler),
            (r"/admin/features", AdminFeatureListHandler),
            (r"/admin/features/update/(\d+)", AdminFeatureUpdateHandler),
        ],
        **settings,
    )


if __name__ == "__main__":
    init_db()
    ensure_demo_users()
    ModelServiceRepository.ensure_default_model()
    DigitalEmployeeRepository.ensure_defaults()
    app = make_app()
    server = HTTPServer(app)
    server.bind(10087)
    server.start()
    print("====== Server 启动成功 ======== 端口：10087 ======")
    tornado.ioloop.IOLoop.current().start()
