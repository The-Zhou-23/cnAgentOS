"""成员 D 独占：用户侧数字员工大厅 + 对话 SSE 接口。

仅普通用户（normal_user）可访问，管理员请使用 /admin/digital-employees。
"""

import json

import tornado.web

from app.controllers.base import BaseHandler
from app.models.digital_employee import DigitalEmployeeRepository
from app.models.user import UserRepository


class _PortalBaseHandler(BaseHandler):
    """用户门户基类：拦截未登录与非 normal_user 用户。"""

    def prepare(self):
        username = self.get_current_user()
        if not username:
            return
        user = UserRepository.get_user_by_username(username)
        role_code = UserRepository.get_role_code(user)
        # 管理员强制走后台
        if UserRepository.is_admin_role(role_code):
            self.redirect("/admin/digital-employees")
            self.finish()


class PortalDigitalEmployeeListHandler(_PortalBaseHandler):
    """用户侧：数字员工大厅。"""

    @tornado.web.authenticated
    def get(self):
        employees = [
            e for e in DigitalEmployeeRepository.list_employees() if e["is_enabled"]
        ]
        self.render(
            "portal/digital_employee.html",
            title="数字员工",
            username=self.current_user,
            role_name="普通用户",
            employees=employees,
        )


class PortalDigitalEmployeeChatHandler(_PortalBaseHandler):
    """用户侧 SSE 对话接口：与管理端共用 chat_stream，支持多轮 history。"""

    @tornado.web.authenticated
    def post(self):
        message = (self.get_body_argument("message", "") or "").strip()
        history_raw = self.get_body_argument("history", "") or ""
        history = []
        if history_raw:
            try:
                parsed = json.loads(history_raw)
                if isinstance(parsed, list):
                    history = parsed
            except Exception:
                history = []
        self.set_header("Content-Type", "text/event-stream; charset=utf-8")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("Connection", "keep-alive")
        self.flush()
        for chunk in DigitalEmployeeRepository.chat_stream(message, history=history):
            self.write(
                f"data: {json.dumps({'message': chunk}, ensure_ascii=False)}\n\n"
            )
            self.flush()
        self.finish()
