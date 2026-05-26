"""
智能瞭望 - 用户侧控制器
负责用户侧瞭望数据浏览、搜索、筛选
"""
import tornado.web

from app.controllers.base import BaseHandler
from app.models.watchtower import WatchtowerRepository


class PortalWatchListHandler(BaseHandler):
    """用户侧瞭望列表页"""

    @tornado.web.authenticated
    def get(self):
        page = max(1, int(self.get_argument("page", 1)))
        page_size = 20
        keyword = (self.get_argument("keyword", "") or "").strip()
        source_id = self.get_argument("source_id", "")

        if keyword or source_id:
            total, records = WatchtowerRepository.list_records_filtered(
                page=page, page_size=page_size, keyword=keyword, source_id=int(source_id) if source_id else None
            )
        else:
            total, records = WatchtowerRepository.list_records(page=page, page_size=page_size)

        total_pages = max(1, -(-total // page_size))
        sources = WatchtowerRepository.list_sources()
        has_prev = page > 1
        has_next = page < total_pages

        user = self.get_current_user()
        role_name = self.get_current_role_name()

        self.render(
            "portal/watch_list.html",
            title="智能瞭望",
            username=user,
            role_name=role_name,
            active_nav="watch",
            records=records,
            sources=sources,
            page=page,
            total=total,
            total_pages=total_pages,
            has_prev=has_prev,
            has_next=has_next,
            keyword=keyword,
            source_id=source_id,
        )


class PortalWatchDetailHandler(BaseHandler):
    """用户侧瞭望详情页"""

    @tornado.web.authenticated
    def get(self, record_id):
        record = WatchtowerRepository.get_record(int(record_id))
        if not record:
            self.set_status(404)
            self.write("记录不存在")
            return

        user = self.get_current_user()
        role_name = self.get_current_role_name()

        self.render(
            "portal/watch_detail.html",
            title=record["title"],
            username=user,
            role_name=role_name,
            active_nav="watch",
            record=record,
        )
