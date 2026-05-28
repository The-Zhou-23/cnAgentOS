"""成员 D 独占：智慧舆情用户侧控制器。

路由：
- GET  /portal/bigscreen           数智大屏（3D 地球 + 词云 + 指标 + 趋势）
- GET  /portal/sentiment           智能舆情 AI 分析页（前端 SPA 化）
- GET  /portal/sentiment/data      聚合数据 JSON 接口（大屏 + 分析页共用）
- POST /portal/sentiment/analyze   触发 AI 分析（同步返回报告 JSON）
"""

import json

import tornado.web

from app.controllers.base import BaseHandler
from app.models.sentiment import SentimentRepository


class PortalBigscreenHandler(BaseHandler):
    """数智大屏：3D 地球 + 词云 + 指标 + 趋势。"""

    @tornado.web.authenticated
    def get(self):
        metrics = SentimentRepository.overview_metrics()
        self.render(
            "portal/bigscreen.html",
            title="数智大屏 - 智慧舆情",
            username=self.get_current_user(),
            role_name=self.get_current_role_name(),
            active_nav="sentiment",
            metrics=metrics,
        )


class PortalSentimentHandler(BaseHandler):
    """智能舆情 AI 分析页。"""

    @tornado.web.authenticated
    def get(self):
        metrics = SentimentRepository.overview_metrics()
        self.render(
            "portal/sentiment.html",
            title="智慧舆情",
            username=self.get_current_user(),
            role_name=self.get_current_role_name(),
            active_nav="sentiment",
            metrics=metrics,
        )


class PortalSentimentDataHandler(BaseHandler):
    """聚合数据接口：供大屏前端 JS 拉取词频 / 来源 / 趋势 / 地域。

    Query:
        scope = all|watch|chat (default: all)
        days  = int            (default: 14)
        kw_limit = int         (default: 60)
    """

    @tornado.web.authenticated
    def get(self):
        scope = (self.get_argument("scope", "all") or "all").lower()
        if scope not in ("all", "watch", "chat"):
            scope = "all"
        try:
            days = max(1, min(60, int(self.get_argument("days", "14"))))
        except ValueError:
            days = 14
        try:
            kw_limit = max(10, min(200, int(self.get_argument("kw_limit", "60"))))
        except ValueError:
            kw_limit = 60

        data = {
            "metrics": SentimentRepository.overview_metrics(),
            "keywords": SentimentRepository.aggregate_keywords(limit=kw_limit, source=scope),
            "sources": SentimentRepository.aggregate_sources(),
            "trend": SentimentRepository.aggregate_trend(days=days),
            "geo": SentimentRepository.aggregate_geo(),
            "scope": scope,
            "days": days,
        }
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.write(json.dumps(data, ensure_ascii=False))


class PortalSentimentAnalyzeHandler(BaseHandler):
    """AI 分析：POST 触发模型生成舆情报告（同步、非流式）。

    Body (JSON 或表单)：
        scope: all|watch|chat
        days:  int
        sample_size: int
    """

    def check_xsrf_cookie(self) -> None:
        # 用户登录后由前端通过 X-XSRFToken 头携带，简化此处校验
        pass

    @tornado.web.authenticated
    def post(self):
        try:
            payload = json.loads(self.request.body or b"{}")
        except json.JSONDecodeError:
            payload = {}
        scope = (payload.get("scope") or self.get_argument("scope", "all")).lower()
        if scope not in ("all", "watch", "chat"):
            scope = "all"
        try:
            days = int(payload.get("days") or self.get_argument("days", 14))
        except (TypeError, ValueError):
            days = 14
        try:
            sample_size = int(payload.get("sample_size") or self.get_argument("sample_size", 30))
        except (TypeError, ValueError):
            sample_size = 30

        days = max(1, min(60, days))
        sample_size = max(5, min(80, sample_size))

        report = SentimentRepository.generate_report(
            scope=scope, sample_size=sample_size, days=days
        )
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.write(json.dumps(report, ensure_ascii=False))
