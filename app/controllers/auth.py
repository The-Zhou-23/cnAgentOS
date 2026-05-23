# 认证相关 controller(登录/注册/退出)

# 通过Handler 展示 mvc 中controller层 如何接收表单, 校验输入, 调用model层, 再渲染view层 或 跳转
# 登录态 用 secure cookie 保存username

import tornado.web

from app.controllers.base import BaseHandler
from app.models.user import UserRepository

class LoginHandler(BaseHandler):
	# /auth/login
	# get: 渲染登录页
	# post: 校验用户名和密码, 通过后写入secure cookie 并跳转到目标页
	def get(self):
		# self.write(f"""<h3>登录</h3>
		# 	<form method="post" action="/auth/login">
		# 	<input name="username">
		# 	<input name="password">
		# 	<button type="submit">登录admin</button>
		# 	{self.xsrf_form_html()}
		# 	</form>
		# 	""")
		self.render("login.html",title="登录",error=None)

	def post(self):
		username = (self.get_body_argument("username", "") or "").strip()
		password = self.get_body_argument("password", "")
		if not username or not password:
			self.set_status(400)
			return self.render("login.html", title="登录", error="用户名或密码不能为空或输入了无效数据")

		if not UserRepository.verify_user(username, password):
			self.set_status(401)
			return self.render("login.html", title="登录", error="用户名或密码错误")

		self.set_secure_cookie("username", username)
		self.redirect("/admin/users")


class LogoutHandler(BaseHandler):
	# /auth/logout
	def post(self):
		self.clear_cookie("username")
		self.redirect("/auth/login")