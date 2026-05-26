import tornado.web

from app.controllers.base import BaseHandler
from app.models.user import UserRepository


class IndexHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        user = UserRepository.get_user_by_username(self.current_user)
        role_code = UserRepository.get_role_code(user)
        if UserRepository.is_admin_role(role_code):
            self.redirect("/admin/users")
            return
        self.render(
            "index.html",
            title="用户首页",
            username=self.current_user,
            role_name=self.get_current_role_name(),
            active_nav="home",
        )
