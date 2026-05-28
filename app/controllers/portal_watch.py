"""
用户端瞭望中心
负责动态采集源选择、SSE 采集、数据仓库浏览与删除
"""
import json
import math

import tornado.web

from app.controllers.base import BaseHandler
from app.models.model_service import ModelServiceRepository
from app.models.watchtower import WatchtowerRepository


class PortalWatchListHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        sources = WatchtowerRepository.list_sources(user_name=self.current_user)
        baidu = WatchtowerRepository.get_source_by_code("baidu_news", user_name=self.current_user)
        if not baidu:
            WatchtowerRepository.create_default_baidu_source(self.current_user)
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
        source_id = (self.get_argument("source_id", "") or "").strip()
        page_size = 10
        if keyword or source_id:
            total, records = WatchtowerRepository.list_records_filtered(
                page=page,
                page_size=page_size,
                keyword=keyword or None,
                source_id=int(source_id) if source_id else None,
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
            source_id=source_id,
            active_nav="database",
        )


class PortalWatchCollectHandler(BaseHandler):
    @tornado.web.authenticated
    def post(self):
        prompt = (self.get_body_argument("prompt", "") or "").strip()
        source_ids = self.get_body_arguments("source_ids")
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
            kw = re.sub(r"(帮我|请帮我|帮忙|给我|麻烦|我想|我需要|我要|请|收集|采集|获取|找|查找)", "", t)
            kw = re.sub(r"\d+\s*条(新闻|信息|数据|内容|记录)?", "", kw)
            kw = re.sub(r"(从第\s*[一二三四五六七八九十]\s*页开始|从第二页开始|从第三页开始|从第四页开始|第一页|第二页|第三页|第四页)", "", kw)
            kw = re.sub(r"(相关新闻|新闻|信息|数据|内容|记录|的|吧|呢|呀|啊)", "", kw)
            kw = kw.strip(" ，。！？,.")
            return {"keyword": kw, "count": count_v, "start_page": start_v}

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
        if not keyword:
            send("模型未提取到关键词，请重新输入更明确的采集请求")
            self.finish()
            return
        send(f"解析结果：keyword={keyword}，count={count}，start_page={start}")

        baidu = WatchtowerRepository.get_source_by_code("baidu_news", user_name=self.current_user)
        if not baidu:
            WatchtowerRepository.create_default_baidu_source(self.current_user)
            baidu = WatchtowerRepository.get_source_by_code("baidu_news", user_name=self.current_user)

        if not baidu:
            send("未能初始化百度新闻采集源")
            self.finish()
            return

        send(f"正在使用【{baidu['name']}】采集...")
        total_saved = 0
        records_buffer = []
        page_step = int(baidu.get("page_step", 10) or 10)
        max_rounds = max(1, (count + page_step - 1) // page_step + 3)
        round_idx = 0
        current_start = start
        while total_saved < count and round_idx < max_rounds:
            result = WatchtowerRepository.collect(
                source_id=baidu["id"],
                keyword=keyword,
                start_page=current_start,
                item_count=min(page_step, count - total_saved),
                user_name=self.current_user,
            )
            records = result.get("records", [])
            saved = WatchtowerRepository.save_records(records)
            total_saved += saved
            records_buffer.extend(records)
            for item in records:
                send(item["title"])
                self.write(f"data: {json.dumps({'type': 'record', 'record': item}, ensure_ascii=False)}\n\n")
                self.flush()
            current_start += page_step
            round_idx += 1
            if not records:
                break
        send(f"采集结束，共新增 {total_saved} 条")
        self.finish()
        self.finish()


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
