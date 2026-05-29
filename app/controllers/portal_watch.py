"""
用户端瞭望中心
负责动态采集源选择、SSE 采集、数据仓库浏览与删除
"""
import json
import math
import os

import tornado.web

from app.controllers.base import BaseHandler
from app.models.db import get_connection
from app.models.model_service import ModelServiceRepository
from app.models.watchtower import WatchtowerRepository


class PortalWatchListHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        WatchtowerRepository.init_default_sources(self.current_user)
        sources = WatchtowerRepository.list_sources(user_name=self.current_user)
        baidu = WatchtowerRepository.get_source_by_code("baidu_news", user_name=self.current_user)
        self.render(
            "portal/watch_list.html",
            title="智能瞭望",
            username=self.current_user,
            sources=sources,
            default_source=baidu,
            source_count=len(sources),
            active_nav="watch",
        )


class PortalWatchDatabaseHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        page = max(1, int(self.get_argument("page", 1)))
        keyword = (self.get_argument("keyword", "") or "").strip()
        source_name = (self.get_argument("source_name", "") or "").strip()
        page_size = 10
        if keyword or source_name:
            total, records = WatchtowerRepository.list_records_filtered(
                page=page,
                page_size=page_size,
                keyword=keyword or None,
                source_name=source_name or None,
                user_name=self.current_user,
            )
        else:
            total, records = WatchtowerRepository.list_records(page=page, page_size=page_size, user_name=self.current_user)
        total_pages = max(1, math.ceil(total / page_size))
        sources = WatchtowerRepository.list_sources(user_name=self.current_user)
        self.render(
            "portal/watch_database.html",
            title="数据仓库",
            username=self.current_user,
            sources=sources,
            records=records,
            total=total,
            page=page,
            total_pages=total_pages,
            has_prev=page > 1,
            has_next=page < total_pages,
            keyword=keyword,
            source_name=source_name,
            active_nav="database",
        )


class PortalWatchCollectHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self):
        prompt = (self.get_body_argument("prompt", "") or "").strip()
        source_ids = self.get_body_arguments("source_ids")
        area_name = (self.get_body_argument("area_name", "") or "").strip()
        word = (self.get_body_argument("word", "") or "").strip()
        region = (self.get_body_argument("region", "") or "").strip()
        item_count = int(self.get_body_argument("item_count", 10) or 10)
        start_page = int(self.get_body_argument("start_page", 0) or 0)
        self.set_header("Content-Type", "text/event-stream; charset=utf-8")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("Connection", "keep-alive")
        self.flush()

        def send(msg: str):
            self.write(f"data: {json.dumps({'message': msg}, ensure_ascii=False)}\n\n")
            self.flush()

        if not prompt:
            send("请输入关键词或一句话采集指令")
            self.finish()
            return

        selected_sources = []
        for raw_id in source_ids:
            try:
                selected_sources.append(int(raw_id))
            except Exception:
                continue
        if not selected_sources:
            sources = WatchtowerRepository.list_sources(user_name=self.current_user)
            selected_sources = [s["id"] for s in sources if s.get("is_enabled", 1)]
            if not selected_sources:
                WatchtowerRepository.init_default_sources(user_name=self.current_user)
                sources = WatchtowerRepository.list_sources(user_name=self.current_user)
                selected_sources = [s["id"] for s in sources if s.get("is_enabled", 1)]

        if not selected_sources:
            send("已自动创建默认百度新闻采集源，但当前仍未启用，请在采集源面板检查开关状态")
            self.finish()
            return

        import re
        model = ModelServiceRepository.get_system_model()
        if not model:
            send("未找到默认模型，请先在后台配置系统模型")
            self.finish()
            return

        def local_parse(text: str):
            t = text.strip()
            count_m = re.search(r"(\d+)\s*条", t)
            count_v = int(count_m.group(1)) if count_m else 10
            start_v = 0
            if re.search(r"第\s*二\s*页|第二页|从第二页开始", t):
                start_v = 10
            elif re.search(r"第\s*三\s*页|第三页|从第三页开始", t):
                start_v = 20
            elif re.search(r"第\s*四\s*页|第四页|从第四页开始", t):
                start_v = 30
            area_v = ""
            area_patterns = ["四川", "北京", "上海", "重庆", "广东", "湖北", "湖南", "江苏", "浙江", "福建", "云南", "贵州", "陕西", "甘肃", "青海", "辽宁", "吉林", "黑龙江", "河南", "河北", "山东", "山西", "安徽", "江西", "广西", "海南", "天津", "宁夏", "新疆", "内蒙古", "西藏"]
            for ap in area_patterns:
                if ap in t:
                    area_v = ap
                    break
            kw = re.sub(r"(帮我|请帮我|帮忙|给我|麻烦|我想|我需要|我要|请|收集|采集|获取|找|查找)", "", t)
            kw = re.sub(r"\d+\s*条(新闻|信息|数据|内容|记录)?", "", kw)
            kw = re.sub(r"(从第\s*[一二三四五六七八九十]\s*页开始|从第二页开始|从第三页开始|从第四页开始|第一页|第二页|第三页|第四页)", "", kw)
            kw = re.sub(r"(相关新闻|新闻|信息|数据|内容|记录|的|吧|呢|呀|啊)", "", kw)
            kw = kw.strip(" ，。！？,.")
            if not area_v:
                area_v = "四川" if "雅安" in t else ""
            return {"keyword": kw, "count": count_v, "start_page": start_v, "area_name": area_v, "word": kw}

        send("开始解析采集请求...")
        parsed = local_parse(prompt)
        parse_prompt = (
            "你是智能瞭望采集参数解析助手。你的任务是把用户输入解析成严格 JSON，只能输出 JSON，不要输出任何解释、标点说明或多余文字。\n"
            "必须输出的 JSON 字段：keyword, count, start_page。\n"
            "字段含义：\n"
            "- keyword：用户真正要采集的主题词，必须是从原句中提取出来的核心关键词，不要把整句原样返回。\n"
            "- count：需要采集的条数，必须是整数。\n"
            "- start_page：起始页偏移量，0=第一页，10=第二页，20=第三页，以此类推。\n\n"
            "常见示例：\n"
            "用户输入：帮我采集雅安的30条新闻\n"
            "输出：{\"keyword\":\"雅安\",\"count\":30,\"start_page\":0}\n\n"
            "用户输入：收集四川农业大学相关新闻 10条 从第二页开始\n"
            "输出：{\"keyword\":\"四川农业大学\",\"count\":10,\"start_page\":10}\n\n"
            "用户输入：采集成都天气20条\n"
            "输出：{\"keyword\":\"成都天气\",\"count\":20,\"start_page\":0}\n\n"
            f"用户输入：{prompt}"
        )
        try:
            raw = ModelServiceRepository.chat(model["id"], [
                {"role": "system", "content": parse_prompt},
                {"role": "user", "content": prompt},
            ])
            model_parsed = {}
            try:
                model_parsed = json.loads(raw)
            except Exception:
                start = raw.find("{")
                end = raw.rfind("}")
                model_parsed = json.loads(raw[start:end+1]) if start >= 0 and end > start else {}
            if model_parsed.get("keyword"):
                parsed = model_parsed
        except Exception:
            pass

        keyword = (parsed.get("keyword") or "").strip()
        count = int(parsed.get("count") or item_count or 10)
        start = int(parsed.get("start_page") or start_page or 0)
        area_name = (parsed.get("area_name") or area_name or "").strip()
        word = (parsed.get("word") or word or "").strip()
        if not keyword:
            send("模型未提取到关键词，请重新输入更明确的采集请求")
            self.finish()
            return

        sources = WatchtowerRepository.list_sources(user_name=self.current_user)
        source_map = {s.get("id"): s for s in sources}
        has_area_source = any(source_map.get(sid, {}).get("source_code") == "area_news" for sid in selected_sources)
        if not area_name and has_area_source:
            area_name = "四川" if "雅安" in keyword else keyword
        if has_area_source and word and word == area_name:
            word = ""
        # 只有省市名时，word 保持为空
        if has_area_source and keyword and keyword == area_name:
            word = ""
        if has_area_source and not os.getenv("TIANAPI_AREA_NEWS_KEY", "").strip():
            send("地区新闻 key 未配置，请检查 .env 中的 TIANAPI_AREA_NEWS_KEY")
            self.finish()
            return
        send(f"解析结果：keyword={keyword}，count={count}，start_page={start}，area_name={area_name}，word={word}")

        selected_source = None
        for sid in selected_sources:
            src = source_map.get(sid)
            if not src:
                continue
            if src.get("source_code") == "area_news":
                selected_source = src
                break
        if not selected_source:
            for sid in selected_sources:
                src = source_map.get(sid)
                if src:
                    selected_source = src
                    break
        if not selected_source:
            send("未找到可用采集源，请先在采集源面板启用一个来源")
            self.finish()
            return

        send(f"正在使用【{selected_source['name']}】采集...")
        total_saved = 0
        records_buffer = []
        page_step = int(selected_source.get("page_step", 10) or 10)
        max_rounds = max(3, (count + page_step - 1) // page_step + 2)
        round_idx = 0
        current_start = start
        while total_saved < count and round_idx < max_rounds:
            try:
                if selected_source.get("source_code") == "area_news":
                    area_value = area_name or keyword
                    word_value = word or ""
                    send(f"地区新闻请求参数：areaname={area_value}，word={word_value}，page={max(1, current_start or 1)}")
                    result = WatchtowerRepository.collect(
                        source_id=selected_source["id"],
                        keyword=keyword,
                        start_page=current_start,
                        item_count=min(page_step, count - total_saved),
                        user_name=self.current_user,
                        area_name=area_value,
                        word=word_value,
                    )
                else:
                    result = WatchtowerRepository.collect(
                        source_id=selected_source["id"],
                        keyword=keyword,
                        start_page=current_start,
                        item_count=min(page_step, count - total_saved),
                        user_name=self.current_user,
                    )
            except Exception as exc:
                send(f"采集被拦截或失败：{exc}")
                break
            records = result.get("records", [])
            saved = WatchtowerRepository.save_records(records)
            total_saved += saved
            records_buffer.extend(records)
            if records:
                for item in records:
                    send(item.get("title", ""))
                    self.write(f"data: {json.dumps({'type': 'record', 'record': item}, ensure_ascii=False)}\n\n")
                    self.flush()
                current_start += page_step
                round_idx += 1
                continue
            current_start += page_step
            round_idx += 1
            if selected_source.get("source_code") == "area_news" and not records:
                break
        if total_saved < count:
            send(f"当前关键词可用结果不足，实际新增 {total_saved} 条，目标 {count} 条")
        else:
            send(f"采集结束，共新增 {total_saved} 条")
        self.finish()


class PortalWatchAskHandler(BaseHandler):
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
        if sql.startswith("```"):
            sql = sql.strip("`")
            if "\n" in sql:
                sql = sql.split("\n", 1)[1]
            sql = sql.rsplit("\n", 1)[0] if sql.endswith("```") else sql
        banned = ["insert", "update", "delete", "drop", "alter", "create", "attach", "pragma"]
        sql_lower = sql.lower().strip()
        if not sql_lower.startswith("select") or any(word in sql_lower for word in banned) or sql_lower.count(";") > 0 or "watch_records" not in sql_lower:
            self.set_status(400)
            self.write({"ok": False, "error": "生成的SQL不安全", "sql": sql})
            return
        if "limit" not in sql_lower:
            sql = sql.rstrip(";") + " LIMIT 20"
        try:
            with get_connection() as conn:
                conn.row_factory = None
                rows = conn.execute(sql).fetchall()
            result_rows = [dict(row) if hasattr(row, "keys") else list(row) for row in rows]
        except Exception as exc:
            self.set_status(500)
            self.write({"ok": False, "error": f"SQL执行失败: {exc}", "sql": sql})
            return

        answer = f"共查询到 {len(result_rows)} 条结果。"
        self.write({"ok": True, "sql": sql, "rows": result_rows, "answer": answer})


class PortalWatchDeleteHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self, record_id):
        WatchtowerRepository.delete_record(int(record_id), user_name=self.current_user)
        self.redirect("/user/watch")


class PortalWatchBatchDeleteHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self):
        ids = [int(i) for i in self.get_body_arguments("record_ids")]
        WatchtowerRepository.batch_delete_records(ids, user_name=self.current_user)
        self.redirect("/user/watch")
