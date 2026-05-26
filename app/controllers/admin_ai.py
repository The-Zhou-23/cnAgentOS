"""成员 D 独占：模型引擎 + 接口管理 + 数字员工（管理侧 Handler 集合）。

从原 `app/controllers/admin.py` 中迁出 D 负责的 Handler，集中放在此文件。
不要在此文件中混入 B/C/E 的 Handler；其他成员若需调用本文件函数，请走
`ModelServiceRepository`、`APIInterfaceRepository`、`DigitalEmployeeRepository` 等仓储。
"""

import json

import tornado.web

from app.controllers.base import AdminBaseHandler, BaseHandler
from app.models.api_interface import APIInterfaceRepository
from app.models.digital_employee import DigitalEmployeeRepository
from app.models.model_service import ModelServiceRepository
from app.models.watchtower import WatchtowerRepository


# ============================================================
# 接口管理（REQ-F-012）
# ============================================================
class AdminAPIInterfaceListHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        interfaces = APIInterfaceRepository.list_interfaces()
        self.render(
            "admin/api_interfaces.html",
            title="接口管理",
            username=self.current_user,
            interfaces=interfaces,
        )


class AdminAPIInterfaceCreateHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        data = {
            k: (self.get_body_argument(k, "") or "").strip()
            for k in [
                "name",
                "api_url",
                "response_format",
                "request_method",
                "request_example",
                "qps_limit",
                "note",
            ]
        }
        if data["name"] and data["api_url"]:
            APIInterfaceRepository.create_interface(data)
        self.redirect("/admin/api-interfaces")


class AdminAPIInterfaceUpdateHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self, interface_id):
        data = {
            k: (self.get_body_argument(k, "") or "").strip()
            for k in [
                "name",
                "api_url",
                "response_format",
                "request_method",
                "request_example",
                "qps_limit",
                "note",
            ]
        }
        if data["name"] and data["api_url"]:
            APIInterfaceRepository.update_interface(int(interface_id), data)
        self.redirect("/admin/api-interfaces")


class AdminAPIInterfaceDeleteHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self, interface_id):
        APIInterfaceRepository.delete_interface(int(interface_id))
        self.redirect("/admin/api-interfaces")


class AdminAPIInterfaceTestHandler(AdminBaseHandler):
    """REQ-F-012：接口连通性测试，返回 JSON。"""

    @tornado.web.authenticated
    def post(self, interface_id):
        result = APIInterfaceRepository.test_interface(int(interface_id))
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.write(json.dumps(result, ensure_ascii=False))


# ============================================================
# 数字员工（REQ-F-007）
# ============================================================
class AdminDigitalEmployeeListHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        employees = DigitalEmployeeRepository.list_employees()
        models = ModelServiceRepository.list_all_models()
        interfaces = APIInterfaceRepository.list_interfaces()
        self.render(
            "admin/digital_employees.html",
            title="数字员工管理",
            username=self.current_user,
            employees=employees,
            models=models,
            interfaces=interfaces,
        )


def _read_employee_form(handler) -> dict:
    data = {
        "alias": (handler.get_body_argument("alias", "") or "").strip(),
        "description": (handler.get_body_argument("description", "") or "").strip(),
        "employee_type": (handler.get_body_argument("employee_type", "model") or "model").strip(),
        "model_service_id": handler.get_body_argument("model_service_id", "") or None,
        "api_interface_id": handler.get_body_argument("api_interface_id", "") or None,
        "prompt": (handler.get_body_argument("prompt", "") or "").strip(),
        "config_json": (handler.get_body_argument("config_json", "{}") or "{}").strip(),
        "is_enabled": int(handler.get_body_argument("is_enabled", 1) or 1),
    }
    if data["model_service_id"]:
        data["model_service_id"] = int(data["model_service_id"])
    if data["api_interface_id"]:
        data["api_interface_id"] = int(data["api_interface_id"])
    return data


class AdminDigitalEmployeeCreateHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        data = _read_employee_form(self)
        if data["alias"]:
            DigitalEmployeeRepository.create_employee(data)
        self.redirect("/admin/digital-employees")


class AdminDigitalEmployeeUpdateHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self, employee_id):
        data = _read_employee_form(self)
        DigitalEmployeeRepository.update_employee(int(employee_id), data)
        self.redirect("/admin/digital-employees")


class AdminDigitalEmployeeDeleteHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self, employee_id):
        DigitalEmployeeRepository.delete_employee(int(employee_id))
        self.redirect("/admin/digital-employees")


class AdminDigitalEmployeeChatHandler(AdminBaseHandler):
    """管理端调试入口：与用户端共用 DigitalEmployeeRepository.chat_stream。"""

    @tornado.web.authenticated
    def post(self):
        message = (self.get_body_argument("message", "") or "").strip()
        self.set_header("Content-Type", "text/event-stream; charset=utf-8")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("Connection", "keep-alive")
        self.flush()
        for chunk in DigitalEmployeeRepository.chat_stream(message):
            self.write(
                f"data: {json.dumps({'message': chunk}, ensure_ascii=False)}\n\n"
            )
            self.flush()
        self.finish()


# ============================================================
# 模型引擎（REQ-F-008）
# ============================================================
class AdminModelListHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        models = ModelServiceRepository.list_all_models()
        self.render(
            "admin/models.html",
            title="模型引擎",
            username=self.current_user,
            models=models,
        )


class AdminModelCreateHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        data = {
            k: self.get_body_argument(k, "")
            for k in ["name", "model_name", "base_url", "api_key", "conversation_prompt"]
        }
        data["is_system"] = 1 if self.get_body_argument("is_system", "0") == "1" else 0
        ModelServiceRepository.create_model(data)
        self.redirect("/admin/models")


class AdminModelUpdateHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self, model_id):
        data = {
            k: self.get_body_argument(k, "")
            for k in ["name", "model_name", "base_url", "api_key", "conversation_prompt"]
        }
        data["is_system"] = 1 if self.get_body_argument("is_system", "0") == "1" else 0
        ModelServiceRepository.update_model(int(model_id), data)
        self.redirect("/admin/models")


class AdminModelDeleteHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self, model_id):
        ModelServiceRepository.delete_model(int(model_id))
        self.redirect("/admin/models")


class AdminModelSystemHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self, model_id):
        ModelServiceRepository.set_system_model(int(model_id))
        self.redirect("/admin/models")


class AdminModelTestHandler(AdminBaseHandler):
    """模型连通性 + 一句话采集意图调度，SSE 流式输出，并累计 Token 统计。"""

    @tornado.web.authenticated
    def post(self):
        prompt = (self.get_body_argument("prompt", "") or "").strip()
        model = ModelServiceRepository.get_system_model()
        self.set_header("Content-Type", "text/event-stream; charset=utf-8")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("Connection", "keep-alive")
        self.flush()

        def send(msg: str):
            self.write(
                f"data: {json.dumps({'message': msg}, ensure_ascii=False)}\n\n"
            )
            self.flush()

        if not model:
            send("未找到系统模型")
            self.finish()
            return

        prompt_tokens = max(1, len(prompt) // 4)
        completion_tokens = 0
        try:
            send("开始解析你的指令...")
            intent = ModelServiceRepository.parse_collect_intent(prompt)
            if intent:
                send(
                    f"识别到采集任务：关键词={intent['keyword']}，"
                    f"数量={intent['count']}，起始页={intent['start_page']}"
                )
                records = WatchtowerRepository.collect(
                    source_id=1,
                    keyword=intent["keyword"],
                    start_page=intent["start_page"],
                    item_count=intent["count"],
                )
                WatchtowerRepository.save_records(records)
                for record in records:
                    send(record["title"])
                    completion_tokens += max(1, len(record["title"]) // 4)
                send(f"采集完成，共保存 {len(records)} 条标题记录。")
                completion_tokens += 12
            else:
                send("未识别为采集任务，正在调用模型进行普通流式回复...")
                for raw_line in ModelServiceRepository.stream_chat(
                    model["id"], [{"role": "user", "content": prompt}]
                ):
                    usage = ModelServiceRepository.parse_stream_usage(raw_line)
                    if usage:
                        ModelServiceRepository.update_tokens(
                            model["id"],
                            prompt_tokens=usage["prompt_tokens"],
                            completion_tokens=usage["completion_tokens"],
                        )
                        send(
                            f"[usage] prompt={usage['prompt_tokens']}, "
                            f"completion={usage['completion_tokens']}, "
                            f"total={usage['total_tokens']}"
                        )
                        continue
                    if raw_line.startswith("data: "):
                        payload_text = raw_line[6:].strip()
                        if payload_text in ("[DONE]", "DONE"):
                            continue
                        try:
                            payload = json.loads(payload_text)
                            delta = (
                                payload.get("choices", [{}])[0]
                                .get("delta", {})
                                .get("content", "")
                            )
                            if delta:
                                send(delta)
                                completion_tokens += max(1, len(delta) // 4)
                        except Exception:
                            continue
                    elif raw_line:
                        send(raw_line)
                        completion_tokens += max(1, len(raw_line) // 4)
            if completion_tokens:
                ModelServiceRepository.update_tokens(
                    model["id"],
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                )
        except Exception as exc:
            send(f"执行失败：{exc}")
        self.finish()
