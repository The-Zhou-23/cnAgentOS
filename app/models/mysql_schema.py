# MySQL建表脚本 - 与SQLite schema保持一致

MYSQL_TABLES = {
    "roles": """
        CREATE TABLE IF NOT EXISTS roles (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE,
            code VARCHAR(50) NOT NULL UNIQUE,
            is_system TINYINT NOT NULL DEFAULT 0,
            create_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "permissions": """
        CREATE TABLE IF NOT EXISTS permissions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            menu_group VARCHAR(50) NOT NULL,
            name VARCHAR(100) NOT NULL,
            code VARCHAR(50) NOT NULL UNIQUE,
            sort_no INT NOT NULL DEFAULT 0,
            create_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "role_permissions": """
        CREATE TABLE IF NOT EXISTS role_permissions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            role_id INT NOT NULL,
            permission_id INT NOT NULL,
            UNIQUE KEY uk_role_permission (role_id, permission_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "users": """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            salt VARCHAR(32) NOT NULL,
            role_id INT,
            is_disabled TINYINT NOT NULL DEFAULT 0,
            create_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "model_services": """
        CREATE TABLE IF NOT EXISTS model_services (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            model_name VARCHAR(100) NOT NULL,
            base_url VARCHAR(255) NOT NULL,
            api_key VARCHAR(255) NOT NULL DEFAULT '',
            is_system TINYINT NOT NULL DEFAULT 0,
            token_total INT NOT NULL DEFAULT 0,
            token_today INT NOT NULL DEFAULT 0,
            conversation_prompt TEXT NOT NULL DEFAULT '',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "watch_sources": """
        CREATE TABLE IF NOT EXISTS watch_sources (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE,
            source_code VARCHAR(50) NOT NULL UNIQUE,
            entry_urls_json TEXT NOT NULL,
            headers_json TEXT NOT NULL,
            keywords_label VARCHAR(50) NOT NULL DEFAULT '关键字',
            page_param_name VARCHAR(50) NOT NULL DEFAULT 'pn',
            page_step INT NOT NULL DEFAULT 10,
            collect_limit INT NOT NULL DEFAULT 10,
            is_enabled TINYINT NOT NULL DEFAULT 1,
            note TEXT NOT NULL DEFAULT '',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "watch_records": """
        CREATE TABLE IF NOT EXISTS watch_records (
            id INT AUTO_INCREMENT PRIMARY KEY,
            source_id INT NOT NULL,
            source_name VARCHAR(100) NOT NULL,
            keyword VARCHAR(100) NOT NULL,
            title VARCHAR(255) NOT NULL,
            content TEXT NOT NULL,
            url VARCHAR(500) NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "api_interfaces": """
        CREATE TABLE IF NOT EXISTS api_interfaces (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE,
            api_url VARCHAR(500) NOT NULL UNIQUE,
            response_format VARCHAR(20) NOT NULL DEFAULT 'JSON',
            request_method VARCHAR(10) NOT NULL DEFAULT 'GET',
            request_example TEXT NOT NULL,
            qps_limit VARCHAR(100) NOT NULL DEFAULT '每2秒最多4次，携带Token可无视限制',
            note TEXT NOT NULL DEFAULT '',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "digital_employees": """
        CREATE TABLE IF NOT EXISTS digital_employees (
            id INT AUTO_INCREMENT PRIMARY KEY,
            alias VARCHAR(50) NOT NULL UNIQUE,
            description TEXT NOT NULL DEFAULT '',
            employee_type VARCHAR(20) NOT NULL DEFAULT 'model',
            model_service_id INT,
            api_interface_id INT,
            prompt TEXT NOT NULL DEFAULT '',
            config_json TEXT NOT NULL DEFAULT '{}',
            is_enabled TINYINT NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "features": """
        CREATE TABLE IF NOT EXISTS features (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            code VARCHAR(50) NOT NULL UNIQUE,
            menu_group VARCHAR(50) NOT NULL DEFAULT '系统管理',
            route_path VARCHAR(255) NOT NULL,
            sort_no INT NOT NULL DEFAULT 0,
            is_enabled TINYINT NOT NULL DEFAULT 1,
            create_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NULL,
            permission_code VARCHAR(50) NOT NULL DEFAULT '',
            icon VARCHAR(50) NOT NULL DEFAULT 'fas fa-circle',
            active_page VARCHAR(100) NOT NULL DEFAULT ''
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "chat_messages": """
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INT AUTO_INCREMENT PRIMARY KEY,
            group_id VARCHAR(36) NOT NULL,
            from_user VARCHAR(50) NOT NULL,
            to_user VARCHAR(50) NOT NULL,
            content TEXT NOT NULL,
            message_type VARCHAR(20) NOT NULL DEFAULT 'text',
            file_path VARCHAR(255) NULL,
            file_name VARCHAR(100) NULL,
            is_read TINYINT NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            KEY idx_group_id (group_id),
            KEY idx_from_user (from_user),
            KEY idx_created_at (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "chat_groups": """
        CREATE TABLE IF NOT EXISTS chat_groups (
            id VARCHAR(36) PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            avatar VARCHAR(255) NULL,
            description TEXT NULL,
            creator VARCHAR(50) NOT NULL,
            is_private TINYINT NOT NULL DEFAULT 1,
            is_active TINYINT NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "chat_group_members": """
        CREATE TABLE IF NOT EXISTS chat_group_members (
            id INT AUTO_INCREMENT PRIMARY KEY,
            group_id VARCHAR(36) NOT NULL,
            username VARCHAR(50) NOT NULL,
            role VARCHAR(20) NOT NULL DEFAULT 'member',
            joined_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uk_group_member (group_id, username)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "chat_contacts": """
        CREATE TABLE IF NOT EXISTS chat_contacts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(50) NOT NULL,
            contact_id VARCHAR(50) NOT NULL,
            relationship VARCHAR(20) NOT NULL DEFAULT 'friend',
            status VARCHAR(20) NOT NULL DEFAULT 'accepted',
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uk_contact (user_id, contact_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "chat_servers": """
        CREATE TABLE IF NOT EXISTS chat_servers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            host VARCHAR(255) NOT NULL,
            port INT NOT NULL DEFAULT 8000,
            is_active TINYINT NOT NULL DEFAULT 1,
            is_primary TINYINT NOT NULL DEFAULT 0,
            weight INT NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    "ai_tools": """
        CREATE TABLE IF NOT EXISTS ai_tools (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE,
            tool_code VARCHAR(50) NOT NULL UNIQUE,
            description TEXT NOT NULL DEFAULT '',
            api_endpoint VARCHAR(255) NOT NULL,
            request_method VARCHAR(10) NOT NULL DEFAULT 'POST',
            params_json TEXT NOT NULL DEFAULT '{}',
            response_format TEXT NOT NULL DEFAULT 'json',
            is_enabled TINYINT NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """
}


def init_mysql_schema(conn) -> int:
    """初始化MySQL表结构"""
    created = 0
    for table_name, sql in MYSQL_TABLES.items():
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql)
                conn.commit()
                created += 1
        except Exception as e:
            print(f"创建表 {table_name} 失败: {e}")
            conn.rollback()
    return created


def ensure_mysql_column(conn, table: str, column: str, ddl: str) -> bool:
    """确保MySQL表存在指定列"""
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"SHOW COLUMNS FROM {table} LIKE %s", (column,))
            if not cursor.fetchone():
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
                conn.commit()
                return True
        return False
    except Exception as e:
        print(f"添加列 {column} 失败: {e}")
        conn.rollback()
        return False
