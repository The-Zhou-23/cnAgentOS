// 成员 D 独占：用户侧数字员工大厅交互脚本
// 功能：员工卡片点击填充 @别名、SSE 流式输出、清空对话、快捷提示、多轮对话历史。
(function () {
    const grid = document.getElementById('employeeGrid');
    const form = document.getElementById('chatForm');
    const input = document.getElementById('chatInput');
    const history = document.getElementById('chatHistory');
    const sendBtn = document.getElementById('sendBtn');
    const clearBtn = document.getElementById('clearBtn');

    // 多轮上下文：仅缓存模型路由相关的 user/assistant 文本，限制最近 20 条
    const conversation = [];
    const HISTORY_MAX = 20;

    // 这些前缀来自 chat_stream 的状态行，不应进入 conversation 上下文
    const STATUS_PREFIXES = [
        '已匹配数字员工：',
        '请求天气接口：',
        '请求音乐接口：',
        '处理完成',
        '执行失败',
        '未找到数字员工',
        '请输入 @别名',
        '未识别出城市',
        '未找到对应接口',
        '未找到可用模型',
    ];

    function isStatusLine(text) {
        if (!text) return true;
        return STATUS_PREFIXES.some(p => text.startsWith(p));
    }

    function getXsrf() {
        const tokenInput = form.querySelector('input[name="_xsrf"]');
        return tokenInput ? tokenInput.value : '';
    }

    function appendMsg(role, text) {
        const wrap = document.createElement('div');
        wrap.className = 'de-msg ' + (role === 'user' ? 'de-msg-user' : 'de-msg-bot');
        const avatar = document.createElement('div');
        avatar.className = 'de-avatar';
        avatar.innerHTML = role === 'user'
            ? '<i class="fas fa-user"></i>'
            : '<i class="fas fa-robot"></i>';
        const bubble = document.createElement('div');
        bubble.className = 'de-bubble';
        bubble.textContent = text;
        wrap.appendChild(avatar);
        wrap.appendChild(bubble);
        history.appendChild(wrap);
        history.scrollTop = history.scrollHeight;
        return bubble;
    }

    // 员工卡片点击 → 填充 @别名
    if (grid) {
        grid.addEventListener('click', (e) => {
            const card = e.target.closest('.de-employee-card');
            if (!card) return;
            grid.querySelectorAll('.de-employee-card.active').forEach(el => el.classList.remove('active'));
            card.classList.add('active');
            const alias = card.dataset.alias;
            const cur = input.value.trim();
            const stripped = cur.replace(/^@\S+\s*/, '');
            input.value = `@${alias} ${stripped}`.trim();
            input.focus();
            const len = input.value.length;
            input.setSelectionRange(len, len);
        });
    }

    // 快捷提示标签
    document.querySelectorAll('.de-quick-tag').forEach(tag => {
        tag.addEventListener('click', () => {
            input.value = tag.dataset.tip || tag.textContent;
            input.focus();
        });
    });

    // 清空对话
    clearBtn?.addEventListener('click', () => {
        history.innerHTML = '';
        conversation.length = 0;
        appendMsg('bot', '会话已清空，可重新开始。');
    });

    form?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const message = input.value.trim();
        if (!message) return;
        appendMsg('user', message);
        input.value = '';
        sendBtn.disabled = true;
        const bubble = appendMsg('bot', '');

        // 构造发往后端的 history（只保留最近 HISTORY_MAX 条 user/assistant）
        const sentHistory = conversation.slice(-HISTORY_MAX);

        try {
            const formData = new FormData();
            formData.append('message', message);
            formData.append('history', JSON.stringify(sentHistory));
            formData.append('_xsrf', getXsrf());
            const resp = await fetch('/portal/digital-employee/chat', {
                method: 'POST',
                body: formData,
            });
            if (!resp.ok || !resp.body) {
                bubble.textContent = '请求失败：' + resp.status;
                return;
            }
            const reader = resp.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let buffer = '';
            let acc = '';
            const meaningfulChunks = []; // 收集非状态行，作为本轮 assistant 回复内容
            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const parts = buffer.split('\n\n');
                buffer = parts.pop() || '';
                for (const part of parts) {
                    const line = part.split('\n').find(x => x.startsWith('data: '));
                    if (!line) continue;
                    try {
                        const payload = JSON.parse(line.slice(6));
                        if (payload.message) {
                            acc += payload.message;
                            if (payload.message.length > 60 || /[。！？!?\n]$/.test(payload.message)) {
                                acc += '\n';
                            }
                            bubble.textContent = acc;
                            history.scrollTop = history.scrollHeight;
                            if (!isStatusLine(payload.message)) {
                                meaningfulChunks.push(payload.message);
                            }
                        }
                    } catch (err) {
                        // 忽略解析失败的心跳
                    }
                }
            }

            // 入历史：当前 user + 本轮模型/接口的"实质回答"
            conversation.push({ role: 'user', content: message });
            const assistantText = meaningfulChunks.join('').trim();
            if (assistantText) {
                conversation.push({ role: 'assistant', content: assistantText });
            }
            // 控制最大长度，防止 payload 过大
            while (conversation.length > HISTORY_MAX) conversation.shift();
        } catch (err) {
            bubble.textContent = '执行失败：' + err.message;
        } finally {
            sendBtn.disabled = false;
            input.focus();
        }
    });
})();
