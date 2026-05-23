# 项目结构说明

```text
C:.
|   app.md  # 项目结构说明文档
|   app.py  # 程序主入口，创建 Tornado 应用、配置路由并启动服务
|   demo.db  # 示例数据库文件
|   test.py  # 测试脚本/临时验证文件
|
+---app
|   |   __init__.py  # 将 `app` 目录标记为 Python 包
|   |
|   +---controllers
|   |   |   auth.py      # 认证控制器，处理登录和退出请求
|   |   |   base.py      # 控制器基类，封装登录态获取等公共逻辑
|   |   |   home.py      # 首页控制器，处理后台首页展示
|   |   |   __init__.py  # 将 `controllers` 目录标记为 Python 包
|   |
|   +---models
|   |   |   db.py        # 数据库连接、数据库路径和初始化建表逻辑
|   |   |   user.py      # 用户仓储层，负责用户创建、查询和校验
|   |   |   __init__.py  # 将 `models` 目录标记为 Python 包
|   |
|   +---static
|   |   +---css
|   |   |       base.css # 基础样式文件
|   |   |
|   |   \---js
|   |           base.js  # 基础脚本文件
|   |
|   \---templates
|       |   base.html     # 公共模板基底
|       |   index.html    # 后台首页模板
|       |   login.html    # 登录页模板
|       |   register.html # 注册页模板，预留页面
|
\---database
        app.db  # SQLite 数据库文件
\---venv(python=3.12)