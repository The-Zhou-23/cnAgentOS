"""用户侧智能聊天（Task3）。"""

import json
import os

import tornado.web

from app.controllers.base import BaseHandler
from app.models.chat import CHAT_UPLOAD_DIR, ChatRepository
from app.models.digital_employee import DigitalEmployeeRepository
from app.models.user import UserRepository


class _PortalUserHandler(BaseHandler):
    def prepare(self):
        username = self.get_current_user()
        if not username:
            return
        user = UserRepository.get_user_by_username(username)
        role_code = UserRepository.get_role_code(user)
        if UserRepository.is_admin_role(role_code):
            self.redirect("/admin/chat/groups")
            raise tornado.web.Finish()


class PortalChatHandler(_PortalUserHandler):
    @tornado.web.authenticated
    def get(self):
        user = self.get_current_user_record()
        server = ChatRepository.get_active_server()
        digitals = ChatRepository.list_digital_employees_for_picker()
        self.render(
            "portal/chat.html",
            title="智能聊天",
            username=self.current_user,
            role_name=self.get_current_role_name(),
            active_nav="chat",
            active_page="",
            user_id=user["id"] if user else 0,
            server=server,
            digitals=digitals,
        )


class PortalChatApiHandler(_PortalUserHandler):
    """JSON API：好友、会话、消息、建群等。"""

    @tornado.web.authenticated
    def get(self, action: str):
        user = self.get_current_user_record()
        uid = user["id"]
        if action == "conversations":
            self.write_json({"ok": True, "items": ChatRepository.list_conversations(uid)})
            return
        if action == "contacts":
            self.write_json(
                {
                    "ok": True,
                    "contacts": [
                        {"id": r["id"], "username": r["username"]}
                        for r in ChatRepository.list_contacts(uid)
                    ],
                    "pending": [
                        {"id": r["id"], "username": r["username"]}
                        for r in ChatRepository.list_pending_requests(uid)
                    ],
                    "outgoing": [
                        {"id": r["id"], "username": r["username"]}
                        for r in ChatRepository.list_outgoing_pending(uid)
                    ],
                }
            )
            return
        if action == "messages":
            conv_type = self.get_argument("conv_type", "")
            conv_id = self.get_argument("conv_id", "")
            after_id = int(self.get_argument("after_id", "0") or 0)
            if not ChatRepository.can_access_conv(uid, conv_type, conv_id):
                self.write_json({"ok": False, "message": "无权访问该会话"})
                return
            rows = ChatRepository.get_messages(conv_type, conv_id, after_id=after_id)
            self.write_json(
                {
                    "ok": True,
                    "messages": [dict(r) for r in rows],
                }
            )
            return
        if action == "members":
            group_id = int(self.get_argument("group_id", "0") or 0)
            if not ChatRepository.user_in_group(uid, group_id):
                self.write_json({"ok": False, "message": "无权查看"})
                return
            self.write_json(
                {"ok": True, "members": ChatRepository.get_group_members(group_id)}
            )
            return
        if action == "server":
            self.write_json({"ok": True, "server": ChatRepository.get_active_server()})
            return
        if action == "digitals":
            self.write_json(
                {"ok": True, "items": ChatRepository.list_digital_employees_for_picker()}
            )
            return
        self.set_status(404)
        self.write_json({"ok": False, "message": "unknown action"})

    @tornado.web.authenticated
    def post(self, action: str):
        user = self.get_current_user_record()
        uid = user["id"]
        if action == "search":
            keyword = (self.get_body_argument("keyword", "") or "").strip()
            rows = ChatRepository.search_users(keyword, uid)
            self.write_json(
                {
                    "ok": True,
                    "users": [{"id": r["id"], "username": r["username"]} for r in rows],
                }
            )
            return
        if action == "friend":
            username = (self.get_body_argument("username", "") or "").strip()
            result = ChatRepository.send_friend_request(uid, username)
            self.write_json(result)
            return
        if action == "accept":
            requester_id = int(self.get_body_argument("friend_id", "0") or 0)
            result = ChatRepository.accept_friend(uid, requester_id)
            self.write_json(result)
            return
        if action == "unfriend":
            friend_id = int(self.get_body_argument("friend_id", "0") or 0)
            result = ChatRepository.remove_friend(uid, friend_id)
            self.write_json(result)
            return
        if action == "group":
            name = self.get_body_argument("name", "")
            friend_ids = self.get_body_arguments("friend_ids")
            digital_aliases = self.get_body_arguments("digital_aliases")
            result = ChatRepository.create_group(uid, name, friend_ids, digital_aliases)
            self.write_json(result)
            return
        if action == "send":
            conv_type = self.get_body_argument("conv_type", "")
            conv_id = self.get_body_argument("conv_id", "")
            content = (self.get_body_argument("content", "") or "").strip()
            if not content:
                self.write_json({"ok": False, "message": "消息不能为空"})
                return
            if not ChatRepository.can_access_conv(uid, conv_type, conv_id):
                self.write_json({"ok": False, "message": "无权发送"})
                return
            msg_id = ChatRepository.add_message(
                conv_type,
                conv_id,
                "user",
                uid,
                user["username"],
                content,
            )
            digital_replies = []
            if conv_type == "group" and "@" in content:
                gid = int(conv_id)
                for alias in ChatRepository.parse_mentions(content):
                    if not ChatRepository.group_has_digital(gid, alias):
                        continue
                    full_msg = content if content.startswith(f"@{alias}") else f"@{alias} {content}"
                    history = []
                    parts = []
                    for chunk in DigitalEmployeeRepository.chat_stream(full_msg, history=history):
                        if chunk != "处理完成":
                            parts.append(chunk)
                    reply_text = "\n".join(parts).strip() or f"@{alias} 暂无回复"
                    ChatRepository.add_message(
                        conv_type,
                        conv_id,
                        "digital",
                        0,
                        alias,
                        reply_text,
                    )
                    digital_replies.append({"alias": alias, "content": reply_text})
            self.write_json({"ok": True, "message_id": msg_id, "digital_replies": digital_replies})
            return
        self.set_status(404)
        self.write_json({"ok": False, "message": "unknown action"})

    def write_json(self, data: dict):
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.write(json.dumps(data, ensure_ascii=False))


class PortalChatUploadHandler(_PortalUserHandler):
    @tornado.web.authenticated
    def post(self):
        user = self.get_current_user_record()
        if not self.request.files.get("file"):
            self.set_status(400)
            self.finish(json.dumps({"ok": False, "message": "未选择文件"}, ensure_ascii=False))
            return
        f = self.request.files["file"][0]
        conv_type = self.get_body_argument("conv_type", "")
        conv_id = self.get_body_argument("conv_id", "")
        if not ChatRepository.can_access_conv(user["id"], conv_type, conv_id):
            self.set_status(403)
            self.finish(json.dumps({"ok": False, "message": "无权上传"}, ensure_ascii=False))
            return
        result = ChatRepository.save_file(f["body"], f["filename"], f.get("content_type", ""))
        if result.get("ok"):
            ChatRepository.add_message(
                conv_type,
                conv_id,
                "user",
                user["id"],
                user["username"],
                f"[文件] {f['filename']}",
                msg_type="file",
                file_id=result["file_id"],
            )
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.write(json.dumps(result, ensure_ascii=False))


class PortalChatFileHandler(_PortalUserHandler):
    @tornado.web.authenticated
    def get(self, file_id: str):
        row = ChatRepository.get_file(int(file_id))
        if not row:
            self.set_status(404)
            self.finish("文件不存在")
            return
        path = os.path.join(CHAT_UPLOAD_DIR, row["stored_name"])
        if not os.path.isfile(path):
            self.set_status(404)
            self.finish("文件已删除")
            return
        self.set_header("Content-Type", row["mime_type"] or "application/octet-stream")
        self.set_header(
            "Content-Disposition",
            f'attachment; filename="{row["original_name"]}"',
        )
        with open(path, "rb") as fp:
            self.write(fp.read())
