"""成员 D 独占：模型引擎仓储层。

对外稳定 API（供 E 等其他成员调用，签名与返回结构在任务一周期内不变）：

- ``ModelServiceRepository.chat(model_id: int, messages: list[dict], stream: bool=False) -> str``
    阻塞式调用 OpenAI 兼容 ``/chat/completions``，返回原始响应文本（JSON 字符串）。

- ``ModelServiceRepository.stream_chat(model_id: int, messages: list[dict]) -> Iterator[str]``
    流式调用，逐行 yield ``data: {...}`` / 心跳行；调用方自行解析 OpenAI 增量。

- ``ModelServiceRepository.get_system_model() -> sqlite3.Row | None``
    获取当前 ``is_system=1`` 的系统默认模型。

- ``ModelServiceRepository.update_tokens(model_id, prompt_tokens, completion_tokens) -> None``
    Token 累计（``token_total`` 始终递增；``token_today`` 跨日自动归零再累计）。

- ``ModelServiceRepository.test_connectivity(model_id: int) -> dict``
    发送一条 hello 探测目标模型连通性，返回 ``{ok, status, message, elapsed_ms, content}``。

- ``DigitalEmployeeRepository.chat_stream(message, history=None) -> Iterator[str]``
    见 ``digital_employee.py``。@别名路由 + 多轮上下文。
"""

import json
import os
import sqlite3
import time
from datetime import date
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from app.models.db import get_connection


def _load_dotenv_if_needed():
    """Load project .env when running locally so model config is available."""
    for key in ("MODEL_API_KEY", "MODEL_BASE_URL", "MODEL_DEFAULT_NAME"):
        if os.getenv(key):
            continue
        env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, ".env"))
        if not os.path.exists(env_path):
            return
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    if k not in ("MODEL_API_KEY", "MODEL_BASE_URL", "MODEL_DEFAULT_NAME"):
                        continue
                    os.environ.setdefault(k, v.strip())
        except Exception:
            return


_load_dotenv_if_needed()


class ModelServiceRepository:
    @staticmethod
    def list_models(page: int = 1, page_size: int = 6):
        offset = (page - 1) * page_size
        with get_connection() as conn:
            total = conn.execute("select count(1) as c from model_services").fetchone()["c"]
            rows = conn.execute(
                """
                select id, name, model_name, base_url, api_key, is_system, token_total,
                       token_today, conversation_prompt, created_at, updated_at
                from model_services
                order by is_system desc, id desc
                limit ? offset ?
                """,
                (page_size, offset),
            ).fetchall()
        return int(total), rows

    @staticmethod
    def list_all_models():
        with get_connection() as conn:
            return conn.execute("select * from model_services order by is_system desc, id desc").fetchall()

    @staticmethod
    def get_model(model_id: int):
        with get_connection() as conn:
            return conn.execute("select * from model_services where id = ?", (model_id,)).fetchone()

    @staticmethod
    def create_model(data: dict) -> bool:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    insert into model_services(
                        name, model_name, base_url, api_key, is_system,
                        token_total, token_today, conversation_prompt
                    ) values(?,?,?,?,?,?,?,?)
                    """,
                    (
                        data.get("name"),
                        data.get("model_name"),
                        data.get("base_url"),
                        data.get("api_key"),
                        int(data.get("is_system", 0)),
                        int(data.get("token_total", 0)),
                        int(data.get("token_today", 0)),
                        data.get("conversation_prompt", ""),
                    ),
                )
                if int(data.get("is_system", 0)) == 1:
                    conn.execute("update model_services set is_system = 0 where id != last_insert_rowid()")
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def update_model(model_id: int, data: dict) -> bool:
        with get_connection() as conn:
            conn.execute(
                """
                update model_services set
                    name = ?, model_name = ?, base_url = ?, api_key = ?, is_system = ?,
                    conversation_prompt = ?, updated_at = datetime('now')
                where id = ?
                """,
                (
                    data.get("name"),
                    data.get("model_name"),
                    data.get("base_url"),
                    data.get("api_key"),
                    int(data.get("is_system", 0)),
                    data.get("conversation_prompt", ""),
                    model_id,
                ),
            )
            if int(data.get("is_system", 0)) == 1:
                conn.execute("update model_services set is_system = 0 where id != ?", (model_id,))
        return True

    @staticmethod
    def delete_model(model_id: int) -> None:
        with get_connection() as conn:
            conn.execute("delete from model_services where id = ?", (model_id,))

    @staticmethod
    def set_system_model(model_id: int) -> None:
        with get_connection() as conn:
            conn.execute("update model_services set is_system = 0")
            conn.execute("update model_services set is_system = 1 where id = ?", (model_id,))

    @staticmethod
    def get_system_model():
        with get_connection() as conn:
            row = conn.execute("select * from model_services where is_system = 1 order by id desc limit 1").fetchone()
        return row

    @staticmethod
    def update_tokens(model_id: int, prompt_tokens: int = 0, completion_tokens: int = 0):
        """累计 Token；``token_today`` 在跨日时自动归零，再累加当次量。"""
        total_tokens = prompt_tokens + completion_tokens
        today = date.today().isoformat()
        with get_connection() as conn:
            row = conn.execute(
                "select token_today, token_today_date from model_services where id = ?",
                (model_id,),
            ).fetchone()
            if not row:
                return
            stored_date = (row["token_today_date"] if "token_today_date" in row.keys() else "") or ""
            if stored_date != today:
                conn.execute(
                    "update model_services set token_today = 0, token_today_date = ? where id = ?",
                    (today, model_id),
                )
            conn.execute(
                """
                update model_services set
                    token_total = token_total + ?,
                    token_today = token_today + ?,
                    token_today_date = ?,
                    updated_at = datetime('now')
                where id = ?
                """,
                (total_tokens, total_tokens, today, model_id),
            )

    @staticmethod
    def ensure_default_model():
        with get_connection() as conn:
            exists = conn.execute("select count(1) as c from model_services").fetchone()["c"]
            if not exists:
                conn.execute(
                    """
                    insert into model_services(
                        name, model_name, base_url, api_key, is_system,
                        token_total, token_today, conversation_prompt
                    ) values(?,?,?,?,?,?,?,?)
                    """,
                    (
                        "默认模型服务",
                        os.getenv("MODEL_DEFAULT_NAME", "deepseek-v3"),
                        os.getenv("MODEL_BASE_URL", "https://aigc-api.aitoolcore.com/api/v1"),
                        os.getenv("MODEL_API_KEY", ""),
                        1,
                        0,
                        0,
                        "你是一个专业的企业管理助手，请用简洁、准确的方式回答。",
                    ),
                )

    @staticmethod
    def _build_request(model_id: int, messages: list[dict], stream: bool = False):
        model = ModelServiceRepository.get_model(model_id)
        if not model:
            raise ValueError("模型不存在")
        api_key = model["api_key"] or os.getenv("MODEL_API_KEY", "")
        base_url = model["base_url"] or os.getenv("MODEL_BASE_URL", "")
        payload = json.dumps({"model": model["model_name"], "messages": messages, "stream": stream}, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return model, Request(f"{base_url.rstrip('/')}/chat/completions", data=payload, headers=headers, method="POST")

    @staticmethod
    def chat(model_id: int, messages: list[dict], stream: bool = False):
        model, request = ModelServiceRepository._build_request(model_id, messages, stream=stream)
        try:
            with urlopen(request, timeout=120) as resp:
                response_text = resp.read().decode("utf-8", errors="ignore")
                status = getattr(resp, "status", 200)
                if status >= 400:
                    raise RuntimeError(f"模型 API 返回 HTTP {status}: {response_text[:500]}")
                return response_text
        except HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="ignore")[:500]
            except Exception:
                detail = str(exc)
            raise RuntimeError(f"模型 API 请求失败 HTTP {exc.code}: {detail}")
        except URLError as exc:
            raise RuntimeError(f"无法连接模型服务 ({model.get('base_url', '')}): {exc.reason}")

    @staticmethod
    def stream_chat(model_id: int, messages: list[dict]):
        _, request = ModelServiceRepository._build_request(model_id, messages, stream=True)
        with urlopen(request, timeout=120) as resp:
            while True:
                line = resp.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="ignore").strip()
                if not text:
                    continue
                yield text

    @staticmethod
    def parse_stream_usage(line: str):
        try:
            if line.startswith("data: "):
                line = line[6:]
            if line in ("[DONE]", "DONE"):
                return None
            payload = json.loads(line)
            usage = payload.get("usage") or {}
            if usage:
                return {
                    "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
                    "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
                    "total_tokens": int(usage.get("total_tokens", 0) or 0),
                }
        except Exception:
            return None
        return None

    @staticmethod
    def parse_collect_intent(text: str):
        import re
        m = re.search(r"收集(.+?)的(\d+)条信息", text)
        if not m:
            return None
        return {"action": "collect_baidu_news", "keyword": m.group(1).strip(), "count": int(m.group(2)), "start_page": 0}

    @staticmethod
    def test_connectivity(model_id: int) -> dict:
        """REQ-F-008：发送一条最小请求，验证模型 API 是否连通。

        返回结构：``{ok, status, message, elapsed_ms, content}``。
        """
        model = ModelServiceRepository.get_model(model_id)
        if not model:
            return {"ok": False, "status": 0, "message": "模型不存在", "elapsed_ms": 0}
        messages = [
            {"role": "system", "content": "你是连通性测试助手，请用一句话回应。"},
            {"role": "user", "content": "ping"},
        ]
        started = time.time()
        try:
            _, request = ModelServiceRepository._build_request(model_id, messages, stream=False)
            with urlopen(request, timeout=20) as resp:
                code = getattr(resp, "status", 200)
                raw = resp.read().decode("utf-8", errors="ignore")
            content = ""
            try:
                payload = json.loads(raw)
                content = (
                    ((payload.get("choices") or [{}])[0].get("message") or {}).get("content")
                    or ""
                ).strip()
                usage = payload.get("usage") or {}
                if usage:
                    ModelServiceRepository.update_tokens(
                        model_id,
                        prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
                        completion_tokens=int(usage.get("completion_tokens", 0) or 0),
                    )
            except Exception:
                content = raw[:200]
            return {
                "ok": 200 <= int(code) < 400,
                "status": int(code),
                "message": "连通成功" if 200 <= int(code) < 400 else "连通失败",
                "elapsed_ms": int((time.time() - started) * 1000),
                "content": content[:500],
            }
        except HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="ignore")[:300]
            except Exception:
                detail = ""
            return {
                "ok": False,
                "status": exc.code,
                "message": f"HTTP {exc.code}：{exc.reason}",
                "elapsed_ms": int((time.time() - started) * 1000),
                "content": detail,
            }
        except URLError as exc:
            return {
                "ok": False,
                "status": 0,
                "message": f"网络错误：{exc.reason}",
                "elapsed_ms": int((time.time() - started) * 1000),
                "content": "",
            }
        except Exception as exc:
            return {
                "ok": False,
                "status": 0,
                "message": f"调用失败：{exc}",
                "elapsed_ms": int((time.time() - started) * 1000),
                "content": "",
            }
