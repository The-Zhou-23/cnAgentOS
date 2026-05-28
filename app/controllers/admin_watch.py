"""
瞭望管理 - 管理侧控制器
负责瞭望数据源管理、采集执行、采集记录管理
"""
import json
import re

import tornado.web

from app.controllers.base import AdminBaseHandler
from app.models.watchtower import WatchtowerRepository


class AdminWatchSourceListHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        sources = WatchtowerRepository.list_sources()
        if not sources:
            # 初始化默认采集源
            WatchtowerRepository.init_default_sources()
            sources = WatchtowerRepository.list_sources()
        self.render("admin/watch_sources.html", title="瞭望数据源管理", username=self.current_user, sources=sources)


class AdminWatchSourceCreateHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        data = {
            "name": (self.get_body_argument("name", "") or "").strip(),
            "source_code": (self.get_body_argument("source_code", "") or "").strip(),
            "entry_urls": json.loads(self.get_body_argument("entry_urls", "[]") or "[]"),
            "headers": json.loads(self.get_body_argument("headers", "{}") or "{}"),
            "keywords_label": (self.get_body_argument("keywords_label", "关键字") or "").strip(),
            "page_param_name": (self.get_body_argument("page_param_name", "pn") or "").strip(),
            "page_step": int(self.get_body_argument("page_step", 10) or 10),
            "collect_limit": int(self.get_body_argument("collect_limit", 10) or 10),
            "is_enabled": int(self.get_body_argument("is_enabled", 1) or 1),
            "note": (self.get_body_argument("note", "") or "").strip(),
            "parse_rules": json.loads(self.get_body_argument("parse_rules", "{}") or "{}"),
            "base_url": (self.get_body_argument("base_url", "") or "").strip(),
        }
        if data["name"] and data["source_code"]:
            WatchtowerRepository.create_source(data)
        self.redirect("/admin/watch-sources")


class AdminWatchSourceUpdateHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self, source_id):
        data = {
            "name": (self.get_body_argument("name", "") or "").strip(),
            "source_code": (self.get_body_argument("source_code", "") or "").strip(),
            "entry_urls": json.loads(self.get_body_argument("entry_urls", "[]") or "[]"),
            "headers": json.loads(self.get_body_argument("headers", "{}") or "{}"),
            "keywords_label": (self.get_body_argument("keywords_label", "关键字") or "").strip(),
            "page_param_name": (self.get_body_argument("page_param_name", "pn") or "").strip(),
            "page_step": int(self.get_body_argument("page_step", 10) or 10),
            "collect_limit": int(self.get_body_argument("collect_limit", 10) or 10),
            "is_enabled": int(self.get_body_argument("is_enabled", 1) or 1),
            "note": (self.get_body_argument("note", "") or "").strip(),
            "parse_rules": json.loads(self.get_body_argument("parse_rules", "{}") or "{}"),
            "base_url": (self.get_body_argument("base_url", "") or "").strip(),
        }
        WatchtowerRepository.update_source(int(source_id), data)
        self.redirect("/admin/watch-sources")


class AdminWatchSourceDeleteHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self, source_id):
        WatchtowerRepository.delete_source(int(source_id))
        self.redirect("/admin/watch-sources")


class AdminWatchCollectHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        """SSE 流式采集接口"""
        prompt = (self.get_body_argument("prompt", "") or "").strip()
        source_id = self.get_body_argument("source_id", None)
        item_count = int(self.get_body_argument("item_count", 10) or 10)
        max_pages = int(self.get_body_argument("max_pages", 1) or 1)
        incremental = self.get_body_argument("incremental", "true").lower() == "true"

        if not prompt:
            self.set_header("Content-Type", "text/event-stream; charset=utf-8")
            self.set_header("Cache-Control", "no-cache")
            self.set_header("Connection", "keep-alive")
            self.write("data: {}\n\n")
            self.flush()
            self.finish()
            return

        # 从 prompt 中提取关键词和数量
        keyword, count = self._extract_keyword_and_count(prompt, item_count)

        # 确定采集源
        source_ids = []
        if source_id:
            source_ids = [int(source_id)]
        else:
            sources = WatchtowerRepository.list_sources()
            enabled_sources = [s for s in sources if s["is_enabled"]]
            source_ids = [s["id"] for s in enabled_sources]

        if not source_ids:
            self.set_header("Content-Type", "text/event-stream; charset=utf-8")
            self.set_header("Cache-Control", "no-cache")
            self.set_header("Connection", "keep-alive")
            self.flush()
            self.write("data: {}\n\n")
            self.flush()
            self.finish()
            return

        self.set_header("Content-Type", "text/event-stream; charset=utf-8")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("Connection", "keep-alive")
        self.flush()

        def send(msg: str):
            self.write(f"data: {json.dumps({'message': msg}, ensure_ascii=False)}\n\n")
            self.flush()

        incr_status = "增量" if incremental else "全量"
        send(f"开始{incr_status}采集：关键词「{keyword}」，每页 {count} 条，最多 {max_pages} 页")

        total_collected = 0
        total_skipped = 0

        for src_id in source_ids:
            source = WatchtowerRepository.get_source(src_id)
            send(f"正在从「{source['name']}」采集...")

            for page_idx in range(max_pages):
                start_page = page_idx
                send(f"  正在采集第 {page_idx + 1} 页...")
                try:
                    result = WatchtowerRepository.collect(src_id, keyword, start_page, count, incremental=incremental)
                    records = result["records"]
                    skipped = result["skipped"]

                    if skipped > 0:
                        send(f"  跳过已存在的记录：{skipped} 条")

                    if records:
                        saved = WatchtowerRepository.save_records(records)
                        total_collected += saved
                        for r in records:
                            send(f"  ✓ 采集到：{r['title']}")
                    else:
                        send("  本页无新数据")
                except Exception as e:
                    send(f"  ✗ 第 {page_idx + 1} 页采集失败：{e}")

        send(f"采集完成！共采集 {total_collected} 条新记录")
        self.finish()

    @staticmethod
    def _extract_keyword_and_count(prompt: str, default_count: int):
        """从自然语言中提取关键词和采集数量"""
        # 尝试匹配数量：例如 "10条"、"20条信息"
        count_match = re.search(r"(\d+)\s*条", prompt)
        count = int(count_match.group(1)) if count_match else default_count

        # 尝试匹配关键词：去除数量相关描述后的核心词
        keyword = prompt
        # 去除常见前缀
        keyword = re.sub(r"^(我想|帮我|请|帮我|查询|收集|采集|获取|查找)+", "", keyword)
        # 去除数量描述
        keyword = re.sub(r"\d+\s*条(信息|数据|新闻|内容|记录)?", "", keyword)
        # 去除语气词
        keyword = re.sub(r"(的|了|吗|呢|吧|啊|呀|哦)+", "", keyword)
        keyword = keyword.strip()

        if not keyword:
            keyword = prompt

        return keyword, count


class AdminWatchRecordListHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        page = max(1, int(self.get_argument("page", 1)))
        page_size = 20
        total, records = WatchtowerRepository.list_records(page=page, page_size=page_size)
        total_pages = max(1, -(-total // page_size))  # ceil division
        start_no = total - (page - 1) * page_size
        has_prev = page > 1
        has_next = page < total_pages
        self.render("admin/watch_records.html", title="采集结果", username=self.current_user,
                    records=records, page=page, page_size=page_size, total=total,
                    total_pages=total_pages, start_no=start_no, has_prev=has_prev, has_next=has_next)


class AdminWatchRecordDeleteHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self, record_id):
        WatchtowerRepository.delete_record(int(record_id))
        self.redirect("/admin/watch-records")


class AdminWatchRecordBatchDeleteHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        ids = [int(i) for i in self.get_body_arguments("record_ids")]
        WatchtowerRepository.batch_delete_records(ids)
        self.redirect("/admin/watch-records")
