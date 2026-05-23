import json
import math

import tornado.web

from app.controllers.base import BaseHandler
from app.models.model_service import ModelServiceRepository
from app.models.rbac import RBACRepository
from app.models.user import UserRepository
from app.models.watchtower import WatchtowerRepository


class AdminLoginHandler(BaseHandler):
    def get(self):
        self.render("admin/login.html", title="管理员登录", error=None)

    def post(self):
        username = (self.get_body_argument("username", "") or "").strip()
        password = self.get_body_argument("password", "")
        if not username or not password:
            self.set_status(400)
            return self.render("admin/login.html", title="管理员登录", error="用户名或密码不能为空")
        if not UserRepository.verify_user(username, password):
            self.set_status(401)
            return self.render("admin/login.html", title="管理员登录", error="用户名或密码错误")
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
        self.render("admin/users.html", title="用户管理", username=self.current_user, users=users, roles=roles, page=page, page_size=page_size, total=total, total_pages=total_pages, has_prev=page > 1, has_next=page < total_pages)


class AdminUserCreateHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self):
        username = (self.get_body_argument("username", "") or "").strip()
        password = self.get_body_argument("password", "")
        role_id = self.get_body_argument("role_id", None)
        role_id = int(role_id) if role_id else None
        if username and password:
            UserRepository.create_user(username, password, role_id)
        self.redirect("/admin/users")


class AdminUserUpdateHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self, user_id):
        user_id = int(user_id)
        username = (self.get_body_argument("username", "") or "").strip()
        password = self.get_body_argument("password", "")
        role_id = self.get_body_argument("role_id", None)
        role_id = int(role_id) if role_id else None
        user = UserRepository.get_user_by_id(user_id)
        if user and user["username"] == "admin":
            UserRepository.update_user_password_only(user_id, password)
        else:
            UserRepository.update_user(user_id, username, password or None, role_id)
        self.redirect("/admin/users")


class AdminUserDeleteHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self, user_id):
        user = UserRepository.get_user_by_id(int(user_id))
        if not (user and user["username"] == "admin"):
            UserRepository.delete_user(int(user_id))
        self.redirect("/admin/users")


class AdminUserResetPasswordHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self, user_id):
        password = (self.get_body_argument("password", "") or "").strip()
        if password:
            UserRepository.update_user_password_only(int(user_id), password)
        self.redirect("/admin/users")


class AdminUserBatchDeleteHandler(BaseHandler):
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


class AdminRoleListHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        roles = RBACRepository.list_roles()
        permissions = RBACRepository.list_permissions()
        role_permissions = {role["id"]: RBACRepository.get_role_permissions(role["id"]) for role in roles}
        self.render("admin/roles.html", title="角色管理", username=self.current_user, roles=roles, permissions=permissions, role_permissions=role_permissions)


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
        RBACRepository.update_role(int(role_id), (self.get_body_argument("name", "") or "").strip(), (self.get_body_argument("code", "") or "").strip())
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
        self.render("admin/permissions.html", title="权限管理", username=self.current_user, permissions=permissions, roles=roles)


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
        RBACRepository.update_permission(int(permission_id), (self.get_body_argument("menu_group", "") or "").strip(), (self.get_body_argument("name", "") or "").strip(), (self.get_body_argument("code", "") or "").strip(), int(self.get_body_argument("sort_no", 0) or 0))
        self.redirect("/admin/permissions")


class AdminPermissionDeleteHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self, permission_id):
        RBACRepository.delete_permission(int(permission_id))
        self.redirect("/admin/permissions")


class AdminModelListHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        sources = WatchtowerRepository.list_sources()
        if not sources:
            WatchtowerRepository.create_source({
                "name": "百度新闻",
                "source_code": "baidu_news",
                "entry_urls": [
                    "https://www.baidu.com/s?ie=utf-8&bsst=1&rsv_dl=news_t_sk&tn=news&cl=2&medium=0&rtt=1&wd={关键词}",
                    "https://www.baidu.com/s?ie=utf-8&bsst=1&rsv_dl=news_b_pn&tn=news&cl=2&medium=0&rtt=1&wd={关键词}&pn={分页步进}"
                ],
                "headers": {},
                "keywords_label": "关键词",
                "page_param_name": "pn",
                "page_step": 10,
                "collect_limit": 10,
                "is_enabled": 1,
                "note": "百度新闻专用采集源，仅需填写关键词与起始页数",
            })
            sources = WatchtowerRepository.list_sources()
        self.render("admin/watch_sources.html", title="一句话采集工作台", username=self.current_user, sources=sources)


class AdminModelCreateHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self):
        data = {k: self.get_body_argument(k, "") for k in ["name", "model_name", "base_url", "api_key", "conversation_prompt"]}
        data["is_system"] = 1 if self.get_body_argument("is_system", "0") == "1" else 0
        ModelServiceRepository.create_model(data)
        self.redirect("/admin/models")


class AdminModelUpdateHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self, model_id):
        data = {k: self.get_body_argument(k, "") for k in ["name", "model_name", "base_url", "api_key", "conversation_prompt"]}
        data["is_system"] = 1 if self.get_body_argument("is_system", "0") == "1" else 0
        ModelServiceRepository.update_model(int(model_id), data)
        self.redirect("/admin/models")


class AdminModelDeleteHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self, model_id):
        ModelServiceRepository.delete_model(int(model_id))
        self.redirect("/admin/models")


class AdminModelSystemHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self, model_id):
        ModelServiceRepository.set_system_model(int(model_id))
        self.redirect("/admin/models")


class AdminModelTestHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self):
        prompt = (self.get_body_argument("prompt", "") or "").strip()
        model = ModelServiceRepository.get_system_model()
        self.set_header("Content-Type", "text/event-stream; charset=utf-8")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("Connection", "keep-alive")
        self.flush()

        def send(msg: str):
            self.write(f"data: {json.dumps({'message': msg}, ensure_ascii=False)}\n\n")
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
                send(f"识别到采集任务：关键词={intent['keyword']}，数量={intent['count']}，起始页={intent['start_page']}")
                records = WatchtowerRepository.collect(source_id=1, keyword=intent["keyword"], start_page=intent["start_page"], item_count=intent["count"])
                WatchtowerRepository.save_records(records)
                for record in records:
                    send(record["title"])
                    completion_tokens += max(1, len(record["title"]) // 4)
                send(f"采集完成，共保存 {len(records)} 条标题记录。")
                completion_tokens += 12
            else:
                send("未识别为采集任务，正在调用模型进行普通流式回复...")
                for raw_line in ModelServiceRepository.stream_chat(model["id"], [{"role": "user", "content": prompt}]):
                    usage = ModelServiceRepository.parse_stream_usage(raw_line)
                    if usage:
                        ModelServiceRepository.update_tokens(model["id"], prompt_tokens=usage["prompt_tokens"], completion_tokens=usage["completion_tokens"])
                        send(f"[usage] prompt={usage['prompt_tokens']}, completion={usage['completion_tokens']}, total={usage['total_tokens']}")
                        continue
                    if raw_line.startswith("data: "):
                        payload_text = raw_line[6:].strip()
                        if payload_text in ("[DONE]", "DONE"):
                            continue
                        try:
                            payload = json.loads(payload_text)
                            delta = payload.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if delta:
                                send(delta)
                                completion_tokens += max(1, len(delta) // 4)
                        except Exception:
                            continue
                    elif raw_line:
                        send(raw_line)
                        completion_tokens += max(1, len(raw_line) // 4)

            if completion_tokens:
                ModelServiceRepository.update_tokens(model["id"], prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
        except Exception as exc:
            send(f"执行失败：{exc}")
        self.finish()


class AdminWatchSourceListHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        sources = WatchtowerRepository.list_sources()
        if not sources:
            WatchtowerRepository.create_source({
                "name": "百度新闻",
                "source_code": "baidu_news",
                "entry_urls": [
                    "https://www.baidu.com/s?ie=utf-8&bsst=1&rsv_dl=news_t_sk&tn=news&cl=2&medium=0&rtt=1&wd={关键词}",
                    "https://www.baidu.com/s?ie=utf-8&bsst=1&rsv_dl=news_b_pn&tn=news&cl=2&medium=0&rtt=1&wd={关键词}&pn={分页步进}"
                ],
                "headers": {},
                "keywords_label": "关键词",
                "page_param_name": "pn",
                "page_step": 10,
                "collect_limit": 10,
                "is_enabled": 1,
                "note": "百度新闻专用采集源，仅需填写关键词与起始页数",
            })
            sources = WatchtowerRepository.list_sources()
        self.render("admin/watch_sources.html", title="百度新闻采集", username=self.current_user, sources=sources)


class AdminWatchSourceCreateHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self):
        # 固定为百度新闻专用源，仅保留关键词和起始页逻辑
        data = {
            "name": "百度新闻",
            "source_code": "baidu_news",
            "entry_urls": [
                "https://www.baidu.com/s?ie=utf-8&bsst=1&rsv_dl=news_t_sk&tn=news&cl=2&medium=0&rtt=1&wd={关键词}",
                "https://www.baidu.com/s?ie=utf-8&bsst=1&rsv_dl=news_b_pn&tn=news&cl=2&medium=0&rtt=1&wd={关键词}&pn={分页步进}"
            ],
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            },
            "keywords_label": "关键词",
            "page_param_name": "pn",
            "page_step": 10,
            "collect_limit": 10,
            "is_enabled": 1,
            "note": "百度新闻专用采集源，仅需填写关键词与起始页数",
        }
        exists = any(source["source_code"] == "baidu_news" for source in WatchtowerRepository.list_sources())
        if not exists:
            WatchtowerRepository.create_source(data)
        self.redirect("/admin/watch-sources")


class AdminWatchSourceUpdateHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self, source_id):
        # 固定源不允许修改结构，仅保留启用状态
        source = WatchtowerRepository.get_source(int(source_id))
        if source and source["source_code"] == "baidu_news":
            data = {
                "name": "百度新闻",
                "source_code": "baidu_news",
                "entry_urls": json.loads(source["entry_urls_json"] or "[]"),
                "headers": json.loads(source["headers_json"] or "{}"),
                "keywords_label": "关键词",
                "page_param_name": "pn",
                "page_step": 10,
                "collect_limit": 10,
                "is_enabled": 1 if self.get_body_argument("is_enabled", "1") == "1" else 0,
                "note": "百度新闻专用采集源，仅需填写关键词与起始页数",
            }
            WatchtowerRepository.update_source(int(source_id), data)
        self.redirect("/admin/watch-sources")


class AdminWatchSourceDeleteHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self, source_id):
        WatchtowerRepository.delete_source(int(source_id))
        self.redirect("/admin/watch-sources")


class AdminWatchCollectHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self):
        source_id = int(self.get_body_argument("source_id"))
        keyword = (self.get_body_argument("keyword", "") or "").strip()
        start_page = int(self.get_body_argument("start_page", 0) or 0)
        item_count = int(self.get_body_argument("item_count", 1) or 1)
        records = WatchtowerRepository.collect(source_id, keyword, start_page, item_count)
        WatchtowerRepository.save_records(records)
        self.redirect("/admin/watch-records")


class AdminWatchRecordListHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        page = max(1, int(self.get_argument("page", 1)))
        total, records = WatchtowerRepository.list_records(page=page, page_size=20)
        total_pages = max(1, math.ceil(total / 20))
        sources = WatchtowerRepository.list_sources()
        start_no = total - (page - 1) * 20
        self.render("admin/watch_records.html", title="数据仓库", username=self.current_user, records=records, sources=sources, page=page, total=total, total_pages=total_pages, has_prev=page > 1, has_next=page < total_pages, start_no=start_no)


class AdminWatchRecordDeleteHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self, record_id):
        WatchtowerRepository.delete_record(int(record_id))
        self.redirect("/admin/watch-records")


class AdminWatchRecordBatchDeleteHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self):
        ids = [int(i) for i in self.get_body_arguments("record_ids")]
        WatchtowerRepository.batch_delete_records(ids)
        self.redirect("/admin/watch-records")
