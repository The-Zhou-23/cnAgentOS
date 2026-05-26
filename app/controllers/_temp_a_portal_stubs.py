"""
【临时文件 - 成员 A】
用途：为门户首页功能卡片提供占位路由，待成员 C/D/E 实现正式页面后删除。
对应正式路由：
  - /portal/query            -> 成员 E（智能问数）
  - /portal/watch            -> 成员 C（智能瞭望）
  - /portal/digital-employee -> 成员 D（数字员工）
"""

import tornado.web

from app.controllers.base import BaseHandler


class _TempPortalStubHandler(BaseHandler):
    stub_title = "功能开发中"
    stub_desc = ""
    owner = ""
    active_nav = ""

    @tornado.web.authenticated
    def get(self):
        user = self.get_current_user()
        role_name = self.get_current_role_name()
        self.render(
            "_temp_a_portal_stub.html",
            title=self.stub_title,
            username=user,
            role_name=role_name,
            active_nav=self.active_nav,
            stub_title=self.stub_title,
            stub_desc=self.stub_desc,
            owner=self.owner,
        )


class TempPortalQueryHandler(_TempPortalStubHandler):
    stub_title = "智能问数"
    stub_desc = "自然语言提问，获取业务数据答案与结构化结果。"
    owner = "成员 E"
    active_nav = "query"


class TempPortalWatchHandler(_TempPortalStubHandler):
    stub_title = "智能瞭望"
    stub_desc = "浏览已采集的数据瞭望内容，掌握关键动态与资讯信息。"
    owner = "成员 C"
    active_nav = "watch"


class TempPortalDigitalEmployeeHandler(_TempPortalStubHandler):
    stub_title = "数字员工"
    stub_desc = "与面向业务场景的数字助手交互，获得更贴近工作的智能服务。"
    owner = "成员 D"
    active_nav = "digital"
