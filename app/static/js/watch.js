/**
 * 智能瞭望 - 前端交互脚本
 * 用于管理侧采集页面和用户侧浏览页面的交互逻辑
 */

// 自动初始化
document.addEventListener('DOMContentLoaded', function() {
    initWatchSources();
    initWatchCollect();
    initWatchFilter();
});

/**
 * 初始化采集源开关
 */
function initWatchSources() {
    const switches = document.querySelectorAll('.source-switch');
    if (!switches.length) return;

    switches.forEach(switchEl => {
        switchEl.addEventListener('change', handleSourceToggle);
    });

    // 配置输入框自动保存
    const configInputs = document.querySelectorAll('.config-input');
    configInputs.forEach(input => {
        input.addEventListener('change', handleConfigSave);
    });

    // 初始化添加采集源模态框
    initAddSourceModal();
}

/**
 * 初始化添加采集源模态框
 */
function initAddSourceModal() {
    const addSourceBtn = document.getElementById('addSourceBtn');
    const addSourceModal = document.getElementById('addSourceModal');
    const closeModal = document.getElementById('closeModal');
    const cancelBtn = document.getElementById('cancelBtn');

    // 打开模态框
    if (addSourceBtn && addSourceModal) {
        addSourceBtn.addEventListener('click', () => {
            addSourceModal.classList.add('show');
        });
    }

    // 关闭模态框
    const closeModalFn = () => {
        if (addSourceModal) {
            addSourceModal.classList.remove('show');
        }
    };

    if (closeModal) {
        closeModal.addEventListener('click', closeModalFn);
    }

    if (cancelBtn) {
        cancelBtn.addEventListener('click', closeModalFn);
    }

    // 点击遮罩关闭模态框
    if (addSourceModal) {
        addSourceModal.addEventListener('click', (e) => {
            if (e.target === addSourceModal) {
                closeModalFn();
            }
        });
    }

    // 添加采集源表单提交
    const addSourceForm = document.getElementById('addSourceForm');
    if (addSourceForm) {
        addSourceForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            try {
                const formData = new FormData(addSourceForm);
                const response = await fetch('/admin/watch-sources/create', {
                    method: 'POST',
                    body: formData
                });
                
                if (response.ok) {
                    closeModalFn();
                    addSourceForm.reset();
                    // 刷新页面或更新采集源列表
                    window.location.reload();
                } else {
                    console.error('添加采集源失败');
                }
            } catch (err) {
                console.error('添加采集源失败:', err);
            }
        });
    }
}

/**
 * 处理采集源开关切换
 */
async function handleSourceToggle(e) {
    const sourceId = e.target.dataset.sourceId;
    const isEnabled = e.target.checked ? 1 : 0;
    const card = e.target.closest('.source-card');
    
    // 更新卡片视觉状态
    if (isEnabled) {
        card.classList.add('enabled');
        card.classList.remove('disabled');
    } else {
        card.classList.add('disabled');
        card.classList.remove('enabled');
    }

    // 发送更新请求
    try {
        const formData = buildSourceFormData(card, isEnabled);
        await fetch(`/admin/watch-sources/update/${sourceId}`, {
            method: 'POST',
            body: formData
        });
    } catch (err) {
        console.error('更新采集源状态失败:', err);
        // 恢复开关状态
        e.target.checked = !isEnabled;
        card.classList.toggle('enabled');
        card.classList.toggle('disabled');
    }
}

/**
 * 处理配置保存
 */
async function handleConfigSave(e) {
    const sourceId = e.target.dataset.sourceId;
    const field = e.target.dataset.field;
    const card = e.target.closest('.source-card');
    const isEnabled = card.classList.contains('enabled');

    // max_pages 不保存到数据库
    if (field === 'max_pages') return;

    try {
        const formData = buildSourceFormData(card, isEnabled ? 1 : 0);
        await fetch(`/admin/watch-sources/update/${sourceId}`, {
            method: 'POST',
            body: formData
        });
    } catch (err) {
        console.error('保存配置失败:', err);
    }
}

/**
 * 构建采集源表单数据
 */
function buildSourceFormData(card, isEnabled) {
    const formData = new FormData();
    const xsrfInput = document.querySelector('[name="_xsrf"]');
    if (xsrfInput) {
        formData.append('_xsrf', xsrfInput.value);
    }
    
    formData.append('name', card.querySelector('h4').textContent);
    formData.append('source_code', card.querySelector('.source-code').textContent);
    formData.append('is_enabled', isEnabled);
    formData.append('collect_limit', card.querySelector('[data-field="collect_limit"]').value);
    formData.append('entry_urls', '[]');
    formData.append('headers', '{}');
    formData.append('keywords_label', '关键字');
    formData.append('page_param_name', 'pn');
    formData.append('page_step', '10');
    formData.append('note', card.querySelector('.source-note').textContent);
    
    return formData;
}

/**
 * 初始化采集表单
 */
function initWatchCollect() {
    const form = document.getElementById('collectForm');
    if (!form) return;

    const streamBox = document.getElementById('streamBox');
    const streamStatus = document.getElementById('streamStatus');
    const searchBtn = document.getElementById('searchBtn');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const prompt = document.getElementById('prompt').value.trim();
        if (!prompt) return;

        // 获取启用的采集源和配置
        const enabledSources = [];
        document.querySelectorAll('.source-card.enabled').forEach(card => {
            const sourceId = card.dataset.sourceId;
            const itemCount = card.querySelector('[data-field="collect_limit"]').value;
            const maxPages = card.querySelector('[data-field="max_pages"]').value;
            enabledSources.push({ sourceId, itemCount, maxPages });
        });

        if (enabledSources.length === 0) {
            streamBox.innerHTML = '<div class="stream-error"><i class="fas fa-exclamation-triangle"></i> 请至少启用一个采集源</div>';
            return;
        }

        // 禁用按钮，显示加载状态
        searchBtn.disabled = true;
        searchBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 采集中...';
        streamStatus.textContent = '采集中...';
        streamStatus.classList.add('active');
        streamBox.innerHTML = '';

        // 依次采集每个源
        for (const source of enabledSources) {
            streamBox.innerHTML += `<div class="stream-source-header"><i class="fas fa-database"></i> 采集源 #${source.sourceId}</div>`;
            
            const formData = new FormData();
            const xsrfInput = document.querySelector('[name="_xsrf"]');
            if (xsrfInput) {
                formData.append('_xsrf', xsrfInput.value);
            }
            formData.append('prompt', prompt);
            formData.append('source_id', source.sourceId);
            formData.append('item_count', source.itemCount);
            formData.append('max_pages', source.maxPages);

            try {
                const resp = await fetch('/admin/watch-collect', {
                    method: 'POST',
                    body: formData
                });

                if (!resp.ok) {
                    streamBox.innerHTML += `<div class="stream-error">请求失败</div>`;
                    continue;
                }

                const reader = resp.body.getReader();
                const decoder = new TextDecoder('utf-8');
                let buffer = '';

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
                                streamBox.innerHTML += `<div class="stream-line">${escapeHtml(payload.message)}</div>`;
                                streamBox.scrollTop = streamBox.scrollHeight;
                            }
                        } catch (err) {}
                    }
                }
            } catch (err) {
                streamBox.innerHTML += `<div class="stream-error">采集失败：${err.message}</div>`;
            }
        }

        // 恢复按钮状态
        searchBtn.disabled = false;
        searchBtn.innerHTML = '<i class="fas fa-bolt"></i> <span>开始采集</span>';
        streamStatus.textContent = '采集完成';
        streamStatus.classList.remove('active');
    });
}

/**
 * 初始化筛选功能
 */
function initWatchFilter() {
    const filterForm = document.querySelector('.watch-filter-form');
    if (!filterForm) return;

    // 回车提交
    const keywordInput = filterForm.querySelector('[name="keyword"]');
    if (keywordInput) {
        keywordInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                filterForm.submit();
            }
        });
    }
}

/**
 * HTML 转义
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
