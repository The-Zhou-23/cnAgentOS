# 数据库配置管理控制器 - 成员C主责

import json
import tornado.web
from app.models.database import (
    get_db_type, set_db_type, test_connection, 
    update_mysql_config, get_database_config,
    DB_TYPE_SQLITE, DB_TYPE_MYSQL
)
from app.models.mysql_schema import init_mysql_schema


class AdminDatabaseSettingsHandler(tornado.web.RequestHandler):
    """数据库设置页面"""
    
    @tornado.web.authenticated
    def get(self):
        config = get_database_config()
        current_db_type = get_db_type()
        
        self.render(
            "admin/database_settings.html",
            title="数据库配置",
            username=self.current_user,
            current_db_type=current_db_type,
            db_types=[DB_TYPE_SQLITE, DB_TYPE_MYSQL],
            mysql_config=config["mysql"]
        )


class AdminDatabaseTestHandler(tornado.web.RequestHandler):
    """测试数据库连接"""
    
    @tornado.web.authenticated
    def post(self):
        try:
            db_type = self.get_body_argument("db_type", "")
            host = self.get_body_argument("host", "")
            port = int(self.get_body_argument("port", 3306))
            database = self.get_body_argument("database", "")
            username = self.get_body_argument("username", "")
            password = self.get_body_argument("password", "")
            
            if db_type == DB_TYPE_SQLITE:
                success = test_connection(DB_TYPE_SQLITE)
            else:
                mysql_config = {
                    "host": host,
                    "port": port,
                    "database": database,
                    "username": username,
                    "password": password
                }
                success = test_connection(DB_TYPE_MYSQL, mysql_config)
            
            self.write(json.dumps({
                "success": success,
                "message": "连接测试成功" if success else "连接测试失败"
            }))
        except Exception as e:
            self.write(json.dumps({
                "success": False,
                "message": str(e)
            }))


class AdminDatabaseSaveHandler(tornado.web.RequestHandler):
    """保存数据库配置"""
    
    @tornado.web.authenticated
    def post(self):
        try:
            db_type = self.get_body_argument("db_type", "")
            host = self.get_body_argument("host", "")
            port = int(self.get_body_argument("port", 3306))
            database = self.get_body_argument("database", "")
            username = self.get_body_argument("username", "")
            password = self.get_body_argument("password", "")
            
            # 更新MySQL配置
            update_mysql_config(host, port, database, username, password)
            
            # 切换数据库类型
            set_db_type(db_type)
            
            # 如果切换到MySQL，初始化表结构
            if db_type == DB_TYPE_MYSQL:
                from app.models.database import get_connection
                try:
                    with get_connection() as conn:
                        created = init_mysql_schema(conn)
                        self.write(json.dumps({
                            "success": True,
                            "message": f"配置保存成功，已创建 {created} 张表"
                        }))
                except Exception as e:
                    # 切换回SQLite
                    set_db_type(DB_TYPE_SQLITE)
                    self.write(json.dumps({
                        "success": False,
                        "message": f"MySQL初始化失败，已回滚到SQLite: {str(e)}"
                    }))
            else:
                self.write(json.dumps({
                    "success": True,
                    "message": "配置保存成功"
                }))
        except Exception as e:
            self.write(json.dumps({
                "success": False,
                "message": str(e)
            }))


class AdminDatabaseMigrateHandler(tornado.web.RequestHandler):
    """数据库迁移页面"""
    
    @tornado.web.authenticated
    def get(self):
        self.render(
            "admin/database_migrate.html",
            title="数据库迁移",
            username=self.current_user,
            current_db_type=get_db_type()
        )
