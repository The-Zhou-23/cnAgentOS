"""成员 D 独占：智慧舆情仓储层。

职责：
1. 提供数智大屏所需的聚合数据：关键词词频、来源分布、时间趋势、地域分布。
2. 提供 AI 舆情分析能力：将聊天/瞭望文本汇总后调模型生成结构化报告
   （摘要 / 风险 / 趋势 / 建议 四段式）。
3. 暴露稳定的"对外只读"接口，供 D 自己的页面调用；同时按任务分工
   声明对 E（瞭望）/A（聊天）的只读依赖：

   - ``SentimentRepository.aggregate_keywords(limit, source)`` —
     聚合关键词词频，``source`` 可选 ``watch`` / ``chat`` / ``all``。
     瞭望侧来自 watch_records；聊天侧来自 chat_messages（仅文本消息抽样）。
     如未来 E 提供 ``WatchtowerRepository.aggregate_keywords`` 或 A 提供
     ``ChatRepository.sample_messages``，本层会自动优先调用对端接口。
   - ``SentimentRepository.sample_messages(limit, since)`` —
     聊天文本抽样（D 自身实现的兜底版本，仅查询 chat_messages 中
     ``msg_type='text'`` 的内容；同样优先调用 A 提供的版本）。

任务三 D3-3 AI 分析：
   - ``SentimentRepository.generate_report(scope, sample_size)`` —
     把抽样文本拼成 prompt，调 ``ModelServiceRepository.chat`` 拿结果。
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timedelta
from typing import Iterable

from app.models.db import get_connection
from app.models.model_service import ModelServiceRepository
from app.models.watchtower import WatchtowerRepository

# 中文/英文停用词（精简版，词云与关键词聚合共用）
STOPWORDS = {
    # 单字虚词
    "的", "了", "和", "是", "在", "我", "有", "也", "都", "就",
    "不", "人", "他", "她", "它", "你", "们", "这", "那", "之",
    "与", "及", "为", "以", "或", "但", "而", "并", "等", "中",
    "上", "下", "对", "于", "把", "被", "向", "从", "到", "由",
    "如", "若", "其", "已", "未", "无", "有", "可", "能", "会",
    # 常见短词
    "我们", "他们", "她们", "你们", "什么", "怎么", "为什么", "因为", "所以",
    "但是", "如果", "虽然", "然而", "或者", "以及", "进行", "需要", "使用",
    "可以", "应该", "今天", "昨天", "明天", "现在", "之后", "之前", "已经",
    "正在", "将要", "可能", "也许", "大家", "自己", "其他", "一些", "这些",
    "那些", "这个", "那个", "一个", "一种", "一样", "一直", "一定", "一般",
    "比较", "非常", "特别", "尤其", "主要", "重要", "比如", "例如",
    # 英文常见停用词（少量）
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "should",
    "can", "could", "may", "might", "must", "shall", "of", "to", "in", "on",
    "at", "by", "for", "with", "about", "against", "between", "into",
    "through", "during", "before", "after", "above", "below", "up", "down",
    "this", "that", "these", "those", "i", "you", "he", "she", "it", "we",
    "they", "them", "his", "her", "its", "our", "their", "and", "or", "but",
    "if", "as", "so", "than", "too", "very", "just", "not", "no",
}

# 简易"省份-代表关键字"映射，用于大屏 3D 地球的地域统计模拟
# 从抽样标题/正文中匹配命中的省份，用于 ECharts-GL geo 散点
PROVINCE_KEYWORDS = {
    "北京": ["北京", "首都"],
    "上海": ["上海", "沪", "魔都"],
    "广东": ["广东", "广州", "深圳", "粤"],
    "四川": ["四川", "成都", "川"],
    "浙江": ["浙江", "杭州", "杭"],
    "江苏": ["江苏", "南京", "苏州"],
    "山东": ["山东", "济南", "青岛"],
    "湖北": ["湖北", "武汉"],
    "湖南": ["湖南", "长沙"],
    "河南": ["河南", "郑州"],
    "陕西": ["陕西", "西安"],
    "重庆": ["重庆", "渝"],
    "天津": ["天津", "津"],
    "福建": ["福建", "福州", "厦门"],
    "辽宁": ["辽宁", "沈阳", "大连"],
    "黑龙江": ["黑龙江", "哈尔滨"],
    "云南": ["云南", "昆明"],
    "新疆": ["新疆", "乌鲁木齐"],
    "西藏": ["西藏", "拉萨"],
    "内蒙古": ["内蒙", "呼和浩特"],
    "广西": ["广西", "南宁"],
    "贵州": ["贵州", "贵阳"],
    "甘肃": ["甘肃", "兰州"],
    "青海": ["青海", "西宁"],
    "宁夏": ["宁夏", "银川"],
    "江西": ["江西", "南昌"],
    "安徽": ["安徽", "合肥"],
    "河北": ["河北", "石家庄"],
    "山西": ["山西", "太原"],
    "吉林": ["吉林", "长春"],
    "海南": ["海南", "海口", "三亚"],
    "台湾": ["台湾", "台北"],
    "香港": ["香港", "港"],
    "澳门": ["澳门"],
}

# 省份大致经纬度（中心点），ECharts-GL geo3D 散点用
PROVINCE_COORDS = {
    "北京": [116.40, 39.90], "上海": [121.47, 31.23], "广东": [113.27, 23.13],
    "四川": [104.07, 30.67], "浙江": [120.15, 30.28], "江苏": [118.78, 32.05],
    "山东": [117.00, 36.65], "湖北": [114.30, 30.60], "湖南": [112.98, 28.20],
    "河南": [113.62, 34.75], "陕西": [108.95, 34.27], "重庆": [106.55, 29.57],
    "天津": [117.20, 39.13], "福建": [119.30, 26.08], "辽宁": [123.43, 41.80],
    "黑龙江": [126.63, 45.75], "云南": [102.73, 25.04], "新疆": [87.62, 43.83],
    "西藏": [91.13, 29.65], "内蒙古": [111.65, 40.82], "广西": [108.32, 22.82],
    "贵州": [106.71, 26.57], "甘肃": [103.83, 36.05], "青海": [101.78, 36.62],
    "宁夏": [106.27, 38.47], "江西": [115.90, 28.68], "安徽": [117.27, 31.87],
    "河北": [114.50, 38.05], "山西": [112.55, 37.87], "吉林": [125.32, 43.88],
    "海南": [110.33, 20.03], "台湾": [121.50, 25.05], "香港": [114.17, 22.32],
    "澳门": [113.55, 22.20],
}


# 中文双字 + 英文词 简易分词
_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]{2,4}|[A-Za-z]{3,}|\d{4,}")


def _tokenize(text: str) -> list[str]:
    if not text:
        return []
    raw = _TOKEN_RE.findall(text)
    return [w.lower() for w in raw if w.strip().lower() not in STOPWORDS]


class SentimentRepository:
    # ---------- 数据抽样 ----------

    @staticmethod
    def sample_watch_titles(limit: int = 200, days: int = 30) -> list[dict]:
        """瞭望数据抽样：仅读 watch_records 表，按时间倒序。"""
        since = (datetime.now() - timedelta(days=days)).isoformat(sep=" ", timespec="seconds")
        with get_connection() as conn:
            rows = conn.execute(
                """
                select id, source_id, source_name, keyword, title, content, url, created_at
                from watch_records
                where created_at >= ?
                order by id desc
                limit ?
                """,
                (since, int(limit)),
            ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def sample_chat_messages(limit: int = 200, days: int = 7) -> list[dict]:
        """聊天文本抽样：仅读取 chat_messages 中 msg_type='text' 的内容。

        优先调用 A 暴露的 ``ChatRepository.sample_messages`` 以保证 D 不直接耦合表结构；
        若 A 尚未提供，则按"只读 SQL"的方式兜底。
        """
        try:
            from app.models.chat import ChatRepository  # type: ignore
            if hasattr(ChatRepository, "sample_messages"):
                rows = ChatRepository.sample_messages(limit, days)  # type: ignore[attr-defined]
                return [dict(r) for r in rows]
        except Exception:
            pass

        since = (datetime.now() - timedelta(days=days)).isoformat(sep=" ", timespec="seconds")
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    """
                    select id, conv_type, sender_name, content, created_at
                    from chat_messages
                    where msg_type = 'text' and created_at >= ?
                      and sender_type != 'system'
                    order by id desc
                    limit ?
                    """,
                    (since, int(limit)),
                ).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []

    # ---------- 聚合 ----------

    @staticmethod
    def aggregate_keywords(limit: int = 60, source: str = "all") -> list[dict]:
        """聚合关键词词频。

        - source='watch'：仅瞭望
        - source='chat' ：仅聊天
        - source='all'  ：合并两类

        优先调用 E 提供的 ``WatchtowerRepository.aggregate_keywords``；若不存在则本地分词。
        """
        counter: Counter = Counter()

        if source in ("all", "watch"):
            try:
                if hasattr(WatchtowerRepository, "aggregate_keywords"):
                    rows = WatchtowerRepository.aggregate_keywords(limit)  # type: ignore[attr-defined]
                    for row in rows:
                        word = (row.get("word") or row.get("keyword") or "").strip()
                        weight = int(row.get("count") or row.get("weight") or 0)
                        if word:
                            counter[word] += max(1, weight)
                else:
                    raise AttributeError("aggregate_keywords not provided")
            except Exception:
                # 兜底：直接分词标题 + keyword 字段
                for record in SentimentRepository.sample_watch_titles(limit=500, days=60):
                    if record.get("keyword"):
                        counter[record["keyword"]] += 3  # 关键词字段权重高
                    for token in _tokenize(record.get("title") or ""):
                        counter[token] += 1

        if source in ("all", "chat"):
            for msg in SentimentRepository.sample_chat_messages(limit=500, days=30):
                for token in _tokenize(msg.get("content") or ""):
                    counter[token] += 1

        items = [
            {"word": word, "count": count}
            for word, count in counter.most_common(limit)
            if word and word not in STOPWORDS
        ]
        return items

    @staticmethod
    def aggregate_sources() -> list[dict]:
        """瞭望来源分布：source_name -> count。"""
        with get_connection() as conn:
            rows = conn.execute(
                """
                select source_name as name, count(1) as value
                from watch_records
                group by source_name
                order by value desc
                """
            ).fetchall()
        return [{"name": r["name"], "value": int(r["value"])} for r in rows]

    @staticmethod
    def aggregate_trend(days: int = 14) -> dict:
        """近 N 天采集量 + 聊天量趋势。返回 {dates, watch, chat}。"""
        today = datetime.now().date()
        date_list = [(today - timedelta(days=days - 1 - i)).isoformat() for i in range(days)]
        with get_connection() as conn:
            watch_rows = conn.execute(
                """
                select substr(created_at, 1, 10) as d, count(1) as c
                from watch_records
                where date(created_at) >= date(?, ?)
                group by substr(created_at, 1, 10)
                """,
                (today.isoformat(), f"-{days - 1} day"),
            ).fetchall()
            try:
                chat_rows = conn.execute(
                    """
                    select substr(created_at, 1, 10) as d, count(1) as c
                    from chat_messages
                    where date(created_at) >= date(?, ?) and msg_type = 'text'
                    group by substr(created_at, 1, 10)
                    """,
                    (today.isoformat(), f"-{days - 1} day"),
                ).fetchall()
            except Exception:
                chat_rows = []

        watch_map = {r["d"]: int(r["c"]) for r in watch_rows}
        chat_map = {r["d"]: int(r["c"]) for r in chat_rows}
        return {
            "dates": date_list,
            "watch": [watch_map.get(d, 0) for d in date_list],
            "chat": [chat_map.get(d, 0) for d in date_list],
        }

    @staticmethod
    def aggregate_geo() -> list[dict]:
        """地域分布：扫描瞭望标题/正文，命中省份关键字累计计数。"""
        counter: Counter = Counter()
        records = SentimentRepository.sample_watch_titles(limit=500, days=90)
        for record in records:
            text = (record.get("title") or "") + " " + (record.get("content") or "")
            for province, keys in PROVINCE_KEYWORDS.items():
                if any(k in text for k in keys):
                    counter[province] += 1
        result = []
        for province, value in counter.most_common():
            coord = PROVINCE_COORDS.get(province)
            if not coord:
                continue
            result.append({
                "name": province,
                "value": [coord[0], coord[1], int(value)],
            })
        return result

    @staticmethod
    def overview_metrics() -> dict:
        """大屏顶部指标卡数据。"""
        with get_connection() as conn:
            watch_total = conn.execute("select count(1) as c from watch_records").fetchone()["c"]
            source_total = conn.execute(
                "select count(1) as c from watch_sources where is_enabled = 1"
            ).fetchone()["c"]
            try:
                chat_total = conn.execute(
                    "select count(1) as c from chat_messages where msg_type='text'"
                ).fetchone()["c"]
            except Exception:
                chat_total = 0
            today_watch = conn.execute(
                "select count(1) as c from watch_records where date(created_at)=date('now','localtime')"
            ).fetchone()["c"]
        return {
            "watch_total": int(watch_total),
            "source_total": int(source_total),
            "chat_total": int(chat_total),
            "today_watch": int(today_watch),
        }

    # ---------- AI 分析 ----------

    PROMPT_TEMPLATE = (
        "你是一位资深的舆情分析师，请基于下面提供的样本数据，从「{scope_label}」角度撰写一份结构化"
        "舆情分析报告。请严格按以下小节标题输出，每节 3~6 句中文，必要时使用短列表，避免空话套话：\n\n"
        "## 一、整体摘要\n"
        "## 二、热点话题（Top 5，给出关键词与简短解读）\n"
        "## 三、潜在风险与情绪倾向\n"
        "## 四、趋势研判与下一步建议\n\n"
        "==== 样本数据（已脱敏）====\n"
        "{samples}\n"
        "==== 词频 Top 关键词 ====\n"
        "{keywords}\n"
        "==== 时间窗口 ====\n"
        "近 {days} 天\n"
    )

    @staticmethod
    def _format_samples(items: Iterable[dict], max_items: int = 30) -> str:
        lines = []
        for idx, item in enumerate(items, start=1):
            if idx > max_items:
                break
            text = (item.get("title") or item.get("content") or "").strip()
            if not text:
                continue
            text = text.replace("\n", " ")[:120]
            lines.append(f"{idx}. {text}")
        return "\n".join(lines) if lines else "（无样本，请先采集瞭望数据或开启聊天）"

    @staticmethod
    def generate_report(scope: str = "all", sample_size: int = 30, days: int = 14) -> dict:
        """生成 AI 舆情报告。

        scope:
          - 'watch' ：仅瞭望
          - 'chat'  ：仅聊天
          - 'all'   ：两者合并
        返回 {ok, scope, content, model, sample_count, keywords}
        """
        scope_label_map = {"watch": "智能瞭望", "chat": "智能聊天", "all": "全域舆情"}
        scope_label = scope_label_map.get(scope, "全域舆情")

        samples: list[dict] = []
        if scope in ("watch", "all"):
            samples.extend(SentimentRepository.sample_watch_titles(limit=sample_size, days=days))
        if scope in ("chat", "all"):
            samples.extend(SentimentRepository.sample_chat_messages(limit=sample_size, days=days))

        keywords = SentimentRepository.aggregate_keywords(limit=20, source=scope)
        keyword_text = "、".join(f"{k['word']}({k['count']})" for k in keywords[:20]) or "（无）"

        prompt = SentimentRepository.PROMPT_TEMPLATE.format(
            scope_label=scope_label,
            samples=SentimentRepository._format_samples(samples, sample_size),
            keywords=keyword_text,
            days=days,
        )

        model = ModelServiceRepository.get_system_model()
        if not model:
            return {
                "ok": False,
                "scope": scope,
                "content": "未配置系统默认模型，请在「管理后台 → 模型引擎」中开启系统模型。",
                "model": "",
                "sample_count": len(samples),
                "keywords": keywords,
            }

        messages = [
            {"role": "system", "content": "你是一位严谨、客观、擅长结构化输出的中文舆情分析师。"},
            {"role": "user", "content": prompt},
        ]
        try:
            raw = ModelServiceRepository.chat(int(model["id"]), messages, stream=False)
            payload = json.loads(raw)
            content = (
                ((payload.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
            ).strip()
            usage = payload.get("usage") or {}
            if usage:
                ModelServiceRepository.update_tokens(
                    int(model["id"]),
                    prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
                    completion_tokens=int(usage.get("completion_tokens", 0) or 0),
                )
            if not content:
                content = "（模型未返回有效内容）"
            return {
                "ok": True,
                "scope": scope,
                "content": content,
                "model": model["name"],
                "sample_count": len(samples),
                "keywords": keywords,
            }
        except Exception as exc:  # pragma: no cover - 网络/模型异常的兜底
            return {
                "ok": False,
                "scope": scope,
                "content": f"调用模型失败：{exc}",
                "model": model["name"],
                "sample_count": len(samples),
                "keywords": keywords,
            }
