(function () {
    const app = document.querySelector(".chat-app");
    if (!app) return;

    const userId = parseInt(app.dataset.userId || "0", 10);
    let currentConv = null;
    let lastMsgId = 0;
    let pollTimer = null;

    function getXsrf() {
        const input = document.querySelector('input[name="_xsrf"]');
        return input ? input.value : "";
    }

    async function apiGet(action, params) {
        const qs = new URLSearchParams({ ...params });
        const res = await fetch(`/portal/chat/api/${action}?${qs}`);
        return res.json();
    }

    async function apiPost(action, body) {
        const fd = new FormData();
        fd.append("_xsrf", getXsrf());
        Object.entries(body || {}).forEach(([k, v]) => {
            if (Array.isArray(v)) v.forEach((item) => fd.append(k, item));
            else fd.append(k, v);
        });
        const res = await fetch(`/portal/chat/api/${action}`, { method: "POST", body: fd });
        return res.json();
    }

    function esc(s) {
        const d = document.createElement("div");
        d.textContent = s || "";
        return d.innerHTML;
    }

    function renderBubble(msg) {
        const isMe = msg.sender_type === "user" && parseInt(msg.sender_id, 10) === userId;
        let cls = "other";
        if (msg.sender_type === "system") cls = "system";
        else if (msg.sender_type === "digital") cls = "digital";
        else if (isMe) cls = "me";
        const name = msg.sender_name || (isMe ? "我" : "对方");
        return `<div class="chat-bubble ${cls}">
            <div class="meta">${esc(name)} · ${esc(msg.created_at || "")}</div>
            <div>${esc(msg.content)}</div>
        </div>`;
    }

    async function loadConversations() {
        const data = await apiGet("conversations");
        const list = document.getElementById("convList");
        list.innerHTML = "";
        (data.items || []).forEach((item) => {
            const el = document.createElement("div");
            el.className = "chat-conv-item";
            el.dataset.convType = item.conv_type;
            el.dataset.convId = item.conv_id;
            el.dataset.title = item.title;
            el.innerHTML = `<div class="title">${esc(item.title)}</div>
                <div class="preview">${esc(item.last_message || "暂无消息")}</div>`;
            el.addEventListener("click", () => openConv(item, el));
            list.appendChild(el);
        });
    }

    async function openConv(item, el) {
        document.querySelectorAll(".chat-conv-item").forEach((n) => n.classList.remove("active"));
        if (el) el.classList.add("active");
        currentConv = item;
        lastMsgId = 0;
        document.getElementById("chatEmpty").classList.add("d-none");
        document.getElementById("chatActive").classList.remove("d-none");
        document.getElementById("chatTitle").textContent = item.title;
        const ann = document.getElementById("chatAnnouncement");
        if (item.announcement) {
            ann.textContent = item.announcement;
            ann.classList.remove("d-none");
        } else {
            ann.classList.add("d-none");
        }
        if (item.conv_type === "group") {
            const m = await apiGet("members", { group_id: item.conv_id });
            document.getElementById("chatMembersHint").textContent =
                (m.members || []).map((x) => x.name).join("、");
        } else {
            document.getElementById("chatMembersHint").textContent = "私聊";
        }
        await loadMessages(true);
        startPoll();
    }

    async function loadMessages(clear) {
        if (!currentConv) return;
        const data = await apiGet("messages", {
            conv_type: currentConv.conv_type,
            conv_id: currentConv.conv_id,
            after_id: clear ? 0 : lastMsgId,
        });
        const box = document.getElementById("chatMessages");
        if (clear) box.innerHTML = "";
        (data.messages || []).forEach((msg) => {
            if (msg.id > lastMsgId) lastMsgId = msg.id;
            box.insertAdjacentHTML("beforeend", renderBubble(msg));
        });
        box.scrollTop = box.scrollHeight;
    }

    function startPoll() {
        if (pollTimer) clearInterval(pollTimer);
        pollTimer = setInterval(() => loadMessages(false), 3000);
    }

    document.querySelectorAll(".chat-tabs button").forEach((btn) => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".chat-tabs button").forEach((b) => b.classList.remove("active"));
            btn.classList.add("active");
            const tab = btn.dataset.tab;
            document.querySelectorAll(".chat-panel").forEach((p) => p.classList.remove("active"));
            const map = { conv: "panelConv", contacts: "panelContacts", search: "panelSearch", create: "panelCreate" };
            document.getElementById(map[tab]).classList.add("active");
            if (tab === "contacts") loadContacts();
            if (tab === "create") loadFriendCheckboxes();
        });
    });

    async function loadContacts() {
        const data = await apiGet("contacts");
        const pending = document.getElementById("pendingList");
        pending.innerHTML = "";
        (data.pending || []).forEach((p) => {
            const row = document.createElement("div");
            row.className = "chat-pending-item";
            row.innerHTML = `<span>${esc(p.username)} 请求加你为好友</span>
                <span class="chat-pending-actions">
                <button type="button" class="btn btn-sm btn-primary btn-accept">接受</button>
                <button type="button" class="btn btn-sm btn-outline-secondary btn-reject">拒绝</button>
                </span>`;
            row.querySelector(".btn-accept").addEventListener("click", async () => {
                const r = await apiPost("accept", { friend_id: p.id });
                if (!r.ok) {
                    alert(r.message || "无法接受");
                    return;
                }
                loadContacts();
                loadConversations();
            });
            row.querySelector(".btn-reject").addEventListener("click", async () => {
                const r = await apiPost("unfriend", { friend_id: p.id });
                if (!r.ok) {
                    alert(r.message || "操作失败");
                    return;
                }
                loadContacts();
            });
            pending.appendChild(row);
        });
        (data.outgoing || []).forEach((p) => {
            const row = document.createElement("div");
            row.className = "chat-pending-item chat-pending-outgoing";
            row.innerHTML = `<span>已向 ${esc(p.username)} 发送申请，等待对方同意</span>
                <button type="button" class="btn btn-sm btn-outline-secondary">撤回</button>`;
            row.querySelector("button").addEventListener("click", async (e) => {
                e.stopPropagation();
                if (!confirm(`撤回对 ${p.username} 的好友申请？`)) return;
                const r = await apiPost("unfriend", { friend_id: p.id });
                if (!r.ok) {
                    alert(r.message || "撤回失败");
                    return;
                }
                loadContacts();
            });
            pending.appendChild(row);
        });
        const list = document.getElementById("contactList");
        list.innerHTML = "";
        (data.contacts || []).forEach((c) => {
            const el = document.createElement("div");
            el.className = "chat-contact-item";
            el.innerHTML = `<span class="chat-contact-name">${esc(c.username)}</span>
                <button type="button" class="btn btn-sm btn-outline-danger chat-contact-del" title="删除好友">删除</button>`;
            el.querySelector(".chat-contact-name").addEventListener("click", () => {
                const convId = `private:${Math.min(userId, c.id)}:${Math.max(userId, c.id)}`;
                openConv({ conv_type: "private", conv_id: convId, title: c.username }, null);
                document.querySelector('.chat-tabs button[data-tab="conv"]').click();
            });
            el.querySelector(".chat-contact-del").addEventListener("click", async (e) => {
                e.stopPropagation();
                if (!confirm(`确定删除好友 ${c.username}？`)) return;
                const r = await apiPost("unfriend", { friend_id: c.id });
                if (!r.ok) {
                    alert(r.message || "删除失败");
                    return;
                }
                if (
                    currentConv &&
                    currentConv.conv_type === "private" &&
                    currentConv.peer_id === c.id
                ) {
                    currentConv = null;
                    document.getElementById("chatActive").classList.add("d-none");
                    document.getElementById("chatEmpty").classList.remove("d-none");
                }
                loadContacts();
                loadConversations();
            });
            list.appendChild(el);
        });
    }

    document.getElementById("btnSearch").addEventListener("click", async () => {
        const keyword = document.getElementById("searchKeyword").value.trim();
        const data = await apiPost("search", { keyword });
        const box = document.getElementById("searchResults");
        box.innerHTML = "";
        (data.users || []).forEach((u) => {
            const el = document.createElement("div");
            el.className = "chat-search-item";
            el.innerHTML = `<span>${esc(u.username)}</span>
                <button class="btn btn-sm btn-outline-primary">加好友</button>`;
            el.querySelector("button").addEventListener("click", async () => {
                const r = await apiPost("friend", { username: u.username });
                alert(r.message || (r.ok ? "已发送" : "失败"));
            });
            box.appendChild(el);
        });
    });

    async function loadFriendCheckboxes() {
        const data = await apiGet("contacts");
        const box = document.getElementById("friendCheckboxes");
        box.innerHTML = "";
        (data.contacts || []).forEach((c) => {
            const label = document.createElement("label");
            label.innerHTML = `<input type="checkbox" name="friend_ids" value="${c.id}" /> ${esc(c.username)}`;
            box.appendChild(label);
        });
    }

    document.getElementById("createGroupForm").addEventListener("submit", async (e) => {
        e.preventDefault();
        const form = e.target;
        const name = form.name.value.trim();
        const friend_ids = [...form.querySelectorAll('input[name="friend_ids"]:checked')].map((x) => x.value);
        const digital_aliases = [...form.querySelectorAll('input[name="digital_aliases"]:checked')].map((x) => x.value);
        const r = await apiPost("group", { name, friend_ids, digital_aliases });
        if (r.ok) {
            alert("群聊创建成功");
            loadConversations();
            document.querySelector('.chat-tabs button[data-tab="conv"]').click();
        } else {
            alert(r.message || "创建失败");
        }
    });

    document.getElementById("sendForm").addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!currentConv) return;
        const input = document.getElementById("messageInput");
        const content = input.value.trim();
        if (!content) return;
        const r = await apiPost("send", {
            conv_type: currentConv.conv_type,
            conv_id: currentConv.conv_id,
            content,
        });
        input.value = "";
        await loadMessages(false);
        if (r.digital_replies && r.digital_replies.length) {
            await loadMessages(false);
        }
    });

    document.querySelectorAll("#emojiBar button").forEach((btn) => {
        btn.addEventListener("click", () => {
            const input = document.getElementById("messageInput");
            input.value += btn.dataset.emoji;
            input.focus();
        });
    });

    document.getElementById("btnAttach").addEventListener("click", () => {
        document.getElementById("fileInput").click();
    });

    document.getElementById("fileInput").addEventListener("change", async () => {
        if (!currentConv) return alert("请先选择会话");
        const file = document.getElementById("fileInput").files[0];
        if (!file) return;
        const fd = new FormData();
        fd.append("_xsrf", getXsrf());
        fd.append("file", file);
        fd.append("conv_type", currentConv.conv_type);
        fd.append("conv_id", currentConv.conv_id);
        const res = await fetch("/portal/chat/upload", { method: "POST", body: fd });
        const data = await res.json();
        if (data.ok) await loadMessages(false);
        else alert(data.message || "上传失败");
        document.getElementById("fileInput").value = "";
    });

    async function refreshServer() {
        const data = await apiGet("server");
        if (data.server) {
            document.getElementById("serverBadge").textContent = data.server.name;
        }
    }

    loadConversations();
    refreshServer();
    setInterval(refreshServer, 30000);
})();
