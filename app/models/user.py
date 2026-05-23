import hashlib
import secrets
import sqlite3

from app.models.db import get_connection


def _hash_password(password: str, salt: bytes) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return dk.hex()


class UserRepository:
    @staticmethod
    def create_user(username: str, password: str) -> bool:
        salt = secrets.token_bytes(16)
        password_hash = _hash_password(password, salt)

        try:
            with get_connection() as conn:
                conn.execute(
                    "insert into users(username,password_hash,salt) values(?,?,?)",
                    (username, password_hash, salt.hex()),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def update_user(user_id: int, username: str, password: str | None = None) -> bool:
        try:
            with get_connection() as conn:
                if password:
                    salt = secrets.token_bytes(16)
                    password_hash = _hash_password(password, salt)
                    conn.execute(
                        "update users set username = ?, password_hash = ?, salt = ? where id = ?",
                        (username, password_hash, salt.hex(), user_id),
                    )
                else:
                    conn.execute(
                        "update users set username = ? where id = ?",
                        (username, user_id),
                    )
            return True
        except sqlite3.IntegrityError:
            return False

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
                "select id, username, password_hash, salt from users where username = ?",
                (username,),
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
                "select id, username, create_at from users order by id desc limit ? offset ?",
                (page_size, offset),
            ).fetchall()
        return int(total), rows
