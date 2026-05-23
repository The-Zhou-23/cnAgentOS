import hashlib
import secrets
import sqlite3

from app.models.db import get_connection


def _hash_password(password: str, salt: bytes) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return dk.hex()


class UserRepository:
    @staticmethod
    def create_user(username: str, password: str, role_id: int | None = None) -> bool:
        salt = secrets.token_bytes(16)
        password_hash = _hash_password(password, salt)

        try:
            with get_connection() as conn:
                conn.execute(
                    "insert into users(username,password_hash,salt,role_id) values(?,?,?,?)",
                    (username, password_hash, salt.hex(), role_id),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def update_user(user_id: int, username: str, password: str | None = None, role_id: int | None = None) -> bool:
        try:
            with get_connection() as conn:
                if password:
                    salt = secrets.token_bytes(16)
                    password_hash = _hash_password(password, salt)
                    conn.execute(
                        "update users set username = ?, password_hash = ?, salt = ?, role_id = ? where id = ?",
                        (username, password_hash, salt.hex(), role_id, user_id),
                    )
                else:
                    conn.execute(
                        "update users set username = ?, role_id = ? where id = ?",
                        (username, role_id, user_id),
                    )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def update_user_password_only(user_id: int, password: str) -> bool:
        if not password:
            return False
        salt = secrets.token_bytes(16)
        password_hash = _hash_password(password, salt)
        with get_connection() as conn:
            conn.execute(
                "update users set password_hash = ?, salt = ? where id = ?",
                (password_hash, salt.hex(), user_id),
            )
        return True

    @staticmethod
    def delete_user(user_id: int) -> None:
        with get_connection() as conn:
            conn.execute("delete from users where id = ?", (user_id,))

    @staticmethod
    def batch_delete_users(user_ids: list[int]) -> None:
        if not user_ids:
            return
        placeholders = ",".join(["?"] * len(user_ids))
        with get_connection() as conn:
            conn.execute(f"delete from users where id in ({placeholders})", user_ids)

    @staticmethod
    def get_user_by_username(username: str):
        with get_connection() as conn:
            row = conn.execute(
                "select id, username, password_hash, salt, role_id from users where username = ?",
                (username,),
            ).fetchone()
        return row

    @staticmethod
    def get_user_by_id(user_id: int):
        with get_connection() as conn:
            row = conn.execute(
                "select id, username, password_hash, salt, role_id from users where id = ?",
                (user_id,),
            ).fetchone()
        return row

    @staticmethod
    def verify_user(username: str, password: str):
        row = UserRepository.get_user_by_username(username)
        if not row:
            return False

        salt = bytes.fromhex(row["salt"])
        return _hash_password(password, salt) == row["password_hash"]

    @staticmethod
    def count_users() -> int:
        with get_connection() as conn:
            row = conn.execute("select count(1) as c from users").fetchone()
        return int(row["c"])

    @staticmethod
    def list_users(page: int = 1, page_size: int = 20):
        offset = (page - 1) * page_size
        with get_connection() as conn:
            total = conn.execute("select count(1) as c from users").fetchone()["c"]
            rows = conn.execute(
                """
                select u.id, u.username, u.role_id, u.create_at, r.name as role_name, r.code as role_code
                from users u
                left join roles r on u.role_id = r.id
                order by u.id desc
                limit ? offset ?
                """,
                (page_size, offset),
            ).fetchall()
        return int(total), rows
