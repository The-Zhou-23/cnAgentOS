import json
import os
import sqlite3
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
        total_tokens = prompt_tokens + completion_tokens
        with get_connection() as conn:
            conn.execute(
                """
                update model_services set
                    token_total = token_total + ?,
                    token_today = token_today + ?,
                    updated_at = datetime('now')
                where id = ?
                """,
                (total_tokens, total_tokens, model_id),
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
        _, request = ModelServiceRepository._build_request(model_id, messages, stream=stream)
        with urlopen(request, timeout=120) as resp:
            return resp.read().decode("utf-8", errors="ignore")

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
