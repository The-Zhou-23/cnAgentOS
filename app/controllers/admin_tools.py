"""AI 工具集管理 + 数字员工绑定（Task3）。"""

import json

import tornado.web

from app.controllers.base import AdminBaseHandler
from app.models.ai_tool import AIToolRepository
from app.models.digital_employee import DigitalEmployeeRepository


class AdminToolsHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        tools = AIToolRepository.list_tools()
        employees = DigitalEmployeeRepository.list_employees()
        bindings = {}
        for emp in employees:
            bindings[emp["id"]] = AIToolRepository.get_employee_tool_ids(emp["id"])
        self.render(
            "admin/tools.html",
            title="工具集管理",
            username=self.current_user,
            active_page="tools",
            tools=tools,
            employees=employees,
            bindings=bindings,
        )

    @tornado.web.authenticated
    def post(self):
        action = self.get_body_argument("action", "")
        if action == "create_tool":
            AIToolRepository.create_tool(
                {
                    "name": self.get_body_argument("name", ""),
                    "tool_type": self.get_body_argument("tool_type", "http"),
                    "description": self.get_body_argument("description", ""),
                    "config_json": self.get_body_argument("config_json", "{}"),
                    "is_enabled": self.get_body_argument("is_enabled", "1"),
                }
            )
        elif action == "delete_tool":
            AIToolRepository.delete_tool(int(self.get_body_argument("tool_id", "0") or 0))
        elif action == "bind":
            employee_id = int(self.get_body_argument("employee_id", "0") or 0)
            tool_ids = [int(x) for x in self.get_body_arguments("tool_ids")]
            AIToolRepository.bind_tools_to_employee(employee_id, tool_ids)
        self.redirect("/admin/tools")
