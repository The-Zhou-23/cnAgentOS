/* 成员 D：数智大屏脚本
 *
 * 实现说明：
 *  - 3D 地球：使用纯 Canvas 绘制经纬网 + 旋转 + 地域散点（Wireframe Globe）。
 *    原因：项目要求"禁止 CDN"，dist 目录尚未内置 ECharts-GL；离线版本需保证立即可演示。
 *    若未来 dist/echarts/echarts.min.js + echarts-gl.min.js 存在，可在此处替换为 ECharts。
 *  - 词云、来源条、趋势线：复用 sentiment.js 的渲染策略（独立实现以便深色主题）。
 *  - 数据 30 秒自动刷新一次。
 */
(function () {
    "use strict";

    const DATA_URL = window.__SENTIMENT_DATA_URL__ || "/portal/sentiment/data";
    const $ = (sel) => document.querySelector(sel);

    let currentScope = "all";
    let cachedData = null;

    /* ============ 时钟 ============ */
    function tickClock() {
        const now = new Date();
        const pad = (n) => String(n).padStart(2, "0");
        $("#clock").textContent =
            `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ` +
            `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
    }
    setInterval(tickClock, 1000);
    tickClock();

    /* ============ 3D 地球（Wireframe + 散点） ============ */
    class Globe {
        constructor(canvas) {
            this.canvas = canvas;
            this.ctx = canvas.getContext("2d");
            this.points = []; // {lat, lon, value, name}
            this.rotation = 0;
            this.tilt = 0.35; // 约 20°
            this.resize();
            window.addEventListener("resize", () => this.resize());
            this.dragging = false;
            this.lastX = 0;
            canvas.addEventListener("mousedown", (e) => {
                this.dragging = true;
                this.lastX = e.clientX;
            });
            window.addEventListener("mouseup", () => (this.dragging = false));
            window.addEventListener("mousemove", (e) => {
                if (!this.dragging) return;
                const dx = e.clientX - this.lastX;
                this.lastX = e.clientX;
                this.rotation += dx * 0.01;
            });
            this.animate();
        }

        resize() {
            const rect = this.canvas.parentElement.getBoundingClientRect();
            const dpr = window.devicePixelRatio || 1;
            this.W = rect.width;
            this.H = rect.height;
            this.canvas.width = this.W * dpr;
            this.canvas.height = this.H * dpr;
            this.canvas.style.width = this.W + "px";
            this.canvas.style.height = this.H + "px";
            this.ctx.setTransform(1, 0, 0, 1, 0, 0);
            this.ctx.scale(dpr, dpr);
            this.cx = this.W / 2;
            this.cy = this.H / 2;
            this.radius = Math.min(this.W, this.H) * 0.38;
        }

        setPoints(points) {
            this.points = points || [];
        }

        // 经纬度 -> 屏幕坐标（含旋转 + 倾斜）
        project(lat, lon) {
            const latR = (lat * Math.PI) / 180;
            const lonR = (lon * Math.PI) / 180 + this.rotation;
            // 球面坐标
            let x = Math.cos(latR) * Math.sin(lonR);
            let y = Math.sin(latR);
            let z = Math.cos(latR) * Math.cos(lonR);

            // 绕 X 轴倾斜
            const cy = Math.cos(this.tilt);
            const sy = Math.sin(this.tilt);
            const ny = y * cy - z * sy;
            const nz = y * sy + z * cy;
            y = ny;
            z = nz;

            return {
                x: this.cx + x * this.radius,
                y: this.cy - y * this.radius,
                z, // > 0 表示朝向观察者
            };
        }

        drawSphereBg() {
            const ctx = this.ctx;
            const grd = ctx.createRadialGradient(
                this.cx - this.radius * 0.4,
                this.cy - this.radius * 0.4,
                this.radius * 0.1,
                this.cx,
                this.cy,
                this.radius
            );
            grd.addColorStop(0, "rgba(56,189,248,0.18)");
            grd.addColorStop(0.6, "rgba(15,30,65,0.55)");
            grd.addColorStop(1, "rgba(7,14,36,0.95)");
            ctx.beginPath();
            ctx.arc(this.cx, this.cy, this.radius, 0, Math.PI * 2);
            ctx.fillStyle = grd;
            ctx.fill();

            // 外发光
            ctx.beginPath();
            ctx.arc(this.cx, this.cy, this.radius + 6, 0, Math.PI * 2);
            ctx.strokeStyle = "rgba(56,189,248,0.35)";
            ctx.lineWidth = 1.2;
            ctx.stroke();
        }

        drawGrid() {
            const ctx = this.ctx;
            ctx.strokeStyle = "rgba(56,189,248,0.22)";
            ctx.lineWidth = 0.6;

            // 经线
            for (let lon = -180; lon < 180; lon += 20) {
                ctx.beginPath();
                let started = false;
                for (let lat = -90; lat <= 90; lat += 4) {
                    const p = this.project(lat, lon);
                    if (p.z < -0.05) {
                        started = false;
                        continue;
                    }
                    if (!started) {
                        ctx.moveTo(p.x, p.y);
                        started = true;
                    } else {
                        ctx.lineTo(p.x, p.y);
                    }
                }
                ctx.stroke();
            }

            // 纬线
            for (let lat = -60; lat <= 60; lat += 20) {
                ctx.beginPath();
                let started = false;
                for (let lon = -180; lon <= 180; lon += 4) {
                    const p = this.project(lat, lon);
                    if (p.z < -0.05) {
                        started = false;
                        continue;
                    }
                    if (!started) {
                        ctx.moveTo(p.x, p.y);
                        started = true;
                    } else {
                        ctx.lineTo(p.x, p.y);
                    }
                }
                ctx.stroke();
            }
        }

        drawPoints() {
            const ctx = this.ctx;
            if (!this.points.length) return;
            const max = this.points.reduce(
                (m, p) => Math.max(m, p.value && p.value[2] ? p.value[2] : 0),
                1
            );
            this.points.forEach((pt) => {
                if (!pt.value) return;
                const [lon, lat, val] = pt.value;
                const p = this.project(lat, lon);
                if (p.z < -0.05) return; // 背面不画
                const ratio = val / max;
                const r = 3 + ratio * 7;

                // 外圈光晕
                ctx.beginPath();
                ctx.arc(p.x, p.y, r * 2.5, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(56,189,248,${0.08 + ratio * 0.18})`;
                ctx.fill();

                // 主散点
                ctx.beginPath();
                ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
                const grd = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r);
                grd.addColorStop(0, "#fef3c7");
                grd.addColorStop(0.5, "#f59e0b");
                grd.addColorStop(1, "rgba(239,68,68,0.4)");
                ctx.fillStyle = grd;
                ctx.fill();

                // 标签：仅前置半球 & 高频显示
                if (p.z > 0.45 && val >= max * 0.35) {
                    ctx.fillStyle = "#e2e8f0";
                    ctx.font = "11px -apple-system, sans-serif";
                    ctx.fillText(`${pt.name} ${val}`, p.x + r + 4, p.y + 4);
                }
            });
        }

        animate() {
            const loop = () => {
                if (!this.dragging) {
                    this.rotation += 0.002;
                }
                this.ctx.clearRect(0, 0, this.W, this.H);
                this.drawSphereBg();
                this.drawGrid();
                this.drawPoints();
                requestAnimationFrame(loop);
            };
            requestAnimationFrame(loop);
        }
    }

    let globe = null;

    /* ============ 词云（深色版） ============ */
    function renderWordCloudCanvas(canvas, words) {
        const rect = canvas.parentElement.getBoundingClientRect();
        const W = Math.max(220, rect.width);
        const H = Math.max(220, rect.height);
        const dpr = window.devicePixelRatio || 1;
        canvas.width = W * dpr;
        canvas.height = H * dpr;
        canvas.style.width = W + "px";
        canvas.style.height = H + "px";
        const ctx = canvas.getContext("2d");
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.scale(dpr, dpr);
        ctx.clearRect(0, 0, W, H);

        if (!words || !words.length) {
            ctx.fillStyle = "#64748b";
            ctx.font = "13px -apple-system, sans-serif";
            ctx.textAlign = "center";
            ctx.fillText("暂无词频数据", W / 2, H / 2);
            return;
        }

        const max = words[0].count || 1;
        const min = words[words.length - 1].count || 1;
        const colors = ["#38bdf8", "#818cf8", "#22c55e", "#f59e0b", "#f472b6", "#a78bfa"];
        const placed = [];

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

        words.slice(0, 60).forEach((item, idx) => {
            const ratio = max === min ? 1 : (item.count - min) / (max - min);
            const fontSize = Math.round(12 + ratio * 28);
            ctx.font = `700 ${fontSize}px -apple-system, "PingFang SC", sans-serif`;
            const text = item.word;
            const m = ctx.measureText(text);
            const w = m.width + 8;
            const h = fontSize + 6;
            let angle = (idx * 137.5 * Math.PI) / 180;
            for (let r = 0; r < Math.min(W, H) / 2; r += 4) {
                const cx = W / 2 + Math.cos(angle) * r - w / 2;
                const cy = H / 2 + Math.sin(angle) * r - h / 2;
                const box = { x: cx, y: cy, w, h };
                if (cx > 4 && cy > 4 && cx + w < W - 4 && cy + h < H - 4 && !intersects(box)) {
                    placed.push(box);
                    ctx.fillStyle = colors[idx % colors.length];
                    ctx.shadowColor = colors[idx % colors.length];
                    ctx.shadowBlur = 8;
                    ctx.textBaseline = "top";
                    ctx.fillText(text, cx + 4, cy + 3);
                    ctx.shadowBlur = 0;
                    break;
                }
                angle += 0.6;
            }
        });
    }

    /* ============ 来源（深色） ============ */
    function renderSourcesDark(container, sources) {
        container.innerHTML = "";
        if (!sources || !sources.length) {
            container.innerHTML = '<div style="color:#64748b;text-align:center;padding:20px;">暂无来源</div>';
            return;
        }
        const max = Math.max(...sources.map((s) => s.value)) || 1;
        sources.slice(0, 12).forEach((s) => {
            const el = document.createElement("div");
            el.className = "bigscreen-source-item";
            el.innerHTML = `
                <div class="name" title="${escapeHtml(s.name)}">${escapeHtml(s.name)}</div>
                <div class="track"><div class="fill" style="width:${(s.value / max * 100).toFixed(1)}%"></div></div>
                <div class="value">${s.value}</div>
            `;
            container.appendChild(el);
        });
        $("#src-total").textContent = sources.length + " 项";
    }

    /* ============ 趋势 SVG（深色） ============ */
    function renderTrendDark(svg, trend) {
        svg.innerHTML = "";
        if (!trend || !trend.dates || !trend.dates.length) return;
        const W = svg.clientWidth || 600;
        const H = svg.clientHeight || 200;
        const padL = 28, padR = 12, padT = 14, padB = 22;
        const innerW = W - padL - padR;
        const innerH = H - padT - padB;
        const all = (trend.watch || []).concat(trend.chat || []);
        const max = Math.max(1, ...all);

        svg.setAttribute("viewBox", `0 0 ${W} ${H}`);

        for (let i = 0; i <= 4; i++) {
            const y = padT + (innerH / 4) * i;
            const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
            line.setAttribute("x1", padL);
            line.setAttribute("x2", W - padR);
            line.setAttribute("y1", y);
            line.setAttribute("y2", y);
            line.setAttribute("stroke", "rgba(56,189,248,0.12)");
            svg.appendChild(line);
            const t = document.createElementNS("http://www.w3.org/2000/svg", "text");
            t.setAttribute("x", 4);
            t.setAttribute("y", y + 4);
            t.setAttribute("font-size", "10");
            t.setAttribute("fill", "#64748b");
            t.textContent = Math.round(max - (max / 4) * i);
            svg.appendChild(t);
        }

        const dates = trend.dates;
        const stepX = innerW / Math.max(1, dates.length - 1);
        dates.forEach((d, i) => {
            if (i % Math.ceil(dates.length / 7) !== 0 && i !== dates.length - 1) return;
            const x = padL + stepX * i;
            const t = document.createElementNS("http://www.w3.org/2000/svg", "text");
            t.setAttribute("x", x);
            t.setAttribute("y", H - 6);
            t.setAttribute("font-size", "10");
            t.setAttribute("fill", "#94a3b8");
            t.setAttribute("text-anchor", "middle");
            t.textContent = d.slice(5);
            svg.appendChild(t);
        });

        function buildPath(values, color) {
            const points = values.map((v, i) => {
                const x = padL + stepX * i;
                const y = padT + innerH - (v / max) * innerH;
                return [x, y];
            });
            const d = "M " + points.map((p) => p.join(",")).join(" L ");
            const line = document.createElementNS("http://www.w3.org/2000/svg", "path");
            line.setAttribute("d", d);
            line.setAttribute("fill", "none");
            line.setAttribute("stroke", color);
            line.setAttribute("stroke-width", "2");
            line.setAttribute("filter", "drop-shadow(0 0 6px " + color + ")");
            svg.appendChild(line);

            // 区域
            const area = document.createElementNS("http://www.w3.org/2000/svg", "path");
            const dArea =
                "M " +
                points.map((p) => p.join(",")).join(" L ") +
                ` L ${padL + stepX * (points.length - 1)},${padT + innerH} L ${padL},${padT + innerH} Z`;
            area.setAttribute("d", dArea);
            area.setAttribute("fill", color);
            area.setAttribute("opacity", "0.16");
            svg.insertBefore(area, line);

            points.forEach((p) => {
                const c = document.createElementNS("http://www.w3.org/2000/svg", "circle");
                c.setAttribute("cx", p[0]);
                c.setAttribute("cy", p[1]);
                c.setAttribute("r", "2.5");
                c.setAttribute("fill", color);
                svg.appendChild(c);
            });
        }
        buildPath(trend.watch || [], "#38bdf8");
        buildPath(trend.chat || [], "#22c55e");

        // 图例
        const lg = document.createElementNS("http://www.w3.org/2000/svg", "g");
        lg.innerHTML = `
            <circle cx="${W - 110}" cy="${padT + 4}" r="3.5" fill="#38bdf8"/>
            <text x="${W - 102}" y="${padT + 8}" font-size="10" fill="#cbd5f5">瞭望</text>
            <circle cx="${W - 60}" cy="${padT + 4}" r="3.5" fill="#22c55e"/>
            <text x="${W - 52}" y="${padT + 8}" font-size="10" fill="#cbd5f5">聊天</text>
        `;
        svg.appendChild(lg);
    }

    /* ============ 实时动态 feed（用关键词模拟滚动） ============ */
    function renderFeed(container, keywords, geo) {
        container.innerHTML = "";
        const items = [];
        (geo || []).slice(0, 8).forEach((g) => {
            items.push({
                src: "地域",
                text: `${g.name} 热度 ${g.value[2]}`,
            });
        });
        (keywords || []).slice(0, 12).forEach((k) => {
            items.push({
                src: "关键词",
                text: `${k.word} 出现 ${k.count} 次`,
            });
        });
        items.sort(() => Math.random() - 0.5);
        items.slice(0, 18).forEach((it) => {
            const el = document.createElement("div");
            el.className = "bigscreen-feed-item";
            el.innerHTML = `<span class="src">[${it.src}]</span>${escapeHtml(it.text)}`;
            container.appendChild(el);
        });
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

    /* ============ 主流程 ============ */
    async function loadAndRender() {
        try {
            const url = `${DATA_URL}?scope=${encodeURIComponent(currentScope)}&days=14&kw_limit=80`;
            const resp = await fetch(url, { credentials: "same-origin" });
            const data = await resp.json();
            cachedData = data;

            // 指标
            const m = data.metrics || {};
            $("#m-watch").textContent = m.watch_total ?? 0;
            $("#m-source").textContent = m.source_total ?? 0;
            $("#m-chat").textContent = m.chat_total ?? 0;
            $("#m-today").textContent = m.today_watch ?? 0;

            // 地球散点
            if (globe) globe.setPoints(data.geo || []);

            // 词云
            renderWordCloudCanvas($("#bs-wordcloud"), data.keywords);

            // 来源
            renderSourcesDark($("#bs-sources"), data.sources);

            // 趋势
            renderTrendDark($("#bs-trend"), data.trend);

            // feed
            renderFeed($("#bs-feed"), data.keywords, data.geo);
        } catch (err) {
            console.error("[bigscreen] load failed:", err);
        }
    }

    document.addEventListener("DOMContentLoaded", () => {
        const canvas = $("#globe-canvas");
        globe = new Globe(canvas);

        $("#scope-switch").addEventListener("change", (e) => {
            currentScope = e.target.value;
            loadAndRender();
        });

        loadAndRender();
        // 30 秒自动刷新
        setInterval(loadAndRender, 30 * 1000);

        // 词云每 60 秒打散重排（保持视觉变化）
        setInterval(() => {
            if (cachedData && cachedData.keywords) {
                const shuffled = cachedData.keywords.slice().sort(() => Math.random() - 0.5);
                renderWordCloudCanvas($("#bs-wordcloud"), shuffled);
            }
        }, 60 * 1000);
    });
})();
