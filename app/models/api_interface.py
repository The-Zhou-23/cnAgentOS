import sqlite3
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from app.models.db import get_connection


def _encode_url(url: str) -> str:
    """对包含中文/特殊字符的 URL 做 IDNA + percent 编码兜底。"""
    if not url:
        return url
    try:
        parts = urlsplit(url.strip())
        netloc = parts.netloc
        # host 部分尝试 IDNA；端口/用户信息原样保留
        if netloc:
            try:
                host = parts.hostname or ""
                ascii_host = host.encode("idna").decode("ascii") if host else ""
                userinfo = ""
                if parts.username:
                    userinfo = parts.username
                    if parts.password:
                        userinfo += f":{parts.password}"
                    userinfo += "@"
                port = f":{parts.port}" if parts.port else ""
                netloc = f"{userinfo}{ascii_host}{port}"
            except Exception:
                netloc = parts.netloc
        return urlunsplit(
            (
                parts.scheme,
                netloc,
                quote(parts.path, safe="/%"),
                quote(parts.query, safe="=&%+"),
                quote(parts.fragment, safe="%"),
            )
        )
    except Exception:
        # 兜底：对整体 URL 做一次安全编码
        return quote(url, safe=":/?&=#%+@")


class APIInterfaceRepository:
    @staticmethod
    def list_interfaces():
        with get_connection() as conn:
            return conn.execute("select * from api_interfaces order by id asc").fetchall()

    @staticmethod
    def get_interface(interface_id: int):
        with get_connection() as conn:
            return conn.execute("select * from api_interfaces where id = ?", (interface_id,)).fetchone()

    @staticmethod
    def create_interface(data: dict) -> bool:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    insert into api_interfaces(name, api_url, response_format, request_method, request_example, qps_limit, note)
                    values(?,?,?,?,?,?,?)
                    """,
                    (
                        data.get("name"),
                        data.get("api_url"),
                        data.get("response_format", "JSON"),
                        data.get("request_method", "GET"),
                        data.get("request_example", data.get("api_url")),
                        data.get("qps_limit", "每2秒最多4次，携带Token可无视限制"),
                        data.get("note", ""),
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def update_interface(interface_id: int, data: dict) -> bool:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    update api_interfaces set
                        name=?, api_url=?, response_format=?, request_method=?, request_example=?, qps_limit=?, note=?, updated_at=datetime('now')
                    where id=?
                    """,
                    (
                        data.get("name"),
                        data.get("api_url"),
                        data.get("response_format", "JSON"),
                        data.get("request_method", "GET"),
                        data.get("request_example", data.get("api_url")),
                        data.get("qps_limit", "每2秒最多4次，携带Token可无视限制"),
                        data.get("note", ""),
                        interface_id,
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def delete_interface(interface_id: int) -> None:
        with get_connection() as conn:
            conn.execute("delete from api_interfaces where id = ?", (interface_id,))

    @staticmethod
    def test_interface(interface_id: int) -> dict:
        """对外部接口做一次轻量连通性探测，返回结构化结果。"""
        item = APIInterfaceRepository.get_interface(interface_id)
        if not item:
            return {"ok": False, "status": 0, "message": "接口不存在", "elapsed_ms": 0}
        raw_url = item["request_example"] or item["api_url"]
        url = _encode_url(raw_url)
        method = (item["request_method"] or "GET").upper()
        started = time.time()
        try:
            req = Request(url, method=method)
            req.add_header(
                "User-Agent",
                "Mozilla/5.0 (cnAgentOS API Tester)",
            )
            with urlopen(req, timeout=10) as resp:
                code = getattr(resp, "status", 200)
                body = resp.read(2048).decode("utf-8", errors="ignore")
            return {
                "ok": 200 <= int(code) < 400,
                "status": int(code),
                "message": "请求成功",
                "elapsed_ms": int((time.time() - started) * 1000),
                "preview": body[:500],
            }
        except HTTPError as exc:
            return {
                "ok": False,
                "status": exc.code,
                "message": f"HTTP 错误：{exc.reason}",
                "elapsed_ms": int((time.time() - started) * 1000),
            }
        except URLError as exc:
            return {
                "ok": False,
                "status": 0,
                "message": f"网络错误：{exc.reason}",
                "elapsed_ms": int((time.time() - started) * 1000),
            }
        except Exception as exc:
            return {
                "ok": False,
                "status": 0,
                "message": f"调用失败：{exc}",
                "elapsed_ms": int((time.time() - started) * 1000),
            }
