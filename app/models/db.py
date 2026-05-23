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
        _ensure_column(conn, "users", "role_id", "role_id INTEGER")

        conn.execute(
            "INSERT OR IGNORE INTO roles(name, code, is_system) VALUES(?, ?, 1)",
            ("超级管理员", "super_admin"),
        )
        conn.execute(
            "INSERT OR IGNORE INTO permissions(menu_group, name, code, sort_no) VALUES(?, ?, ?, ?)",
            ("系统管理", "功能管理", "system.menu", 10),
        )
        conn.execute(
            "INSERT OR IGNORE INTO permissions(menu_group, name, code, sort_no) VALUES(?, ?, ?, ?)",
            ("系统管理", "权限管理", "system.permission", 20),
        )
        conn.execute(
            "INSERT OR IGNORE INTO permissions(menu_group, name, code, sort_no) VALUES(?, ?, ?, ?)",
            ("系统管理", "角色管理", "system.role", 30),
        )
        conn.execute(
            "UPDATE users SET role_id = (SELECT id FROM roles WHERE code = 'super_admin') WHERE username = 'admin'"
        )
