# 数据库配置抽象层 - 成员C主责
# 支持 SQLite 和 MySQL 切换，统一连接入口

import os
import json
import sqlite3
from typing import Any, Dict, Optional

# 数据库类型常量
DB_TYPE_SQLITE = "sqlite"
DB_TYPE_MYSQL = "mysql"

# 配置文件路径
CONFIG_PATH = os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "config", "database.json")


class DatabaseConfig:
    """数据库配置管理类"""
    
    def __init__(self):
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载数据库配置"""
        default_config = {
            "db_type": DB_TYPE_SQLITE,
            "sqlite": {
                "path": os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "database", "app.db")
            },
            "mysql": {
                "host": "localhost",
                "port": 3306,
                "database": "cnagentos",
                "username": "root",
                "password": "",
                "charset": "utf8mb4"
            }
        }
        
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
            except Exception:
                pass
        
        return default_config
    
    def _save_config(self):
        """保存数据库配置"""
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)
    
    def get_db_type(self) -> str:
        """获取当前数据库类型"""
        return self._config.get("db_type", DB_TYPE_SQLITE)
    
    def set_db_type(self, db_type: str):
        """设置数据库类型"""
        if db_type in [DB_TYPE_SQLITE, DB_TYPE_MYSQL]:
            self._config["db_type"] = db_type
            self._save_config()
    
    def get_sqlite_path(self) -> str:
        """获取SQLite数据库路径"""
        return self._config["sqlite"]["path"]
    
    def get_mysql_config(self) -> Dict[str, Any]:
        """获取MySQL配置"""
        return self._config["mysql"]
    
    def update_mysql_config(self, host: str, port: int, database: str, username: str, password: str):
        """更新MySQL配置"""
        self._config["mysql"] = {
            "host": host,
            "port": port,
            "database": database,
            "username": username,
            "password": password,
            "charset": "utf8mb4"
        }
        self._save_config()
    
    def test_mysql_connection(self) -> bool:
        """测试MySQL连接"""
        try:
            import pymysql
            config = self.get_mysql_config()
            conn = pymysql.connect(
                host=config["host"],
                port=config["port"],
                user=config["username"],
                password=config["password"],
                database=config["database"],
                charset=config["charset"]
            )
            conn.close()
            return True
        except Exception:
            return False


# 全局配置实例
_db_config = DatabaseConfig()


def get_connection():
    """统一数据库连接入口"""
    db_type = _db_config.get_db_type()
    
    if db_type == DB_TYPE_MYSQL:
        return _get_mysql_connection()
    else:
        return _get_sqlite_connection()


def _get_sqlite_connection():
    """获取SQLite连接"""
    path = _db_config.get_sqlite_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _get_mysql_connection():
    """获取MySQL连接"""
    try:
        import pymysql
        from pymysql.cursors import DictCursor
        
        config = _db_config.get_mysql_config()
        conn = pymysql.connect(
            host=config["host"],
            port=config["port"],
            user=config["username"],
            password=config["password"],
            database=config["database"],
            charset=config["charset"],
            cursorclass=DictCursor
        )
        return conn
    except ImportError:
        raise RuntimeError("MySQL驱动未安装，请安装 pymysql: pip install pymysql")
    except Exception as e:
        raise RuntimeError(f"MySQL连接失败: {str(e)}")


def get_db_type() -> str:
    """获取当前数据库类型"""
    return _db_config.get_db_type()


def set_db_type(db_type: str):
    """设置数据库类型"""
    _db_config.set_db_type(db_type)


def test_connection(db_type: str, mysql_config: Optional[Dict] = None) -> bool:
    """测试数据库连接"""
    if db_type == DB_TYPE_SQLITE:
        try:
            with get_connection():
                return True
        except Exception:
            return False
    elif db_type == DB_TYPE_MYSQL:
        if mysql_config:
            # 临时使用传入的配置测试
            try:
                import pymysql
                conn = pymysql.connect(
                    host=mysql_config["host"],
                    port=mysql_config["port"],
                    user=mysql_config["username"],
                    password=mysql_config["password"],
                    database=mysql_config["database"],
                    charset="utf8mb4"
                )
                conn.close()
                return True
            except Exception:
                return False
        return _db_config.test_mysql_connection()
    return False


def update_mysql_config(host: str, port: int, database: str, username: str, password: str):
    """更新MySQL配置"""
    _db_config.update_mysql_config(host, port, database, username, password)


def get_database_config() -> Dict[str, Any]:
    """获取当前数据库配置"""
    return _db_config._config
