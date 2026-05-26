# 认证相关 controller(登录/注册/退出)

import re
import time

import tornado.web

from app.controllers._temp_a_role_helper import get_role_id_by_code
from app.controllers.base import BaseHandler
from app.models.user import UserRepository

_USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,20}$")
_LOGIN_FAIL_LIMIT = 5
_LOGIN_FAIL_WINDOW = 15 * 60
_login_failures: dict[str, list[float]] = {}


def _client_key(handler: BaseHandler, username: str) -> str:
    ip = handler.request.remote_ip or "unknown"
    return f"{ip}:{username.strip().lower()}"


def _is_login_blocked(handler: BaseHandler, username: str) -> bool:
    key = _client_key(handler, username)
    now = time.time()
    attempts = [t for t in _login_failures.get(key, []) if now - t < _LOGIN_FAIL_WINDOW]
    _login_failures[key] = attempts
    return len(attempts) >= _LOGIN_FAIL_LIMIT


def _record_login_failure(handler: BaseHandler, username: str) -> None:
    key = _client_key(handler, username)
    now = time.time()
    attempts = [t for t in _login_failures.get(key, []) if now - t < _LOGIN_FAIL_WINDOW]
    attempts.append(now)
    _login_failures[key] = attempts


def _clear_login_failures(handler: BaseHandler, username: str) -> None:
    _login_failures.pop(_client_key(handler, username), None)


def validate_username(username: str) -> str | None:
    username = (username or "").strip()
    if not username:
        return "用户名不能为空"
    if not _USERNAME_PATTERN.match(username):
        return "用户名需为 3～20 位字母、数字或下划线"
    return None


def validate_password(password: str, confirm: str | None = None) -> str | None:
    if not password:
        return "密码不能为空"
    if len(password) < 6 or len(password) > 32:
        return "密码长度需为 6～32 位"
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "密码需同时包含字母和数字"
    if confirm is not None and password != confirm:
        return "两次输入的密码不一致"
    return None


class LoginHandler(BaseHandler):
    def get(self):
        login_type = self.get_argument("type", "user")
        if login_type not in ("user", "admin"):
            login_type = "user"
        success = self.get_argument("success", None)
        self.render(
            "login.html",
            title="登录",
            error=None,
            success=success,
            login_type=login_type,
        )

    def post(self):
        username = (self.get_body_argument("username", "") or "").strip()
        password = self.get_body_argument("password", "")
        login_type = self.get_body_argument("login_type", "user")
        if login_type not in ("user", "admin"):
            login_type = "user"

        if not username or not password:
            self.set_status(400)
            return self.render(
                "login.html",
                title="登录",
                error="用户名或密码不能为空",
                success=None,
                login_type=login_type,
            )

        if _is_login_blocked(self, username):
            self.set_status(429)
            return self.render(
                "login.html",
                title="登录",
                error=f"登录失败次数过多，请 {_LOGIN_FAIL_WINDOW // 60} 分钟后再试",
                success=None,
                login_type=login_type,
            )

        user = UserRepository.get_user_by_username(username)
        if not user or not UserRepository.verify_user(username, password):
            _record_login_failure(self, username)
            self.set_status(401)
            return self.render(
                "login.html",
                title="登录",
                error="用户名或密码错误",
                success=None,
                login_type=login_type,
            )

        role_code = UserRepository.get_role_code(user)
        is_admin = UserRepository.is_admin_role(role_code)
        is_normal_user = UserRepository.is_normal_user_role(role_code)

        if login_type == "admin":
            if not is_admin:
                self.set_status(403)
                return self.render(
                    "login.html",
                    title="登录",
                    error="该账号不是管理员，请使用普通用户入口登录",
                    success=None,
                    login_type=login_type,
                )
        else:
            if not is_normal_user:
                self.set_status(403)
                return self.render(
                    "login.html",
                    title="登录",
                    error="该账号不是普通用户，请使用管理员入口登录",
                    success=None,
                    login_type=login_type,
                )

        _clear_login_failures(self, username)
        self.set_secure_cookie("username", username)
        if login_type == "admin":
            self.redirect("/admin/users")
        else:
            self.redirect("/")


class RegisterHandler(BaseHandler):
    def get(self):
        self.render("register.html", title="注册", error=None, form={})

    def post(self):
        username = (self.get_body_argument("username", "") or "").strip()
        password = self.get_body_argument("password", "")
        confirm = self.get_body_argument("confirm_password", "")
        form = {"username": username}

        username_error = validate_username(username)
        if username_error:
            self.set_status(400)
            return self.render("register.html", title="注册", error=username_error, form=form)

        password_error = validate_password(password, confirm)
        if password_error:
            self.set_status(400)
            return self.render("register.html", title="注册", error=password_error, form=form)

        if UserRepository.get_user_by_username(username):
            self.set_status(409)
            return self.render("register.html", title="注册", error="用户名已存在，请更换后重试", form=form)

        role_id = get_role_id_by_code("normal_user")
        if role_id is None:
            self.set_status(500)
            return self.render(
                "register.html",
                title="注册",
                error="系统尚未初始化普通用户角色，请联系管理员",
                form=form,
            )

        if not UserRepository.create_user(username, password, role_id):
            self.set_status(409)
            return self.render("register.html", title="注册", error="用户名已存在，请更换后重试", form=form)

        self.set_secure_cookie("username", username)
        self.redirect("/")


class LogoutHandler(BaseHandler):
    def post(self):
        self.clear_cookie("username")
        self.redirect("/auth/login")
