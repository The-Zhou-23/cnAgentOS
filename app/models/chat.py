"""智能聊天子系统数据层（Task3）。"""

import hashlib
import json
import os
import sqlite3
from typing import Any

from app.models.db import get_connection, _project_root

CHAT_UPLOAD_DIR = os.path.join(_project_root(), "uploads", "chat")


class ChatRepository:
    @staticmethod
    def init_schema():
        os.makedirs(CHAT_UPLOAD_DIR, exist_ok=True)
        with get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_friendships(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    friend_id INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL DEFAULT(datetime('now')),
                    UNIQUE(user_id, friend_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_groups(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    owner_id INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    announcement TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT(datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT(datetime('now'))
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_group_members(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    member_type TEXT NOT NULL,
                    member_ref_id INTEGER NOT NULL,
                    nickname TEXT NOT NULL DEFAULT '',
                    joined_at TEXT NOT NULL DEFAULT(datetime('now')),
                    UNIQUE(group_id, member_type, member_ref_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conv_type TEXT NOT NULL,
                    conv_id INTEGER NOT NULL,
                    sender_type TEXT NOT NULL,
                    sender_id INTEGER NOT NULL,
                    sender_name TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL,
                    msg_type TEXT NOT NULL DEFAULT 'text',
                    file_id INTEGER,
                    created_at TEXT NOT NULL DEFAULT(datetime('now'))
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_files(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_hash TEXT NOT NULL UNIQUE,
                    original_name TEXT NOT NULL,
                    stored_name TEXT NOT NULL,
                    size INTEGER NOT NULL DEFAULT 0,
                    mime_type TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT(datetime('now'))
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_servers(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    base_url TEXT NOT NULL,
                    weight INTEGER NOT NULL DEFAULT 100,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    is_primary INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT(datetime('now'))
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_msg_conv ON chat_messages(conv_type, conv_id, id)"
            )
            ChatRepository.cleanup_legacy_pending_pairs()
            row = conn.execute("select count(1) as c from chat_servers").fetchone()
            if row["c"] == 0:
                conn.execute(
                    """
                    insert into chat_servers(name, base_url, weight, is_active, is_primary)
                    values(?,?,?,?,?)
                    """,
                    ("本地主节点", "http://127.0.0.1:10087", 100, 1, 1),
                )

    @staticmethod
    def search_users(keyword: str, exclude_user_id: int, limit: int = 20):
        kw = f"%{keyword.strip()}%"
        with get_connection() as conn:
            return conn.execute(
                """
                select id, username from users
                where username like ? and id != ? and coalesce(is_disabled, 0) = 0
                order by username limit ?
                """,
                (kw, exclude_user_id, limit),
            ).fetchall()

    @staticmethod
    def send_friend_request(user_id: int, target_username: str) -> dict:
        with get_connection() as conn:
            target = conn.execute(
                "select id, username from users where username = ?",
                (target_username,),
            ).fetchone()
            if not target:
                return {"ok": False, "message": "用户不存在"}
            if target["id"] == user_id:
                return {"ok": False, "message": "不能添加自己为好友"}
            existing = conn.execute(
                """
                select user_id, friend_id, status from chat_friendships
                where (user_id=? and friend_id=?) or (user_id=? and friend_id=?)
                """,
                (user_id, target["id"], target["id"], user_id),
            ).fetchone()
            if existing:
                st = existing["status"]
                if st == "accepted":
                    return {"ok": False, "message": "已是好友"}
                # 对方已向我发起申请 → 应点「接受」而非再次申请
                if existing["user_id"] == target["id"] and existing["friend_id"] == user_id:
                    return {"ok": False, "message": "对方已向你发送申请，请在通讯录中接受"}
                return {"ok": False, "message": "好友申请已发送，请等待对方处理"}
            # 仅保存单向 pending：user_id=发起人，friend_id=接收人
            conn.execute(
                "delete from chat_friendships where user_id=? and friend_id=? and status='pending'",
                (target["id"], user_id),
            )
            conn.execute(
                "insert into chat_friendships(user_id, friend_id, status) values(?,?,?)",
                (user_id, target["id"], "pending"),
            )
        return {"ok": True, "message": "好友申请已发送"}

    @staticmethod
    def accept_friend(acceptor_id: int, requester_id: int) -> dict:
        """仅接收方 acceptor_id 可接受 requester_id 发来的申请。"""
        if acceptor_id == requester_id:
            return {"ok": False, "message": "不能同意自己的好友申请"}
        with get_connection() as conn:
            pending = conn.execute(
                """
                select id from chat_friendships
                where user_id=? and friend_id=? and status='pending'
                """,
                (requester_id, acceptor_id),
            ).fetchone()
            if not pending:
                return {"ok": False, "message": "无待处理的好友申请或无权操作"}
            conn.execute(
                """
                update chat_friendships set status='accepted'
                where user_id=? and friend_id=?
                """,
                (requester_id, acceptor_id),
            )
            conn.execute(
                """
                insert into chat_friendships(user_id, friend_id, status)
                values(?,?,?)
                on conflict(user_id, friend_id) do update set status='accepted'
                """,
                (acceptor_id, requester_id, "accepted"),
            )
        return {"ok": True, "message": "已成为好友"}

    @staticmethod
    def remove_friend(user_id: int, friend_id: int) -> dict:
        """删除好友或撤回/拒绝好友关系（双向记录一并清除）。"""
        if user_id == friend_id:
            return {"ok": False, "message": "无效操作"}
        with get_connection() as conn:
            row = conn.execute(
                """
                select 1 from chat_friendships
                where (user_id=? and friend_id=?) or (user_id=? and friend_id=?)
                """,
                (user_id, friend_id, friend_id, user_id),
            ).fetchone()
            if not row:
                return {"ok": False, "message": "不存在该好友关系"}
            conn.execute(
                """
                delete from chat_friendships
                where (user_id=? and friend_id=?) or (user_id=? and friend_id=?)
                """,
                (user_id, friend_id, friend_id, user_id),
            )
        return {"ok": True, "message": "已删除好友"}

    @staticmethod
    def list_contacts(user_id: int):
        with get_connection() as conn:
            rows = conn.execute(
                """
                select distinct u.id, u.username
                from chat_friendships f
                join users u on u.id = case
                    when f.user_id = ? then f.friend_id
                    else f.user_id
                end
                where (f.user_id = ? or f.friend_id = ?) and f.status = 'accepted'
                order by u.username
                """,
                (user_id, user_id, user_id),
            ).fetchall()
        return rows

    @staticmethod
    def list_pending_requests(user_id: int):
        """别人发给我、待我同意的申请（friend_id = 当前用户）。"""
        with get_connection() as conn:
            return conn.execute(
                """
                select u.id, u.username, f.created_at
                from chat_friendships f
                join users u on u.id = f.user_id
                where f.friend_id = ? and f.status = 'pending'
                order by f.created_at desc
                """,
                (user_id,),
            ).fetchall()

    @staticmethod
    def list_outgoing_pending(user_id: int):
        """我发出、等待对方同意的申请。"""
        with get_connection() as conn:
            return conn.execute(
                """
                select u.id, u.username, f.created_at
                from chat_friendships f
                join users u on u.id = f.friend_id
                where f.user_id = ? and f.status = 'pending'
                order by f.created_at desc
                """,
                (user_id,),
            ).fetchall()

    @staticmethod
    def cleanup_legacy_pending_pairs():
        """清理旧版双向 pending 脏数据，每组好友关系只保留一条 pending。"""
        with get_connection() as conn:
            conn.execute(
                """
                delete from chat_friendships
                where status = 'pending'
                  and id in (
                    select f1.id
                    from chat_friendships f1
                    inner join chat_friendships f2
                      on f1.user_id = f2.friend_id and f1.friend_id = f2.user_id
                    where f1.status = 'pending' and f2.status = 'pending'
                      and f1.id > f2.id
                  )
                """
            )

    @staticmethod
    def private_conv_id(user_a: int, user_b: int) -> str:
        return f"private:{min(user_a, user_b)}:{max(user_a, user_b)}"

    @staticmethod
    def _parse_private_conv(conv_key: str) -> tuple[int, int] | None:
        parts = (conv_key or "").split(":")
        if len(parts) != 3 or parts[0] != "private":
            return None
        return int(parts[1]), int(parts[2])

    @staticmethod
    def list_conversations(user_id: int) -> list[dict]:
        items: list[dict] = []
        contacts = ChatRepository.list_contacts(user_id)
        for c in contacts:
            conv_key = ChatRepository.private_conv_id(user_id, c["id"])
            last = ChatRepository._last_message("private", conv_key)
            items.append(
                {
                    "conv_type": "private",
                    "conv_id": conv_key,
                    "title": c["username"],
                    "peer_id": c["id"],
                    "last_message": last["content"] if last else "",
                    "last_at": last["created_at"] if last else "",
                }
            )
        with get_connection() as conn:
            groups = conn.execute(
                """
                select g.id, g.name, g.status, g.announcement
                from chat_groups g
                join chat_group_members m on m.group_id = g.id
                where m.member_type = 'user' and m.member_ref_id = ? and g.status != 'dissolved'
                order by g.updated_at desc
                """,
                (user_id,),
            ).fetchall()
        for g in groups:
            last = ChatRepository._last_message("group", str(g["id"]))
            items.append(
                {
                    "conv_type": "group",
                    "conv_id": str(g["id"]),
                    "title": g["name"],
                    "peer_id": g["id"],
                    "status": g["status"],
                    "announcement": g["announcement"],
                    "last_message": last["content"] if last else "",
                    "last_at": last["created_at"] if last else "",
                }
            )
        items.sort(key=lambda x: x.get("last_at") or "", reverse=True)
        return items

    @staticmethod
    def _last_message(conv_type: str, conv_id: str):
        with get_connection() as conn:
            return conn.execute(
                """
                select content, created_at from chat_messages
                where conv_type=? and conv_id=?
                order by id desc limit 1
                """,
                (conv_type, conv_id),
            ).fetchone()

    @staticmethod
    def create_group(owner_id: int, name: str, friend_ids: list[int], digital_aliases: list[str]) -> dict:
        name = (name or "").strip()
        if not name:
            return {"ok": False, "message": "群名称不能为空"}
        friend_ids = [int(x) for x in friend_ids if int(x) != owner_id]
        with get_connection() as conn:
            cur = conn.execute(
                "insert into chat_groups(name, owner_id) values(?,?)",
                (name, owner_id),
            )
            group_id = cur.lastrowid
            conn.execute(
                "insert into chat_group_members(group_id, member_type, member_ref_id, nickname) values(?,?,?,?)",
                (group_id, "user", owner_id, ""),
            )
            for fid in friend_ids:
                row = conn.execute(
                    """
                    select 1 from chat_friendships
                    where status='accepted'
                      and ((user_id=? and friend_id=?) or (user_id=? and friend_id=?))
                    """,
                    (owner_id, fid, fid, owner_id),
                ).fetchone()
                if row:
                    conn.execute(
                        """
                        insert or ignore into chat_group_members(group_id, member_type, member_ref_id)
                        values(?,?,?)
                        """,
                        (group_id, "user", fid),
                    )
            from app.models.digital_employee import DigitalEmployeeRepository

            for alias in digital_aliases:
                alias = alias.strip().lstrip("@")
                if not alias:
                    continue
                emp = DigitalEmployeeRepository.get_employee_by_alias(alias)
                if emp:
                    conn.execute(
                        """
                        insert or ignore into chat_group_members(group_id, member_type, member_ref_id, nickname)
                        values(?,?,?,?)
                        """,
                        (group_id, "digital", emp["id"], alias),
                    )
            conn.execute(
                "update chat_groups set updated_at=datetime('now') where id=?",
                (group_id,),
            )
        ChatRepository.add_system_message("group", str(group_id), f"群「{name}」已创建")
        return {"ok": True, "group_id": group_id}

    @staticmethod
    def get_group_members(group_id: int):
        with get_connection() as conn:
            rows = conn.execute(
                """
                select m.member_type, m.member_ref_id, m.nickname,
                       u.username as user_name,
                       d.alias as digital_alias
                from chat_group_members m
                left join users u on m.member_type='user' and u.id = m.member_ref_id
                left join digital_employees d on m.member_type='digital' and d.id = m.member_ref_id
                where m.group_id = ?
                """,
                (group_id,),
            ).fetchall()
        result = []
        for r in rows:
            if r["member_type"] == "user":
                result.append(
                    {
                        "type": "user",
                        "id": r["member_ref_id"],
                        "name": r["user_name"] or f"用户{r['member_ref_id']}",
                    }
                )
            else:
                result.append(
                    {
                        "type": "digital",
                        "id": r["member_ref_id"],
                        "name": r["digital_alias"] or r["nickname"] or "数字员工",
                    }
                )
        return result

    @staticmethod
    def user_in_group(user_id: int, group_id: int) -> bool:
        with get_connection() as conn:
            row = conn.execute(
                """
                select 1 from chat_group_members
                where group_id=? and member_type='user' and member_ref_id=?
                """,
                (group_id, user_id),
            ).fetchone()
        return bool(row)

    @staticmethod
    def get_messages(conv_type: str, conv_id: str, after_id: int = 0, limit: int = 50):
        with get_connection() as conn:
            return conn.execute(
                """
                select id, sender_type, sender_id, sender_name, content, msg_type, file_id, created_at
                from chat_messages
                where conv_type=? and conv_id=? and id > ?
                order by id asc limit ?
                """,
                (conv_type, conv_id, after_id, limit),
            ).fetchall()

    @staticmethod
    def add_message(
        conv_type: str,
        conv_id: str,
        sender_type: str,
        sender_id: int,
        sender_name: str,
        content: str,
        msg_type: str = "text",
        file_id: int | None = None,
    ) -> int:
        with get_connection() as conn:
            cur = conn.execute(
                """
                insert into chat_messages(conv_type, conv_id, sender_type, sender_id, sender_name, content, msg_type, file_id)
                values(?,?,?,?,?,?,?,?)
                """,
                (conv_type, conv_id, sender_type, sender_id, sender_name, content, msg_type, file_id),
            )
            msg_id = cur.lastrowid
            if conv_type == "group":
                conn.execute(
                    "update chat_groups set updated_at=datetime('now') where id=?",
                    (int(conv_id),),
                )
        return msg_id

    @staticmethod
    def add_system_message(conv_type: str, conv_id: str, content: str):
        ChatRepository.add_message(conv_type, conv_id, "system", 0, "系统", content, "system")

    @staticmethod
    def can_access_conv(user_id: int, conv_type: str, conv_id: str) -> bool:
        if conv_type == "private":
            parsed = ChatRepository._parse_private_conv(conv_id)
            if not parsed:
                return False
            return user_id in parsed
        if conv_type == "group":
            try:
                gid = int(conv_id)
            except ValueError:
                return False
            with get_connection() as conn:
                g = conn.execute("select status from chat_groups where id=?", (gid,)).fetchone()
                if not g or g["status"] in ("dissolved", "banned"):
                    return False
            return ChatRepository.user_in_group(user_id, gid)
        return False

    @staticmethod
    def save_file(file_body: bytes, original_name: str, mime_type: str = "") -> dict:
        file_hash = hashlib.sha256(file_body).hexdigest()
        with get_connection() as conn:
            existing = conn.execute(
                "select id, stored_name from chat_files where file_hash=?",
                (file_hash,),
            ).fetchone()
            if existing:
                return {
                    "ok": True,
                    "file_id": existing["id"],
                    "dedup": True,
                    "url": f"/portal/chat/file/{existing['id']}",
                }
            ext = os.path.splitext(original_name)[1] or ".bin"
            stored_name = f"{file_hash}{ext}"
            path = os.path.join(CHAT_UPLOAD_DIR, stored_name)
            with open(path, "wb") as f:
                f.write(file_body)
            cur = conn.execute(
                """
                insert into chat_files(file_hash, original_name, stored_name, size, mime_type)
                values(?,?,?,?,?)
                """,
                (file_hash, original_name, stored_name, len(file_body), mime_type),
            )
            fid = cur.lastrowid
        return {"ok": True, "file_id": fid, "dedup": False, "url": f"/portal/chat/file/{fid}"}

    @staticmethod
    def get_file(file_id: int):
        with get_connection() as conn:
            return conn.execute("select * from chat_files where id=?", (file_id,)).fetchone()

    @staticmethod
    def get_active_server() -> dict:
        with get_connection() as conn:
            row = conn.execute(
                """
                select * from chat_servers
                where is_active=1
                order by is_primary desc, weight desc, id asc
                limit 1
                """
            ).fetchone()
            if row:
                return dict(row)
        return {"name": "本地", "base_url": "http://127.0.0.1:10087"}

    @staticmethod
    def list_servers():
        with get_connection() as conn:
            return conn.execute(
                "select * from chat_servers order by is_primary desc, weight desc, id asc"
            ).fetchall()

    @staticmethod
    def create_server(data: dict) -> bool:
        try:
            with get_connection() as conn:
                if int(data.get("is_primary", 0)):
                    conn.execute("update chat_servers set is_primary=0")
                conn.execute(
                    """
                    insert into chat_servers(name, base_url, weight, is_active, is_primary)
                    values(?,?,?,?,?)
                    """,
                    (
                        data["name"],
                        data["base_url"],
                        int(data.get("weight", 100)),
                        int(data.get("is_active", 1)),
                        int(data.get("is_primary", 0)),
                    ),
                )
            return True
        except sqlite3.Error:
            return False

    @staticmethod
    def update_server(server_id: int, data: dict) -> bool:
        with get_connection() as conn:
            if int(data.get("is_primary", 0)):
                conn.execute("update chat_servers set is_primary=0")
            conn.execute(
                """
                update chat_servers set name=?, base_url=?, weight=?, is_active=?, is_primary=?
                where id=?
                """,
                (
                    data["name"],
                    data["base_url"],
                    int(data.get("weight", 100)),
                    int(data.get("is_active", 1)),
                    int(data.get("is_primary", 0)),
                    server_id,
                ),
            )
        return True

    @staticmethod
    def delete_server(server_id: int):
        with get_connection() as conn:
            conn.execute("delete from chat_servers where id=?", (server_id,))

    @staticmethod
    def list_groups_admin(page: int = 1, page_size: int = 20):
        offset = (page - 1) * page_size
        with get_connection() as conn:
            total = conn.execute("select count(1) as c from chat_groups").fetchone()["c"]
            rows = conn.execute(
                """
                select g.*, u.username as owner_name,
                       (select count(1) from chat_group_members m where m.group_id=g.id) as member_count
                from chat_groups g
                left join users u on u.id = g.owner_id
                order by g.id desc limit ? offset ?
                """,
                (page_size, offset),
            ).fetchall()
        return int(total), rows

    @staticmethod
    def set_group_status(group_id: int, status: str, announcement: str = ""):
        with get_connection() as conn:
            conn.execute(
                "update chat_groups set status=?, announcement=?, updated_at=datetime('now') where id=?",
                (status, announcement, group_id),
            )
        if announcement:
            ChatRepository.add_system_message("group", str(group_id), f"【群公告】{announcement}")

    @staticmethod
    def dissolve_group(group_id: int):
        ChatRepository.set_group_status(group_id, "dissolved")
        ChatRepository.add_system_message("group", str(group_id), "群聊已被管理员解散")

    @staticmethod
    def list_files_admin(page: int = 1, page_size: int = 20):
        offset = (page - 1) * page_size
        with get_connection() as conn:
            total = conn.execute("select count(1) as c from chat_files").fetchone()["c"]
            rows = conn.execute(
                "select * from chat_files order by id desc limit ? offset ?",
                (page_size, offset),
            ).fetchall()
        return int(total), rows

    @staticmethod
    def delete_file_admin(file_id: int):
        row = ChatRepository.get_file(file_id)
        if not row:
            return
        path = os.path.join(CHAT_UPLOAD_DIR, row["stored_name"])
        if os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                pass
        with get_connection() as conn:
            conn.execute("delete from chat_files where id=?", (file_id,))

    @staticmethod
    def list_digital_employees_for_picker():
        from app.models.digital_employee import DigitalEmployeeRepository

        return [
            {"id": e["id"], "alias": e["alias"], "description": e["description"]}
            for e in DigitalEmployeeRepository.list_employees()
            if e["is_enabled"]
        ]

    @staticmethod
    def parse_mentions(content: str) -> list[str]:
        import re

        return re.findall(r"@([\u4e00-\u9fa5A-Za-z0-9_\-]+)", content or "")

    @staticmethod
    def group_has_digital(group_id: int, alias: str) -> bool:
        from app.models.digital_employee import DigitalEmployeeRepository

        emp = DigitalEmployeeRepository.get_employee_by_alias(alias)
        if not emp:
            return False
        with get_connection() as conn:
            row = conn.execute(
                """
                select 1 from chat_group_members
                where group_id=? and member_type='digital' and member_ref_id=?
                """,
                (group_id, emp["id"]),
            ).fetchone()
        return bool(row)
