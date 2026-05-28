import json

import tornado.web

from app.controllers.base import AdminBaseHandler
from app.models.scheduler import SchedulerRepository
from app.models.user import UserRepository
from app.models.rbac import RBACRepository


SUPER_ONLY_MSG = "仅超级管理员可操作"


def _check_super(self):
    user = UserRepository.get_user_by_username(self.current_user)
    role_code = UserRepository.get_role_code(user)
    if role_code != "super_admin":
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.finish(json.dumps({"ok": False, "error": SUPER_ONLY_MSG}, ensure_ascii=False))
        return False
    return True


class AdminAutomationListHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        jobs = SchedulerRepository.list_jobs()
        for job in jobs:
            try:
                cfg = json.loads(job.get("config_json", "{}")) if job.get("config_json") else {}
            except (json.JSONDecodeError, TypeError):
                cfg = {}
            job["_keyword"] = cfg.get("keyword", "-")
            job["_item_count"] = cfg.get("item_count", 10)
            job["_max_pages"] = cfg.get("max_pages", 1)
        logs = SchedulerRepository.get_logs(limit=20)
        user = UserRepository.get_user_by_username(self.current_user)
        current_role_code = UserRepository.get_role_code(user)
        self.render(
            "admin/automation.html",
            title="自动化调度",
            username=self.current_user,
            jobs=jobs,
            logs=logs,
            current_role_code=current_role_code,
        )


class AdminAutomationCreateHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self):
        if not _check_super(self):
            return
        name = (self.get_body_argument("name", "") or "").strip()
        minute = (self.get_body_argument("minute", "*") or "*").strip()
        hour = (self.get_body_argument("hour", "*") or "*").strip()
        day = (self.get_body_argument("day", "*") or "*").strip()
        month = (self.get_body_argument("month", "*") or "*").strip()
        week = (self.get_body_argument("week", "*") or "*").strip()
        keyword = (self.get_body_argument("keyword", "人工智能") or "人工智能").strip()
        item_count = int(self.get_body_argument("item_count", 10) or 10)
        max_pages = int(self.get_body_argument("max_pages", 1) or 1)

        cron_expr = f"{minute} {hour} {day} {month} {week}"
        config_json = json.dumps({"keyword": keyword, "item_count": item_count, "max_pages": max_pages, "source_id": None}, ensure_ascii=False)

        job_id = SchedulerRepository.create_job({"name": name, "cron_expr": cron_expr, "config_json": config_json})
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.finish(json.dumps({"ok": True, "job_id": job_id}, ensure_ascii=False))


class AdminAutomationUpdateHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self, job_id):
        if not _check_super(self):
            return
        job_id = int(job_id)
        name = (self.get_body_argument("name", "") or "").strip()
        minute = (self.get_body_argument("minute", "*") or "*").strip()
        hour = (self.get_body_argument("hour", "*") or "*").strip()
        day = (self.get_body_argument("day", "*") or "*").strip()
        month = (self.get_body_argument("month", "*") or "*").strip()
        week = (self.get_body_argument("week", "*") or "*").strip()
        keyword = (self.get_body_argument("keyword", "人工智能") or "人工智能").strip()
        item_count = int(self.get_body_argument("item_count", 10) or 10)
        max_pages = int(self.get_body_argument("max_pages", 1) or 1)

        cron_expr = f"{minute} {hour} {day} {month} {week}"
        config_json = json.dumps({"keyword": keyword, "item_count": item_count, "max_pages": max_pages, "source_id": None}, ensure_ascii=False)

        SchedulerRepository.update_job(job_id, {"name": name, "cron_expr": cron_expr, "config_json": config_json})
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.finish(json.dumps({"ok": True}, ensure_ascii=False))


class AdminAutomationDeleteHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self, job_id):
        if not _check_super(self):
            return
        job_id = int(job_id)
        SchedulerRepository.delete_job(job_id)
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.finish(json.dumps({"ok": True}, ensure_ascii=False))


class AdminAutomationToggleHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self, job_id):
        job_id = int(job_id)
        job = SchedulerRepository.get_job(job_id)
        if not job:
            self.set_header("Content-Type", "application/json; charset=utf-8")
            self.finish(json.dumps({"ok": False, "error": "任务不存在"}, ensure_ascii=False))
            return
        enabled = not job["is_enabled"]
        SchedulerRepository.toggle_job(job_id, enabled)
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.finish(json.dumps({"ok": True, "enabled": enabled}, ensure_ascii=False))


class AdminAutomationRunHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def post(self, job_id):
        job_id = int(job_id)
        job = SchedulerRepository.get_job(job_id)
        if not job:
            self.set_header("Content-Type", "application/json; charset=utf-8")
            self.finish(json.dumps({"ok": False, "error": "任务不存在"}, ensure_ascii=False))
            return

        from app.models.workflow import WorkflowEngine
        try:
            WorkflowEngine._run_watch_collect(job)
            self.set_header("Content-Type", "application/json; charset=utf-8")
            self.finish(json.dumps({"ok": True, "message": "手动执行成功"}, ensure_ascii=False))
        except Exception as e:
            self.set_header("Content-Type", "application/json; charset=utf-8")
            self.finish(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
