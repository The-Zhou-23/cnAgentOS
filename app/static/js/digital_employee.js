// 成员 D 独占：用户侧数字员工大厅交互脚本
// 功能：员工卡片点击填充 @别名、SSE 流式输出、清空对话、快捷提示。
(function () {
    const grid = document.getElementById('employeeGrid');
    const form = document.getElementById('chatForm');
    const input = document.getElementById('chatInput');
    const history = document.getElementById('chatHistory');
    const sendBtn = document.getElementById('sendBtn');
    const clearBtn = document.getElementById('clearBtn');

    function getXsrf() {
        const tokenInput = form.querySelector('input[name="_xsrf"]');
        return tokenInput ? tokenInput.value : '';
    }

    function appendMsg(role, text) {
        const wrap = document.createElement('div');
        wrap.className = 'msg ' + role;
        const avatar = document.createElement('div');
        avatar.className = 'avatar';
        avatar.innerHTML = role === 'user'
            ? '<i class="fas fa-user"></i>'
            : '<i class="fas fa-robot"></i>';
        const bubble = document.createElement('div');
        bubble.className = 'bubble';
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
            const card = e.target.closest('.employee-card');
            if (!card) return;
            grid.querySelectorAll('.employee-card.active').forEach(el => el.classList.remove('active'));
            card.classList.add('active');
            const alias = card.dataset.alias;
            const cur = input.value.trim();
            const stripped = cur.replace(/^@\S+\s*/, '');
            input.value = `@${alias} ${stripped}`.trim();
            input.focus();
            // 把光标移到末尾
            const len = input.value.length;
            input.setSelectionRange(len, len);
        });
    }

    // 快捷提示标签
    document.querySelectorAll('.quick-tag').forEach(tag => {
        tag.addEventListener('click', () => {
            input.value = tag.dataset.tip || tag.textContent;
            input.focus();
        });
    });

    // 清空对话
    clearBtn?.addEventListener('click', () => {
        history.innerHTML = '';
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

        try {
            const formData = new FormData();
            formData.append('message', message);
            formData.append('_xsrf', getXsrf());
            const resp = await fetch('/portal/digital-employees/chat', {
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
                            acc += (acc && !acc.endsWith('\n') ? '' : '') + payload.message;
                            // 短消息逐条换行；长 delta 直接拼接（模型流式返回常见）
                            if (payload.message.length > 60 || /[。！？!?\n]$/.test(payload.message)) {
                                acc += '\n';
                            }
                            bubble.textContent = acc;
                            history.scrollTop = history.scrollHeight;
                        }
                    } catch (err) {
                        // 忽略解析失败的心跳
                    }
                }
            }
        } catch (err) {
            bubble.textContent = '执行失败：' + err.message;
        } finally {
            sendBtn.disabled = false;
            input.focus();
        }
    });
})();
