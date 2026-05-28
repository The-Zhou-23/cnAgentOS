"""后台智能聊天管理（Task3）。"""

import json

import tornado.web

from app.controllers.base import AdminBaseHandler
from app.models.chat import ChatRepository


class AdminChatGroupsHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        page = int(self.get_argument("page", "1") or 1)
        total, groups = ChatRepository.list_groups_admin(page=page)
        self.render(
            "admin/chat_groups.html",
            title="群管理",
            username=self.current_user,
            active_page="chat_groups",
            groups=groups,
            page=page,
            total=total,
        )

    @tornado.web.authenticated
    def post(self):
        action = self.get_body_argument("action", "")
        group_id = int(self.get_body_argument("group_id", "0") or 0)
        if action == "dissolve":
            ChatRepository.dissolve_group(group_id)
        elif action == "ban":
            ChatRepository.set_group_status(group_id, "banned")
        elif action == "unban":
            ChatRepository.set_group_status(group_id, "active")
        elif action == "announce":
            text = (self.get_body_argument("announcement", "") or "").strip()
            ChatRepository.set_group_status(group_id, "active", announcement=text)
        self.redirect("/admin/chat/groups")


class AdminChatGroupMembersHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self, group_id: str):
        members = ChatRepository.get_group_members(int(group_id))
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.write(json.dumps({"ok": True, "members": members}, ensure_ascii=False))


class AdminChatFilesHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        page = int(self.get_argument("page", "1") or 1)
        total, files = ChatRepository.list_files_admin(page=page)
        self.render(
            "admin/chat_files.html",
            title="聊天文件",
            username=self.current_user,
            active_page="chat_files",
            files=files,
            page=page,
            total=total,
        )

    @tornado.web.authenticated
    def post(self):
        file_id = int(self.get_body_argument("file_id", "0") or 0)
        ChatRepository.delete_file_admin(file_id)
        self.redirect("/admin/chat/files")


class AdminChatServersHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        servers = ChatRepository.list_servers()
        self.render(
            "admin/chat_servers.html",
            title="聊天服务器",
            username=self.current_user,
            active_page="chat_servers",
            servers=servers,
        )

    @tornado.web.authenticated
    def post(self):
        action = self.get_body_argument("action", "create")
        if action == "delete":
            ChatRepository.delete_server(int(self.get_body_argument("server_id", "0") or 0))
        else:
            data = {
                "name": self.get_body_argument("name", ""),
                "base_url": self.get_body_argument("base_url", ""),
                "weight": self.get_body_argument("weight", "100"),
                "is_active": self.get_body_argument("is_active", "1"),
                "is_primary": self.get_body_argument("is_primary", "0"),
            }
            sid = self.get_body_argument("server_id", "")
            if sid:
                ChatRepository.update_server(int(sid), data)
            else:
                ChatRepository.create_server(data)
        self.redirect("/admin/chat/servers")
