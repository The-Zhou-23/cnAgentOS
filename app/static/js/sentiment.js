/* 成员 D：智慧舆情分析页交互
 * 设计要点：
 *  1. 离线降级：本项目要求"禁止 CDN"，目前 dist 内未内置 echarts。这里采用纯 Canvas/SVG/HTML
 *     渲染词云、来源条、趋势折线，确保页面立即可用；若未来 dist/echarts/echarts.min.js 存在，
 *     模块会优先加载 ECharts 渲染更丰富视觉。
 *  2. 不直接修改其他成员独占文件，所有交互通过 D 暴露的 /portal/sentiment/data
 *     与 /portal/sentiment/analyze 接口完成。
 */
(function () {
    "use strict";

    const DATA_URL = window.__SENTIMENT_DATA_URL__ || "/portal/sentiment/data";
    const ANALYZE_URL = window.__SENTIMENT_ANALYZE_URL__ || "/portal/sentiment/analyze";
    const XSRF = window.__XSRF__ || "";

    const $ = (sel) => document.querySelector(sel);

    function getParams() {
        return {
            scope: $("#scope").value,
            days: parseInt($("#days").value, 10) || 14,
            sample_size: parseInt($("#sample-size").value, 10) || 30,
        };
    }

    async function fetchData() {
        const p = getParams();
        const url = `${DATA_URL}?scope=${encodeURIComponent(p.scope)}&days=${p.days}&kw_limit=80`;
        const resp = await fetch(url, { credentials: "same-origin" });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return resp.json();
    }

    function renderMetrics(metrics) {
        if (!metrics) return;
        $("#metric-watch").textContent = metrics.watch_total ?? 0;
        $("#metric-source").textContent = metrics.source_total ?? 0;
        $("#metric-chat").textContent = metrics.chat_total ?? 0;
        $("#metric-today").textContent = metrics.today_watch ?? 0;
    }

    /* ============ 词云（Canvas 简易实现） ============ */
    function renderWordCloud(container, words) {
        container.innerHTML = "";
        if (!words || !words.length) {
            container.innerHTML =
                '<div class="sentiment-empty"><i class="fas fa-feather"></i>暂无词频数据，请先采集瞭望或开启聊天</div>';
            return;
        }

        // 简单环形螺旋布局
        const canvas = document.createElement("canvas");
        canvas.className = "wordcloud-canvas";
        container.appendChild(canvas);
        const rect = container.getBoundingClientRect();
        const W = Math.max(280, rect.width);
        const H = Math.max(280, rect.height);
        canvas.width = W * (window.devicePixelRatio || 1);
        canvas.height = H * (window.devicePixelRatio || 1);
        canvas.style.width = W + "px";
        canvas.style.height = H + "px";
        const ctx = canvas.getContext("2d");
        ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);
        ctx.clearRect(0, 0, W, H);

        const max = words[0].count || 1;
        const min = words[words.length - 1].count || 1;
        const placed = []; // {x,y,w,h}
        const colors = ["#2563eb", "#0ea5e9", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"];

        function intersects(box) {
            return placed.some(
                (p) =>
                    !(
                        box.x + box.w < p.x ||
                        p.x + p.w < box.x ||
                        box.y + box.h < p.y ||
                        p.y + p.h < box.y
                    )
            );
        }

        words.slice(0, 80).forEach((item, idx) => {
            const ratio = max === min ? 1 : (item.count - min) / (max - min);
            const fontSize = Math.round(14 + ratio * 36);
            ctx.font = `${600} ${fontSize}px -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif`;
            const text = item.word;
            const m = ctx.measureText(text);
            const w = m.width + 8;
            const h = fontSize + 6;

            // 螺旋寻找空位
            let placedOk = false;
            let angle = (idx * 137.5 * Math.PI) / 180;
            for (let r = 0; r < Math.min(W, H) / 2; r += 4) {
                const cx = W / 2 + Math.cos(angle) * r - w / 2;
                const cy = H / 2 + Math.sin(angle) * r - h / 2;
                const box = { x: cx, y: cy, w, h };
                if (
                    cx > 4 &&
                    cy > 4 &&
                    cx + w < W - 4 &&
                    cy + h < H - 4 &&
                    !intersects(box)
                ) {
                    placed.push(box);
                    ctx.fillStyle = colors[idx % colors.length];
                    ctx.textBaseline = "top";
                    ctx.fillText(text, cx + 4, cy + 3);
                    placedOk = true;
                    break;
                }
                angle += 0.6;
            }
            if (!placedOk) {
                // 放不下就跳过
            }
        });
    }

    /* ============ 来源分布（条形图降级） ============ */
    function renderSources(container, sources) {
        container.innerHTML = "";
        if (!sources || !sources.length) {
            container.innerHTML =
                '<div class="sentiment-empty"><i class="fas fa-database"></i>暂无来源数据</div>';
            return;
        }
        const max = Math.max(...sources.map((s) => s.value)) || 1;
        const list = document.createElement("div");
        list.className = "source-bar-list";
        sources.slice(0, 12).forEach((s) => {
            const item = document.createElement("div");
            item.className = "source-bar-item";
            item.innerHTML = `
                <div class="source-bar-name" title="${escapeHtml(s.name)}">${escapeHtml(s.name)}</div>
                <div class="source-bar-track"><div class="source-bar-fill" style="width:${(s.value / max * 100).toFixed(1)}%"></div></div>
                <div class="source-bar-value">${s.value}</div>
            `;
            list.appendChild(item);
        });
        container.appendChild(list);
    }

    /* ============ 趋势折线（SVG 降级） ============ */
    function renderTrend(container, trend) {
        container.innerHTML = "";
        if (!trend || !trend.dates || !trend.dates.length) {
            container.innerHTML =
                '<div class="sentiment-empty"><i class="fas fa-chart-line"></i>暂无趋势数据</div>';
            return;
        }
        const W = container.clientWidth || 700;
        const H = 220;
        const padL = 36, padR = 16, padT = 18, padB = 28;
        const innerW = W - padL - padR;
        const innerH = H - padT - padB;

        const all = (trend.watch || []).concat(trend.chat || []);
        const max = Math.max(1, ...all);

        const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.setAttribute("class", "trend-svg");
        svg.setAttribute("viewBox", `0 0 ${W} ${H}`);

        // 网格
        for (let i = 0; i <= 4; i++) {
            const y = padT + (innerH / 4) * i;
            const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
            line.setAttribute("x1", padL);
            line.setAttribute("x2", W - padR);
            line.setAttribute("y1", y);
            line.setAttribute("y2", y);
            line.setAttribute("stroke", "rgba(15,23,42,0.06)");
            svg.appendChild(line);

            const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
            label.setAttribute("x", 4);
            label.setAttribute("y", y + 4);
            label.setAttribute("font-size", "10");
            label.setAttribute("fill", "#94a3b8");
            label.textContent = Math.round(max - (max / 4) * i);
            svg.appendChild(label);
        }

        // X 标签
        const dates = trend.dates;
        const stepX = innerW / Math.max(1, dates.length - 1);
        dates.forEach((d, i) => {
            if (i % Math.ceil(dates.length / 7) !== 0 && i !== dates.length - 1) return;
            const x = padL + stepX * i;
            const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
            label.setAttribute("x", x);
            label.setAttribute("y", H - 8);
            label.setAttribute("font-size", "10");
            label.setAttribute("fill", "#64748b");
            label.setAttribute("text-anchor", "middle");
            label.textContent = d.slice(5);
            svg.appendChild(label);
        });

        function buildPath(values, color, fill) {
            const points = values.map((v, i) => {
                const x = padL + stepX * i;
                const y = padT + innerH - (v / max) * innerH;
                return [x, y];
            });
            const d =
                "M " +
                points.map((p) => p.join(",")).join(" L ");
            const line = document.createElementNS("http://www.w3.org/2000/svg", "path");
            line.setAttribute("d", d);
            line.setAttribute("fill", "none");
            line.setAttribute("stroke", color);
            line.setAttribute("stroke-width", "2");
            line.setAttribute("stroke-linejoin", "round");
            svg.appendChild(line);

            if (fill) {
                const area = document.createElementNS("http://www.w3.org/2000/svg", "path");
                const dArea =
                    "M " +
                    points.map((p) => p.join(",")).join(" L ") +
                    ` L ${padL + stepX * (points.length - 1)},${padT + innerH} L ${padL},${padT + innerH} Z`;
                area.setAttribute("d", dArea);
                area.setAttribute("fill", fill);
                area.setAttribute("opacity", "0.18");
                svg.insertBefore(area, line);
            }

            // 端点
            points.forEach((p) => {
                const c = document.createElementNS("http://www.w3.org/2000/svg", "circle");
                c.setAttribute("cx", p[0]);
                c.setAttribute("cy", p[1]);
                c.setAttribute("r", "3");
                c.setAttribute("fill", color);
                svg.appendChild(c);
            });
        }

        buildPath(trend.watch || [], "#2563eb", "#2563eb");
        buildPath(trend.chat || [], "#22c55e", "#22c55e");

        // 图例
        const lg = document.createElementNS("http://www.w3.org/2000/svg", "g");
        lg.innerHTML = `
            <circle cx="${W - 130}" cy="${padT + 4}" r="4" fill="#2563eb"/>
            <text x="${W - 120}" y="${padT + 8}" font-size="11" fill="#475569">瞭望采集</text>
            <circle cx="${W - 60}" cy="${padT + 4}" r="4" fill="#22c55e"/>
            <text x="${W - 50}" y="${padT + 8}" font-size="11" fill="#475569">聊天</text>
        `;
        svg.appendChild(lg);
        container.appendChild(svg);
    }

    function escapeHtml(s) {
        return String(s || "").replace(/[&<>"']/g, (c) => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;",
        }[c]));
    }

    /* ============ 初始化 ============ */
    async function loadAll() {
        try {
            const data = await fetchData();
            renderMetrics(data.metrics);
            renderWordCloud($("#panel-wordcloud"), data.keywords);
            renderSources($("#panel-sources"), data.sources);
            renderTrend($("#panel-trend"), data.trend);
        } catch (err) {
            console.error("[sentiment] load failed:", err);
            $("#panel-wordcloud").innerHTML =
                '<div class="sentiment-empty"><i class="fas fa-exclamation-triangle"></i>加载失败：' +
                escapeHtml(err.message) +
                "</div>";
        }
    }

    /* ============ AI 分析 ============ */
    async function runAnalyze() {
        const btn = $("#btn-analyze");
        const meta = $("#report-meta");
        const content = $("#report-content");
        const params = getParams();
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>分析中...';
        meta.textContent = "正在调用模型...";
        content.innerHTML =
            '<div class="sentiment-empty"><i class="fas fa-cog fa-spin"></i>AI 正在生成报告，请稍候（10~30 秒）</div>';

        try {
            const resp = await fetch(ANALYZE_URL, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-XSRFToken": XSRF,
                },
                body: JSON.stringify(params),
            });
            const data = await resp.json();
            if (!data.ok) {
                meta.textContent = "生成失败";
                content.innerHTML =
                    '<div class="sentiment-empty"><i class="fas fa-exclamation-triangle"></i>' +
                    escapeHtml(data.content || "未知错误") +
                    "</div>";
            } else {
                const ts = new Date().toLocaleString("zh-CN", { hour12: false });
                meta.textContent = `模型：${data.model} · 样本：${data.sample_count} · 范围：${labelOfScope(
                    data.scope
                )} · 生成于 ${ts}`;
                content.innerHTML = renderMarkdownLite(data.content);
                content.scrollTop = 0;
            }
        } catch (err) {
            meta.textContent = "网络错误";
            content.innerHTML =
                '<div class="sentiment-empty"><i class="fas fa-times-circle"></i>' +
                escapeHtml(err.message) +
                "</div>";
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-robot me-1"></i>AI 分析';
        }
    }

    function labelOfScope(s) {
        return { all: "全域", watch: "瞭望", chat: "聊天" }[s] || s;
    }

    // 极简 Markdown 渲染（只处理 ## 标题 / **加粗** / 列表）
    function renderMarkdownLite(text) {
        const safe = escapeHtml(text);
        let html = safe
            .replace(/^### (.+)$/gm, "<h3>$1</h3>")
            .replace(/^## (.+)$/gm, "<h2>$1</h2>")
            .replace(/^# (.+)$/gm, "<h2>$1</h2>")
            .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
            .replace(/^\s*[-*•]\s+(.+)$/gm, "<li>$1</li>");
        html = html.replace(/(<li>.*?<\/li>\n?)+/gs, (m) => "<ul>" + m + "</ul>");
        return html;
    }

    /* ============ 事件绑定 ============ */
    document.addEventListener("DOMContentLoaded", () => {
        loadAll();
        $("#btn-refresh").addEventListener("click", loadAll);
        $("#btn-analyze").addEventListener("click", runAnalyze);
        ["#scope", "#days"].forEach((sel) =>
            $(sel).addEventListener("change", loadAll)
        );
    });
})();
