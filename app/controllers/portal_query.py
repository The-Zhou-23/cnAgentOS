"""
用户端智能问数
自然语言提问，获取业务数据答案与结构化结果。
"""
import json
import re

import tornado.web

from app.controllers.base import BaseHandler
from app.models.db import get_connection
from app.models.model_service import ModelServiceRepository


class PortalQueryHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render(
            "portal/query.html",
            title="智能问数",
            username=self.current_user,
            active_nav="query",
        )


class PortalQueryAskHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self):
        question = (self.get_body_argument("question", "") or "").strip()
        if not question:
            self.set_status(400)
            self.write({"ok": False, "error": "请输入问题"})
            return

        model = ModelServiceRepository.get_system_model()
        if not model:
            self.set_status(400)
            self.write({"ok": False, "error": "未找到默认模型"})
            return

        schema_prompt = """
你是 SQLite SQL 生成助手。
只允许生成单条 SELECT 语句。
禁止输出解释、禁止多语句、禁止写入操作。
只能查询 watch_records 表。
如果用户问题涉及时间，优先使用 created_at 或 publish_time。
如果用户问题涉及地区，优先使用 region。
如果用户问题涉及来源，优先使用 source_name。
如果用户问题涉及关键词，优先使用 keyword 或 title。
如果没有指定数量，默认 LIMIT 20。
请只返回 SQL，不要返回其他内容。

表结构：
- id: 自增ID
- user_name: 用户名
- source_id: 来源ID
- source_name: 新闻来源
- keyword: 采集关键词
- title: 标题
- content: 内容摘要
- url: 原文链接
- source_url: 来源链接
- publish_time: 发布时间
- region: 地区
- school: 学校
- category: 分类
- view_count: 浏览量
- created_at: 入库时间
"""
        try:
            raw_sql = ModelServiceRepository.chat(model["id"], [
                {"role": "system", "content": schema_prompt},
                {"role": "user", "content": question},
            ])
        except Exception as exc:
            self.set_status(500)
            self.write({"ok": False, "error": f"SQL生成失败: {exc}"})
            return

        sql = raw_sql.strip()
        try:
            payload = json.loads(raw_sql)
            sql = (((payload.get("choices") or [{}])[0].get("message") or {}).get("content") or sql).strip()
        except Exception:
            pass
        if sql.startswith("```"):
            sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.I)
            sql = re.sub(r"\s*```$", "", sql)

        banned = ["insert", "update", "delete", "drop", "alter", "create", "attach", "pragma"]
        sql = sql.strip().rstrip(";")
        sql_lower = sql.lower().strip()
        if not sql_lower.startswith("select") or any(word in sql_lower for word in banned) or ";" in sql_lower or "watch_records" not in sql_lower:
            self.set_status(400)
            self.write({"ok": False, "error": "生成的SQL不安全", "sql": sql})
            return

        if "limit" not in sql_lower:
            sql = sql + " LIMIT 20"
            sql_lower = sql.lower().strip()

        try:
            with get_connection() as conn:
                conn.row_factory = None
                rows = conn.execute(sql).fetchall()
            result_rows = []
            for row in rows:
                if hasattr(row, "keys"):
                    result_rows.append(dict(row))
                else:
                    result_rows.append({f"col_{idx}": value for idx, value in enumerate(row)})
        except Exception as exc:
            self.set_status(500)
            self.write({"ok": False, "error": f"SQL执行失败: {exc}", "sql": sql})
            return

        summarize_prompt = f"""
你是一个智能问数总结助手。
请根据用户问题和查询结果，用简洁中文回答。
如果结果为空，直接说明没有查询到数据。

用户问题：{question}
SQL：{sql}
查询结果：{json.dumps(result_rows, ensure_ascii=False)}
"""
        answer = f"共查询到 {len(result_rows)} 条结果。"
        try:
            summary = ModelServiceRepository.chat(model["id"], [
                {"role": "system", "content": summarize_prompt},
                {"role": "user", "content": question},
            ])
            summary = summary.strip()
            if summary:
                answer = summary
        except Exception:
            pass

        self.write({"ok": True, "sql": sql, "rows": result_rows, "answer": answer})
