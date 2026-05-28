# cnAgentOS 项目开发日志

> **记录人**：xyh  
> **最后更新**：2026-05-26  
> **项目**：AI 智能瞭望与智能问数系统（cnAgentOS）  
> **参考文档**：`川农23级团队任务书.pdf`、`requirement.txt`、`团队任务一-任务分配.md`

---

## 一、项目概况

cnAgentOS 是基于 **Python 3.12 + Tornado 6.5.5 + SQLite3** 的 B/S 架构 Web 系统，采用 MVC 分层：

| 层级 | 目录 | 职责 |
|------|------|------|
| 入口 | `app.py` | 路由注册、服务启动、数据库初始化 |
| Controller | `app/controllers/` | 处理 HTTP 请求、鉴权、渲染模板 |
| Model | `app/models/` | 数据库访问与业务数据封装 |
| View | `app/templates/` | HTML 页面模板 |
| Static | `app/static/` | CSS、JS、本地化前端组件（Bootstrap / Font Awesome / layui） |

**运行方式**：在项目根目录执行 `python app.py`，默认端口 **10087**。

**演示账号**：

| 账号 | 密码 | 角色 | 入口 |
|------|------|------|------|
| `admin` | （项目初始化密码） | 超级管理员 | 登录页选「管理员」 |
| `user` | `123456` | 普通用户 | 登录页选「普通用户」 |

---

## 二、团队任务一进展总览

依据 `团队任务一-任务分配.md`，五人分工及当前状态如下：

| 成员 | 负责模块 | 状态 | 说明 |
|------|----------|------|------|
| **A（xyh）** | 基础架构、认证、用户门户 | ✅ 已完成 | 注册、门户布局、临时占位路由等 |
| **B** | 用户/角色/权限/功能管理后台 | 🟡 部分完成 | 用户/角色/权限 CRUD 已有，功能管理页待做 |
| **C** | 智能瞭望（采集 + 用户浏览） | 🟡 部分完成 | 后台采集已有，用户侧浏览待做 |
| **D** | 模型引擎、接口、数字员工 | 🟡 部分完成 | 后台管理已有，用户侧对话页待做 |
| **E** | 智能问数、数据仓库、大屏/设置/统计 | ⬜ 待开发 | 用户问数入口尚未实现 |

**任务书考察点**：需求完整、功能完整、去 AI 化 UI、安全能力、产品化程度——当前以「认证 + 后台骨架 + 门户导航」为主，业务子系统仍待各成员补齐。

---

## 三、本次工作记录（成员 A / xyh）

### 3.1 完成的需求项

| 编号 | 内容 | 对应需求 |
|------|------|----------|
| A-1 | 用户注册（前后端） | REQ-F-002 |
| A-2 | 登录/注册页 UI 规范化（本地 Bootstrap + FA） | REQ-NF-001、REQ-UI-* |
| A-3 | 用户门户布局 `portal_base.html` | 供 C/D/E 子页继承 |
| A-4 | 首页功能卡片可点击跳转 | 链至问数/瞭望/数字员工路由 |
| A-5 | 登录失败限次、密码强度校验、XSRF | REQ-NF-003 |
| A-6 | `_portal_assets.html` 统一静态资源引用 | REQ-NF-001 |
| A-7 | 注册默认绑定 `normal_user` 角色 | 与 B 的 RBAC 联调 |

### 3.2 协作原则

- **未修改**其他成员独占文件（如 `user.py`、`rbac.py`、`admin.py`、`watchtower.py` 等）。
- 需跨模块能力时，新增 **临时文件**（文件名与注释均标注「临时 - 成员 A」），便于后续删除。

### 3.3 新增路由（`app.py`）

| 方法 | 路径 | Handler | 说明 |
|------|------|---------|------|
| GET/POST | `/auth/register` | `RegisterHandler` | 用户注册 |
| GET | `/portal/query` | `TempPortalQueryHandler` | **临时**，待 E 接管 |
| GET | `/portal/watch` | `TempPortalWatchHandler` | **临时**，待 C 接管 |
| GET | `/portal/digital-employee` | `TempPortalDigitalEmployeeHandler` | **临时**，待 D 接管 |

原有路由 `/`、`/auth/login`、`/auth/logout` 及全部 `/admin/*` 路由保持不变。

---

## 四、文件功能说明

### 4.1 根目录

| 文件 | 功能 |
|------|------|
| `app.py` | 主入口：初始化数据库、注册路由、启动 Tornado 服务（端口 10087） |
| `requirement.txt` | 需求跟踪文档（功能/非功能需求清单与状态） |
| `readme.md` | 项目架构与学习说明 |
| `guide.md` | 开发指引 |
| `app.md` | 目录结构索引 |
| `团队任务一-任务分配.md` | 五人分工、文件归属、验收标准 |
| `川农23级团队任务书.pdf` | 实训任务书（任务一至五及汇报要求） |
| `log_xyh.md` | 本日志（进展与修改记录） |
| `test.py` | 临时测试脚本 |
| `demo.db` | 示例数据库（非主库） |
| `database/app.db` | 运行时 SQLite 主库（启动时自动创建/迁移） |

### 4.2 控制器 `app/controllers/`

| 文件 | 负责人 | 功能 |
|------|--------|------|
| `base.py` | A | `BaseHandler`：登录态、`get_current_user_record()`、`get_current_role_name()`；`AdminBaseHandler`：非管理员访问后台时重定向门户 |
| `auth.py` | A | `LoginHandler`：双入口登录（普通用户/管理员）、失败限次；`RegisterHandler`：注册并自动登录；`LogoutHandler`：退出 |
| `home.py` | A | `IndexHandler`：用户门户首页（管理员自动跳转后台） |
| `admin.py` | B/C/D 共用（待拆分） | 后台全部 Handler：用户、角色、权限、接口、数字员工、模型、瞭望源与采集记录等 |
| `_temp_a_role_helper.py` | A（**临时**） | `get_role_id_by_code()`：注册时查询 `normal_user` 角色 ID |
| `_temp_a_portal_stubs.py` | A（**临时**） | 问数/瞭望/数字员工占位页 Handler |

### 4.3 模型 `app/models/`

| 文件 | 负责人 | 功能 |
|------|--------|------|
| `db.py` | 共享（A 牵头 users 表） | 数据库连接、`init_db()` 建表、默认角色/权限种子数据 |
| `user.py` | B | 用户 CRUD、密码哈希校验、角色码查询 |
| `rbac.py` | B | 角色、权限、角色-权限关联 |
| `watchtower.py` | C | 瞭望源、采集逻辑、采集记录 |
| `api_interface.py` | D | 外部 API 接口配置 |
| `model_service.py` | D | 大模型服务配置、对话、Token 统计 |
| `digital_employee.py` | D | 数字员工配置与默认助手 |

### 4.4 模板 `app/templates/`

| 文件 | 负责人 | 功能 |
|------|--------|------|
| `base.html` | A | 全站 HTML 骨架：`{% block content %}`、`head_assets`、`extra_js` |
| `portal_base.html` | A | 用户门户布局：顶栏导航、用户名、退出、页脚 |
| `_portal_assets.html` | A | 本地 Bootstrap / Font Awesome / admin.css / portal.css 统一引入 |
| `login.html` | A | 登录页（普通用户 / 管理员切换、注册入口） |
| `register.html` | A | 注册页（用户名/密码/确认密码、策略说明） |
| `index.html` | A | 用户首页（三张功能卡片跳转） |
| `_temp_a_portal_stub.html` | A（**临时**） | 子系统未就绪时的占位提示页 |
| `admin/*.html` | B/C/D | 各后台管理页面 |
| `admin/_sidebar.html` | 分段维护 | 后台侧栏导航 |

### 4.5 静态资源 `app/static/`

| 文件 | 负责人 | 功能 |
|------|--------|------|
| `css/base.css` | A | 基础重置、错误色、代码样式 |
| `css/portal.css` | A | 认证页、门户顶栏、功能卡片、占位页样式 |
| `css/admin.css` | 后台共用 | 玻璃态面板、侧栏、表格、按钮等后台组件样式 |
| `js/base.js` | A | 前端用户名/密码校验工具 `cnAgentOS.validate*` |
| `dist/*` | 全员遵守 | 本地化 Bootstrap 5.3.8、Font Awesome 5.15.4、layui 2.13.6（禁止 CDN） |

---

## 五、成员 A 修改清单（详细）

### 5.1 新建文件

```
app/controllers/_temp_a_role_helper.py
app/controllers/_temp_a_portal_stubs.py
app/templates/portal_base.html
app/templates/register.html
app/templates/_portal_assets.html
app/templates/_temp_a_portal_stub.html
app/static/css/portal.css
```

### 5.2 修改文件

| 文件 | 修改要点 |
|------|----------|
| `app/controllers/auth.py` | 新增 `RegisterHandler`；`validate_username` / `validate_password`；登录失败 5 次/15 分钟锁定 |
| `app/controllers/base.py` | 新增 `get_current_role_name()` |
| `app/controllers/home.py` | 渲染首页时传入 `active_nav="home"` |
| `app/templates/base.html` | 改为 block 结构，支持模板继承 |
| `app/templates/login.html` | 重构为 `auth-page` 布局；增加注册链接；管理员入口隐藏注册 |
| `app/templates/index.html` | 继承 `portal_base.html`；卡片改为可点击 `<a>` |
| `app/static/css/base.css` | 补充 box-sizing、通用文字样式 |
| `app/static/js/base.js` | 由占位 `console.log` 改为校验工具函数 |
| `app.py` | 注册 `/auth/register`；注册三个临时 `/portal/*` 路由 |

### 5.3 安全与业务规则（auth.py）

- **用户名**：3～20 位，仅字母、数字、下划线。
- **密码**：6～32 位，须同时包含字母和数字。
- **注册**：重复用户名返回 409；成功写入 `normal_user` 角色并 `set_secure_cookie` 后跳转 `/`。
- **登录**：按 IP+用户名记录失败次数，超限返回 429。
- **角色分流**：普通用户入口仅允许 `normal_user`；管理员入口仅允许 `super_admin` / `normal_admin`。

---

## 六、待办与后续计划

### 6.1 成员 A 后续（如有）

- [ ] 成员 B/C/D/E 正式页面就绪后，删除 `_temp_a_*` 及 `app.py` 中临时路由注释段。
- [ ] 与 A 负责的 `app.py` 合并其他成员提交的路由清单。
- [ ] 视联调情况补充 `readme.md` 中用户门户章节（可选）。

### 6.2 其他成员待完成（摘录）

| 成员 | 关键待办 |
|------|----------|
| B | 功能管理页、`admin.py` 拆分为 `admin_rbac.py`、门户权限码校验 |
| C | 用户侧 `/portal/watch` 瞭望列表与筛选 |
| D | 用户侧 `/portal/digital-employee` 对话页、流式输出完善 |
| E | `/portal/query` 问数页、数据仓库、大屏/设置/统计 |

### 6.3 临时文件删除条件

| 临时文件 | 删除时机 |
|----------|----------|
| `_temp_a_role_helper.py` | B 提供稳定 RBAC 查询 API |
| `_temp_a_portal_stubs.py` + `_temp_a_portal_stub.html` | C/D/E 各自路由与模板上线 |
| `app.py` 中 `# 【临时路由 - 成员 A】` 三行 | 同上 |

---

## 七、验证记录

**日期**：2026-05-26  

**本地脚本验证**（`python -c ...`）：

- `validate_username` / `validate_password` 规则断言通过。
- `get_role_id_by_code('normal_user')` 可正确取到角色 ID。
- `UserRepository.create_user` + `verify_user` + 角色码 `normal_user` 流程通过。
- `app.py` 中 `make_app()` 可正常加载全部路由。

**建议手工验证**：

1. 访问 `http://127.0.0.1:10087/auth/register` 注册新用户 → 自动进入首页。
2. 首页点击三个功能卡片 → 显示临时占位页（标注负责人 C/D/E）。
3. 使用 `user/123456` 登录普通用户入口；使用管理员账号登录管理入口 → 进入 `/admin/users`。
4. 连续错误密码 5 次 → 提示 15 分钟内限制登录。

---

## 八、目录结构快照（2026-05-26）

```
cnAgentOS-main/
├── app.py                          # 主入口（含 A 新增路由）
├── requirement.txt
├── readme.md
├── 团队任务一-任务分配.md
├── log_xyh.md                      # 本日志
├── app/
│   ├── controllers/
│   │   ├── base.py                 # [A] 修改
│   │   ├── auth.py                 # [A] 修改
│   │   ├── home.py                 # [A] 修改
│   │   ├── admin.py                # [B/C/D] 未改
│   │   ├── _temp_a_role_helper.py  # [A] 临时
│   │   └── _temp_a_portal_stubs.py # [A] 临时
│   ├── models/                     # 各成员独占，A 未改
│   ├── templates/
│   │   ├── base.html               # [A] 修改
│   │   ├── portal_base.html        # [A] 新建
│   │   ├── login.html              # [A] 修改
│   │   ├── register.html           # [A] 新建
│   │   ├── index.html              # [A] 修改
│   │   ├── _portal_assets.html     # [A] 新建
│   │   ├── _temp_a_portal_stub.html# [A] 临时
│   │   └── admin/                  # 后台模板
│   └── static/
│       ├── css/base.css            # [A] 修改
│       ├── css/portal.css          # [A] 新建
│       ├── css/admin.css
│       ├── js/base.js              # [A] 修改
│       └── dist/                   # 本地化前端组件
└── database/app.db
```

---

## 九、变更日志（Changelog）

| 日期 | 操作人 | 摘要 |
|------|--------|------|
| 2026-05-26 | xyh | 编写 `团队任务一-任务分配.md`，完成五人任务拆分 |
| 2026-05-26 | xyh | 完成成员 A 全部任务：注册、门户布局、静态规范、临时占位路由 |
| 2026-05-26 | xyh | 编写 `log_xyh.md` 项目进展与文件说明日志 |

---

*本日志随项目迭代持续更新；重大联调或合并路由后请追加「变更日志」一节。*
