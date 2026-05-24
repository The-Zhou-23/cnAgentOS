# 数据库链接与建表
import os
import sqlite3


def _project_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))


DB_PATH = os.path.join(_project_root(), "database", "app.db")


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(conn, table: str, column: str, ddl: str):
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def init_db():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS roles(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                code TEXT NOT NULL UNIQUE,
                is_system INTEGER NOT NULL DEFAULT 0,
                create_at TEXT NOT NULL DEFAULT(datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS permissions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                menu_group TEXT NOT NULL,
                name TEXT NOT NULL,
                code TEXT NOT NULL UNIQUE,
                sort_no INTEGER NOT NULL DEFAULT 0,
                create_at TEXT NOT NULL DEFAULT(datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS role_permissions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role_id INTEGER NOT NULL,
                permission_id INTEGER NOT NULL,
                UNIQUE(role_id, permission_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                create_at TEXT NOT NULL DEFAULT(datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS model_services(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                model_name TEXT NOT NULL,
                base_url TEXT NOT NULL,
                api_key TEXT NOT NULL DEFAULT '',
                is_system INTEGER NOT NULL DEFAULT 0,
                token_total INTEGER NOT NULL DEFAULT 0,
                token_today INTEGER NOT NULL DEFAULT 0,
                conversation_prompt TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT(datetime('now')),
                updated_at TEXT NOT NULL DEFAULT(datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS watch_sources(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                source_code TEXT NOT NULL UNIQUE,
                entry_urls_json TEXT NOT NULL,
                headers_json TEXT NOT NULL,
                keywords_label TEXT NOT NULL DEFAULT '关键字',
                page_param_name TEXT NOT NULL DEFAULT 'pn',
                page_step INTEGER NOT NULL DEFAULT 10,
                collect_limit INTEGER NOT NULL DEFAULT 10,
                is_enabled INTEGER NOT NULL DEFAULT 1,
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT(datetime('now')),
                updated_at TEXT NOT NULL DEFAULT(datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS watch_records(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                source_name TEXT NOT NULL,
                keyword TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                url TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT(datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS api_interfaces(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                api_url TEXT NOT NULL UNIQUE,
                response_format TEXT NOT NULL DEFAULT 'JSON',
                request_method TEXT NOT NULL DEFAULT 'GET',
                request_example TEXT NOT NULL,
                qps_limit TEXT NOT NULL DEFAULT '每2秒最多4次，携带Token可无视限制',
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT(datetime('now')),
                updated_at TEXT NOT NULL DEFAULT(datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS digital_employees(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alias TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL DEFAULT '',
                employee_type TEXT NOT NULL DEFAULT 'model',
                model_service_id INTEGER,
                api_interface_id INTEGER,
                prompt TEXT NOT NULL DEFAULT '',
                config_json TEXT NOT NULL DEFAULT '{}',
                is_enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT(datetime('now')),
                updated_at TEXT NOT NULL DEFAULT(datetime('now'))
            )
            """
        )
        _ensure_column(conn, "users", "role_id", "role_id INTEGER")

        conn.execute("INSERT OR IGNORE INTO roles(name, code, is_system) VALUES(?, ?, 1)", ("超级管理员", "super_admin"))
        conn.execute("INSERT OR IGNORE INTO roles(name, code, is_system) VALUES(?, ?, 0)", ("普通管理员", "normal_admin"))
        conn.execute("INSERT OR IGNORE INTO permissions(menu_group, name, code, sort_no) VALUES(?, ?, ?, ?)", ("系统管理", "功能管理", "system.menu", 10))
        conn.execute("INSERT OR IGNORE INTO permissions(menu_group, name, code, sort_no) VALUES(?, ?, ?, ?)", ("系统管理", "权限管理", "system.permission", 20))
        conn.execute("INSERT OR IGNORE INTO permissions(menu_group, name, code, sort_no) VALUES(?, ?, ?, ?)", ("系统管理", "角色管理", "system.role", 30))
        conn.execute("INSERT OR IGNORE INTO api_interfaces(name, api_url, response_format, request_method, request_example, qps_limit, note) VALUES(?, ?, ?, ?, ?, ?, ?)", ("音乐 API", "https://api.52vmy.cn/api/music/wy/rand", "JSON", "GET", "https://api.52vmy.cn/api/music/wy/rand", "每2秒最多4次，携带Token可无视限制", ""))
        conn.execute("INSERT OR IGNORE INTO api_interfaces(name, api_url, response_format, request_method, request_example, qps_limit, note) VALUES(?, ?, ?, ?, ?, ?, ?)", ("天气 API", "https://api.52vmy.cn/api/query/tian", "JSON", "GET", "https://api.52vmy.cn/api/query/tian?city=北京市", "每2秒最多4次，携带Token可无视限制", "点击前往三日天气 API"))
        conn.execute("UPDATE users SET role_id = (SELECT id FROM roles WHERE code = 'super_admin') WHERE username = 'admin'")
