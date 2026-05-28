import json
import re
import sqlite3
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.models.db import get_connection


DEFAULT_CHUANXIAONONG_PROMPT = """你是川小农，面向四川地区人才、就业、薪资与产业发展场景的专业文案编写助手。
你擅长撰写正式、严谨、结构清晰、可直接用于 Word 文档的介绍文案、报告材料、宣传稿、专题汇报和调研内容，并能把 AI、计算机科学与技术、数据库、信息安全、物联网、智慧农业等技术方向与四川本地产业、岗位需求、人才培养、就业趋势和薪资变化结合起来。

工作原则：
1. 先识别用户需求类型，再决定输出主题、提纲、正文或简短答复。
2. 用户提出介绍、解释、简单说说等需求时，可以直接生成正式介绍内容。
3. 用户提出写报告、写宣传稿、写专题材料等需求时，优先先给推荐主题和大纲，再按需要逐章节生成。
4. 用户未提供充分信息时，先补充必要的地区、行业、技术方向或篇幅要求，不要自行虚构结论。
5. 输出语言必须正式、准确、条理清晰，避免口语化、娱乐化表达。
6. 需要回答“你是谁”时，可直接说明：我是川小农，一名面向四川地区人才、就业、薪资与产业发展场景的专业文案编写助手。

写作要求：
- 默认结合四川地区实际展开；
- 优先围绕人才、就业、薪资、产业升级、岗位需求、产教融合等主题；
- 长文先结构后正文，短问可直接回答；
- 不得编造精确数据、政策名称或机构结论。
"""


class DigitalEmployeeRepository:
    @staticmethod
    def list_employees():
        with get_connection() as conn:
            return conn.execute("select * from digital_employees order by is_enabled desc, id desc").fetchall()

    @staticmethod
    def get_employee(employee_id: int):
        with get_connection() as conn:
            return conn.execute("select * from digital_employees where id = ?", (employee_id,)).fetchone()

    @staticmethod
    def get_employee_by_alias(alias: str):
        with get_connection() as conn:
            return conn.execute("select * from digital_employees where alias = ? and is_enabled = 1", (alias,)).fetchone()

    @staticmethod
    def create_employee(data: dict) -> bool:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    insert into digital_employees(alias, description, employee_type, model_service_id, api_interface_id, prompt, config_json, is_enabled)
                    values(?,?,?,?,?,?,?,?)
                    """,
                    (
                        data.get("alias"),
                        data.get("description", ""),
                        data.get("employee_type", "model"),
                        data.get("model_service_id"),
                        data.get("api_interface_id"),
                        data.get("prompt", ""),
                        data.get("config_json", "{}"),
                        int(data.get("is_enabled", 1)),
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def update_employee(employee_id: int, data: dict) -> bool:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    update digital_employees set
                        alias=?, description=?, employee_type=?, model_service_id=?, api_interface_id=?, prompt=?, config_json=?, is_enabled=?, updated_at=datetime('now')
                    where id=?
                    """,
                    (
                        data.get("alias"),
                        data.get("description", ""),
                        data.get("employee_type", "model"),
                        data.get("model_service_id"),
                        data.get("api_interface_id"),
                        data.get("prompt", ""),
                        data.get("config_json", "{}"),
                        int(data.get("is_enabled", 1)),
                        employee_id,
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def delete_employee(employee_id: int) -> None:
        with get_connection() as conn:
            conn.execute("delete from digital_employees where id = ?", (employee_id,))

    # ---------------------------------------------------------------
    # 对话能力（管理端 + 用户端共用）：根据 @别名 路由到模型/接口
    # 调用方向 emit(text:str) 推送一行消息，最终 yield 完成。
    # 提供 chat_stream 作为生成器，便于 SSE 输出；调用方负责包装。
    # ---------------------------------------------------------------
    @staticmethod
    def chat_stream(message: str, history: list[dict] | None = None):
        """根据用户输入解析 @别名 + 内容，按数字员工类型路由调用，逐条 yield 文本。

        :param message: 当前轮次原始输入，要求 ``@别名 内容`` 形式。
        :param history: 历史多轮对话，元素形如 ``{"role":"user|assistant", "content": "..."}``。
            模型型员工会把历史拼到 ``messages`` 中以支持多轮上下文；接口型员工忽略。
        """
        from app.models.api_interface import APIInterfaceRepository
        from app.models.model_service import ModelServiceRepository

        match = re.match(r"^@([\u4e00-\u9fa5A-Za-z0-9_\-]+)\s*(.*)$", message or "")
        if not match:
            yield "请输入 @别名 开头的消息，例如：@川小农 帮我介绍智慧农业"
            return
        alias = match.group(1).strip()
        question = (match.group(2) or "").strip()
        employee = DigitalEmployeeRepository.get_employee_by_alias(alias)
        if not employee:
            yield f"未找到数字员工：@{alias}"
            return
        try:
            if employee["employee_type"] == "api":
                api = APIInterfaceRepository.get_interface(employee["api_interface_id"])
                if not api:
                    # 没有绑定接口的内置类型（如新闻：直接读 watchtower）
                    yield f"已匹配数字员工：@{employee['alias']}，正在准备数据..."
                    yield from DigitalEmployeeRepository._dispatch_internal(employee, question, message)
                    yield "处理完成"
                    return
                yield f"已匹配数字员工：@{employee['alias']}，正在调用接口..."
                yield from DigitalEmployeeRepository._dispatch_api(api, employee, question, message)
                yield "处理完成"
            else:
                model = (
                    ModelServiceRepository.get_model(employee["model_service_id"])
                    if employee["model_service_id"]
                    else ModelServiceRepository.get_system_model()
                )
                if not model:
                    yield "未找到可用模型"
                    return
                prompt = employee["prompt"] or "你是一个专业的数字员工，请简洁回答用户问题。"
                # 多轮上下文：system + 过往 history（限制最近 20 轮防止过长） + 当前 user
                cleaned_history: list[dict] = []
                if history:
                    for h in history[-20:]:
                        role = (h.get("role") or "").strip()
                        content = (h.get("content") or "").strip()
                        if role in ("user", "assistant") and content:
                            cleaned_history.append({"role": role, "content": content})
                messages = [{"role": "system", "content": prompt}]
                messages.extend(cleaned_history)
                messages.append({"role": "user", "content": question or message})
                yield f"已匹配数字员工：@{employee['alias']}，正在调用模型..."
                completion_chars = 0
                for raw_line in ModelServiceRepository.stream_chat(model["id"], messages):
                    if raw_line.startswith("data: "):
                        payload_text = raw_line[6:].strip()
                        if payload_text in ("[DONE]", "DONE"):
                            continue
                        try:
                            payload = json.loads(payload_text)
                            delta = (
                                payload.get("choices", [{}])[0]
                                .get("delta", {})
                                .get("content", "")
                            )
                            if delta:
                                completion_chars += len(delta)
                                yield delta
                        except Exception:
                            continue
                    elif raw_line:
                        completion_chars += len(raw_line)
                        yield raw_line
                # token 估算入库（流式接口未返回 usage 时的兜底统计）
                if completion_chars:
                    prompt_tokens = max(1, sum(len(m.get("content", "")) for m in messages) // 4)
                    completion_tokens = max(1, completion_chars // 4)
                    ModelServiceRepository.update_tokens(
                        model["id"],
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                    )
                yield "处理完成"
        except Exception as exc:
            yield f"执行失败：{exc}"

    @staticmethod
    def _dispatch_api(api, employee, question: str, message: str):
        from app.models.model_service import ModelServiceRepository

        name = api["name"]
        if name == "天气 API":
            city_match = re.search(
                r"(\S+?市|\S+?省|\S+?区|\S+?县|\S+?州|北京|上海|天津|重庆)",
                question or "",
            )
            city = None
            if city_match:
                city = re.sub(
                    r"^(查一下|查询|今天|明天|后天|现在|请问|帮我|看下|看看|一下)+",
                    "",
                    city_match.group(1),
                )
            else:
                model = (
                    ModelServiceRepository.get_model(employee["model_service_id"])
                    if employee["model_service_id"]
                    else ModelServiceRepository.get_system_model()
                )
                if model:
                    parse_prompt = (
                        "你是天气查询参数整理助手。请从用户输入中只提取城市名称，"
                        "若无法识别城市，直接返回：未识别出城市。不要解释，不要扩写。"
                    )
                    raw = ModelServiceRepository.chat(
                        model["id"],
                        [
                            {"role": "system", "content": parse_prompt},
                            {"role": "user", "content": question or message},
                        ],
                    )
                    try:
                        parsed = json.loads(raw)
                        city = (
                            ((parsed.get("choices") or [{}])[0].get("message") or {}).get(
                                "content"
                            )
                            or ""
                        ).strip()
                    except Exception:
                        city = (raw or "").strip()
                    city = (city or "").replace("\n", " ")
                    city = re.sub(r"^城市[:：]?\s*", "", city)
                    city = re.sub(r"^【?城市】?[:：]?\s*", "", city)
                    if not city or "未识别出城市" in city:
                        yield "未识别出城市，请在问题中明确城市名称，例如：@天气 雅安市天气怎么样"
                        return
            if not city:
                yield "未识别出城市，请在问题中明确城市名称，例如：@天气 雅安市天气怎么样"
                return
            url = f"{api['api_url']}?{urlencode({'city': city})}"
            yield f"请求天气接口：{url}"
            with urlopen(Request(url), timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            if isinstance(data, dict) and data.get("code") == 200 and isinstance(
                data.get("data"), dict
            ):
                d = data["data"]
                current = d.get("current") or {}
                living = d.get("living") or []
                rain_tip = next((x for x in living if x.get("name") == "雨伞指数"), None)
                weather_text = (
                    f"{d.get('city', city)}："
                    f"{current.get('weather') or d.get('weather') or '未知'}，"
                    f"当前{current.get('temp') or d.get('temp') or '未知'}℃，"
                    f"风力{current.get('windSpeed') or d.get('windSpeed') or '未知'}，"
                    f"{current.get('date') or d.get('time') or ''}"
                ).strip()
                yield weather_text
                if rain_tip:
                    yield f"雨伞建议：{rain_tip.get('index')}｜{rain_tip.get('tips')}"
            else:
                yield json.dumps(data, ensure_ascii=False)
        elif name == "音乐 API":
            yield f"请求音乐接口：{api['api_url']}"
            with urlopen(Request(api["api_url"]), timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            if isinstance(data, dict) and data.get("code") == 200 and isinstance(
                data.get("data"), dict
            ):
                d = data["data"]
                title = (
                    d.get("song")
                    or d.get("name")
                    or d.get("title")
                    or "随机音乐"
                )
                artist = d.get("singer") or d.get("artist") or "未知歌手"
                album = d.get("album") or d.get("source") or ""
                play_url = (
                    d.get("Music")
                    or d.get("music")
                    or d.get("url")
                    or d.get("play_url")
                    or d.get("mp3")
                    or ""
                )
                cover = d.get("cover") or d.get("pic") or ""
                yield f"音乐推荐：{title}｜{artist}"
                if album:
                    yield f"来源：{album}"
                if cover:
                    yield f"封面：{cover}"
                if play_url:
                    yield f"播放地址：{play_url}"
            else:
                yield json.dumps(data, ensure_ascii=False)
        else:
            with urlopen(Request(api["api_url"]), timeout=30) as resp:
                data = resp.read().decode("utf-8", errors="ignore")
            yield data

    @staticmethod
    def _dispatch_internal(employee, question: str, message: str):
        """无外部接口绑定的内置类型助手，目前支持「新闻」（读 watchtower 最近 N 条）。

        电影助手需要绑定「电影 API」接口，未绑定时给出引导提示。
        """
        from app.models.watchtower import WatchtowerRepository

        alias = employee["alias"]
        config = {}
        try:
            config = json.loads(employee["config_json"] or "{}") or {}
        except Exception:
            config = {}
        kind = (config.get("kind") or "").strip()
        if kind == "news" or alias == "新闻":
            try:
                limit = int(config.get("limit") or 5)
            except Exception:
                limit = 5
            limit = max(1, min(limit, 20))
            _, rows = WatchtowerRepository.list_records(page=1, page_size=limit)
            if not rows:
                yield "暂无新闻数据，请管理员先在「百度新闻采集」中执行一次采集。"
                return
            yield f"最新 {len(rows)} 条新闻："
            for idx, r in enumerate(rows, 1):
                yield f"{idx}. {r['title']}（来源：{r['source_name']}｜关键词：{r['keyword']}）"
                if r["url"]:
                    yield f"   原文：{r['url']}"
        elif kind == "dujitang" or alias == "毒鸡汤":
            import random

            quotes = [
                "你以为有钱人很快乐吗？他们的快乐你根本想象不到。",
                "你全力做到最好，可能还不如别人的随便搞搞。",
                "失败并不可怕，可怕的是你还相信这句话。",
                "当你觉得自己又丑又穷的时候，别绝望，至少你的判断是对的。",
                "生活不止眼前的苟且，还有远方的苟且。",
                "上帝是公平的，给了你丑的外表，还会给你一颗玻璃心。",
            ]
            yield random.choice(quotes)
        elif kind == "movie" or alias == "电影":
            yield (
                "电影助手暂未绑定外部接口。请管理员在「接口管理」中新增电影类 API "
                "（例如 https://api.52vmy.cn/api/... 系列），并在数字员工中绑定接口型即可启用。"
            )
        else:
            yield (
                f"@{alias} 类型为接口型但未绑定接口。请管理员在「数字员工」管理中绑定接口，"
                f"或在 config_json 中指定 kind=news/movie 走内置实现。"
            )

    @staticmethod
    def ensure_defaults():
        from app.models.api_interface import APIInterfaceRepository
        from app.models.model_service import ModelServiceRepository

        system_model = ModelServiceRepository.get_system_model()
        interfaces = {row["name"]: row["id"] for row in APIInterfaceRepository.list_interfaces()}
        defaults = [
            {
                "alias": "川小农",
                "description": "基于默认模型 + 提示词的智能对话数字员工",
                "employee_type": "model",
                "model_service_id": system_model["id"] if system_model else None,
                "api_interface_id": None,
                "prompt": DEFAULT_CHUANXIAONONG_PROMPT,
                "config_json": "{}",
                "is_enabled": 1,
            },
            {
                "alias": "天气",
                "description": "基于接口管理中的天气 API 返回数据",
                "employee_type": "api",
                "model_service_id": None,
                "api_interface_id": interfaces.get("天气 API"),
                "prompt": "仅提取城市名称，不要扩写；若未识别城市，直接提示未识别出城市。",
                "config_json": "{}",
                "is_enabled": 1,
            },
            {
                "alias": "音乐",
                "description": "基于接口管理中的音乐 API 返回数据",
                "employee_type": "api",
                "model_service_id": None,
                "api_interface_id": interfaces.get("音乐 API"),
                "prompt": "仅识别音乐请求意图，优先提取随机播放、歌名或歌手信息，不要扩写。",
                "config_json": "{}",
                "is_enabled": 1,
            },
            {
                "alias": "新闻",
                "description": "基于瞭望采集结果返回最近 N 条新闻标题与原文链接",
                "employee_type": "api",
                "model_service_id": None,
                "api_interface_id": None,
                "prompt": "返回最近的瞭望新闻标题，附带来源、关键词与原文链接。",
                "config_json": '{"kind": "news", "limit": 5}',
                "is_enabled": 1,
            },
            {
                "alias": "电影",
                "description": "电影信息助手（需在接口管理中绑定电影类 API）",
                "employee_type": "api",
                "model_service_id": None,
                "api_interface_id": interfaces.get("电影 API"),
                "prompt": "如已绑定接口，则返回接口数据；否则提示管理员绑定。",
                "config_json": '{"kind": "movie"}',
                "is_enabled": 1,
            },
            {
                "alias": "毒鸡汤",
                "description": "群内 @ 毒鸡汤 获取随机毒鸡汤语录",
                "employee_type": "api",
                "model_service_id": None,
                "api_interface_id": None,
                "prompt": "",
                "config_json": '{"kind": "dujitang"}',
                "is_enabled": 1,
            },
        ]
        with get_connection() as conn:
            for item in defaults:
                existing = conn.execute("select id from digital_employees where alias = ?", (item["alias"],)).fetchone()
                if existing:
                    conn.execute(
                        """
                        update digital_employees set
                            description=?, employee_type=?, model_service_id=?, api_interface_id=?, prompt=?, config_json=?, is_enabled=?, updated_at=datetime('now')
                        where alias=?
                        """,
                        (
                            item["description"],
                            item["employee_type"],
                            item["model_service_id"],
                            item["api_interface_id"],
                            item["prompt"],
                            item["config_json"],
                            item["is_enabled"],
                            item["alias"],
                        ),
                    )
                else:
                    conn.execute(
                        """
                        insert into digital_employees(alias, description, employee_type, model_service_id, api_interface_id, prompt, config_json, is_enabled)
                        values(?,?,?,?,?,?,?,?)
                        """,
                        (
                            item["alias"],
                            item["description"],
                            item["employee_type"],
                            item["model_service_id"],
                            item["api_interface_id"],
                            item["prompt"],
                            item["config_json"],
                            item["is_enabled"],
                        ),
                    )
