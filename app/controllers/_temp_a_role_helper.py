"""
【临时文件 - 成员 A】
用途：注册时查询 normal_user 角色 ID，避免修改成员 B 独占的 rbac.py。
删除条件：成员 B 提供稳定的 RBAC 公开 API 后，改由 auth.py 直接调用并删除本文件。
"""

from app.models.db import get_connection


def get_role_id_by_code(role_code: str) -> int | None:
    with get_connection() as conn:
        row = conn.execute("select id from roles where code = ?", (role_code,)).fetchone()
    return int(row["id"]) if row else None
