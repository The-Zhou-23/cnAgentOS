# Controller 公共基础类（BaseHandler）
"""
在tornado中
- 每一个Url对应一个RequestHandler 可以理解为Controller
- RequestHandler 提供 post / get 等方法来处理http请求

本程序可以提供一个统一的基础类，用于处理一些公共业务,如登录态的处理或获得逻辑，供其他Handler继承使用
"""
import functools
import tornado.web

from app.models.user import UserRepository
from app.models.rbac import RBACRepository


class BaseHandler(tornado.web.RequestHandler):
	# 公共类的用户态认证机制：
	# - 框架会通过 xxxx() 的返回值来判断是否"已经登录"
	# - 如果返回None 则 @tornado.web.authenticated 触发跳转到指定的路由url: login
	def get_current_user(self):
		# 返回当前登录用户的字符串 或 None
		username = self.get_secure_cookie("username")
		if not username:
			return None
		return username.decode('utf-8')

	def get_current_user_record(self):
		username = self.get_current_user()
		if not username:
			return None
		return UserRepository.get_user_by_username(username)


class AdminBaseHandler(BaseHandler):
	def prepare(self):
		if self.request.path.rstrip("/") == "/admin/login":
			return
		username = self.get_current_user()
		if not username:
			return
		user = UserRepository.get_user_by_username(username)
		role_code = UserRepository.get_role_code(user)
		if not UserRepository.is_admin_role(role_code):
			self.redirect("/")
			self.finish()


def require_permission(permission_code: str):
	def decorator(method):
		@functools.wraps(method)
		def wrapper(self, *args, **kwargs):
			username = self.get_current_user()
			if not username:
				self.redirect("/auth/login")
				return
			user = UserRepository.get_user_by_username(username)
			role_code = UserRepository.get_role_code(user)
			if role_code == "super_admin":
				return method(self, *args, **kwargs)
			if role_code == "normal_admin":
				from app.models.db import get_connection
				with get_connection() as conn:
					perm_row = conn.execute("select id from permissions where code = ?", (permission_code,)).fetchone()
					if not perm_row:
						self.set_status(403)
						return self.render("admin/403.html", title="无权限", username=username)
					perm_id = perm_row["id"]
					role_row = conn.execute("select id from roles where code = ?", (role_code,)).fetchone()
					if not role_row:
						self.set_status(403)
						return self.render("admin/403.html", title="无权限", username=username)
					has_perm = RBACRepository.get_role_permissions(role_row["id"])
					if perm_id in has_perm:
						return method(self, *args, **kwargs)
				self.set_status(403)
				return self.render("admin/403.html", title="无权限", username=username)
			self.set_status(403)
			return self.render("admin/403.html", title="无权限", username=username)
		return wrapper
	return decorator