# 成员 D 实现日志（智慧舆情 / 任务三）

> 学号：202308321 ｜ 姓名：方乐 ｜ 主责：智慧舆情（任务三）
> 关联文档：`团队任务2-5-任务分配.md` 第七章

---

## 一、本次交付概览

| 任务 | 文件 | 状态 |
|------|------|------|
| D3-1 离线 ECharts/词云替代方案 | `app/static/js/sentiment.js`、`app/static/js/bigscreen.js`（纯 Canvas + SVG 离线实现） | ✅ |
| D3-2 3D 地球 + 指标卡 + 词云（聊天/瞭望切换） | `app/templates/portal/bigscreen.html` + `bigscreen.js`（自研 Canvas Wireframe Globe，可拖拽旋转） | ✅ |
| D3-3 舆情 AI 分析页 | `app/templates/portal/sentiment.html` + `app/models/sentiment.py:SentimentRepository.generate_report` | ✅ |
| D3-4 门户入口 | `app/templates/index.html` + `app/templates/portal_base.html` 增加「智慧舆情」卡片与导航 | ✅ |
| D3-5 数据接口对接 | `SentimentRepository.aggregate_keywords/sources/trend/geo`，对 E、A 接口预留 hasattr 优先调用 | ✅ |
| D3-6 路由表 + 演示 | 见下方「二、路由表」 | ✅ |

> **可演示路径**：登录任意普通用户 → 首页点击「智慧舆情」卡片 → 进入分析页查看词云 / 来源 / 趋势 / AI 报告 → 点右上「进入数智大屏」查看 3D 地球与全屏可视化。

---

## 二、路由表（提交给成员 C）

| 方法 | 路径 | Handler | 说明 |
|------|------|---------|------|
| GET  | `/portal/bigscreen`         | `PortalBigscreenHandler`        | 数智大屏（独立 body，3D 地球 + 词云 + 指标 + 趋势 + 实时 feed） |
| GET  | `/portal/sentiment`         | `PortalSentimentHandler`        | 舆情分析页（指标 + 词云 + 来源 + 趋势 + AI 报告） |
| GET  | `/portal/sentiment/data`    | `PortalSentimentDataHandler`    | 聚合数据 JSON：`scope=all|watch|chat`，`days`，`kw_limit` |
| POST | `/portal/sentiment/analyze` | `PortalSentimentAnalyzeHandler` | 触发 AI 分析（同步），Body：`{scope, days, sample_size}` |

均已在 `app.py` 注册，登录守卫复用 `@tornado.web.authenticated`。

---

## 三、文件清单（D 独占）

```
app/models/sentiment.py                       # 仓储层：抽样、聚合、AI 分析
app/controllers/portal_sentiment.py           # 4 个 Handler
app/templates/portal/sentiment.html           # 舆情分析页
app/templates/portal/bigscreen.html           # 数智大屏（独立 body）
app/static/css/sentiment.css                  # 浅色 + 深色（大屏）双主题
app/static/js/sentiment.js                    # 分析页交互（词云/来源/趋势/AI 报告）
app/static/js/bigscreen.js                    # 大屏交互（Canvas 3D 地球 + 词云 + 趋势 + 滚动 feed）
log_D.md                                      # 本日志
```

仅在以下"非 D 独占"文件做了**最小补丁**（向 C 同步路由 + 入口卡片）：

- `app.py`：新增 4 条路由（标注 `# 成员 D：智慧舆情`）
- `app/templates/portal_base.html`：导航栏新增「智慧舆情」入口
- `app/templates/index.html`：首页功能卡片新增「智慧舆情」卡片

> 上述跨成员文件的修改边界已严格限制在「新增」而非修改既有逻辑，便于 C 合并。

---

## 四、与其他成员的接口约定

### 4.1 D 调 E（瞭望）

```python
# 优先调用 E 提供的稳定接口（若存在）：
WatchtowerRepository.aggregate_keywords(limit) -> List[{word, count}]
```

若 E 暂未提供，D 会自动降级为本地分词聚合 `watch_records` 表（`title` + `keyword` 字段）。
切换无需任何改动，因此 E 何时落地不阻塞 D。

### 4.2 D 调 A（聊天）

```python
# 优先调用 A 提供的稳定接口（若存在）：
ChatRepository.sample_messages(limit, days) -> List[{content, sender_name, created_at, ...}]
```

若 A 暂未提供，D 兜底使用以下"只读 SQL"，**不修改 chat 表结构**：

```sql
select content from chat_messages where msg_type='text' and created_at >= ? limit ?
```

### 4.3 D 调 模型层（公共）

```python
ModelServiceRepository.chat(model_id, messages, stream=False) -> str  # 阻塞调用
ModelServiceRepository.get_system_model() -> sqlite3.Row
ModelServiceRepository.update_tokens(...)
```

`SentimentRepository.generate_report` 内部已自动选择系统默认模型并累计 Token。
**未修改** `model_service.py`、`digital_employee.py`，符合「D 仅调用、不修改」的约定。

---

## 五、运行验证

| 路由 | 状态码 | 说明 |
|------|--------|------|
| GET `/portal/bigscreen`         | 200 | 大屏 HTML 正常渲染 |
| GET `/portal/sentiment`         | 200 | 分析页 HTML 正常渲染 |
| GET `/portal/sentiment/data`    | 200 | 返回 metrics / keywords / sources / trend / geo 完整 JSON |
| POST `/portal/sentiment/analyze`| 200 | 调用系统默认模型生成结构化报告（已配置模型时） |

冒烟数据样例：

```
overview: {'watch_total': 39, 'source_total': 1, 'chat_total': 0, 'today_watch': 10}
keywords top: 四川农业大学(60) / 腾讯新闻(30) / 新闻(29) / 四川农业(16) / 大学(6) ...
geo: 3 个省份命中
trend: 7 天瞭望累计 39
```

---

## 六、技术决策记录

1. **未引入 ECharts/echarts-gl**：`requirement.txt` 第 5 条「禁止 CDN」+ `dist/` 目前未内置 ECharts，
   引入新二进制依赖需单独审批。改用 **纯 Canvas/SVG 离线实现**（自研 Wireframe Globe + 螺旋词云布局 + SVG 折线），保证项目可立即演示。
   未来若 dist 加入 echarts，可在 JS 入口处探测加载，**不需要改 D 模板**。

2. **不修改其他成员独占文件**：仅在 `app.py`、`portal_base.html`、`index.html` 做新增式补丁；
   严格遵守 v2.0 分工边界。

3. **Prompt 模板冻结**：见 `SentimentRepository.PROMPT_TEMPLATE`，固定四节小标题（摘要 / 热点 / 风险 / 建议），便于演示稳定性。

---

*版本：v1.0 ｜ 日期：2026-05-28*
