import json
import logging
from app.models.scheduler import SchedulerRepository

logger = logging.getLogger(__name__)


class WorkflowEngine:

    @staticmethod
    def check_and_run():
        jobs = SchedulerRepository.list_jobs()
        for job in jobs:
            if not job["is_enabled"]:
                continue
            if not SchedulerRepository.cron_matches(job["cron_expr"]):
                continue
            try:
                WorkflowEngine._run_watch_collect(job)
            except Exception as e:
                logger.error("任务 [%s] 执行失败: %s", job["name"], str(e))
                SchedulerRepository.add_log(job["id"], "fail", str(e))

    @staticmethod
    def _run_watch_collect(job):
        config = json.loads(job["config_json"]) if job["config_json"] else {}
        keyword = config.get("keyword", "人工智能")
        source_id = config.get("source_id")
        item_count = config.get("item_count", 10)
        max_pages = config.get("max_pages", 1)

        from app.models.watchtower import WatchtowerRepository

        try:
            records = WatchtowerRepository.collect(
                source_id=source_id,
                keyword=keyword,
                start_page=1,
                item_count=item_count,
            )
            if records:
                WatchtowerRepository.save_records(records)
            SchedulerRepository.update_last_run(job["id"])
            SchedulerRepository.add_log(job["id"], "success", f"采集完成，关键词={keyword}，获取 {len(records)} 条")
        except Exception as e:
            SchedulerRepository.update_last_run(job["id"])
            raise e
