import sqlite3

from app.models.db import get_connection


DEFAULT_CHUANXIAONONG_PROMPT = """你是川小农，面向四川地区人才、就业、薪资与产业发展场景的专业文案编写助手。
你擅长撰写正式、严谨、结构清晰、可直接用于 Word 文档的介绍文案、报告材料、宣传稿、专题汇报和调研内容，并能把 AI、计算机科学与技术、数据库、信息安全、物联网、智慧农业等技术方向与四川本地产业、岗位需求、人才培养、就业趋势和薪资变化结合起来。

工作原则：
1. 先识别用户需求类型，再决定输出主题、提纲、正文或简短答复。
2. 用户提出介绍、解释、简单说说等需求时，可以直接生成正式介绍内容。
3. 用户提出写报告、写宣传稿、写专题材料等需求时，优先先给推荐主题和大纲，再按需要逐章节生成。
4. 用户未提供充分信息时，先补充必要的地区、行业、技术方向或篇幅要求，不要自行虚构结论。
5. 输出语言必须正式、准确、条理清晰，避免口语化、娱乐化表达。
6. 需要回答“你是谁”时，可直接说明：我是川小农，一名面向四川地区人才、就业、薪资与产业发展场景的专业文案编写助手。

写作要求：
- 默认结合四川地区实际展开；
- 优先围绕人才、就业、薪资、产业升级、岗位需求、产教融合等主题；
- 长文先结构后正文，短问可直接回答；
- 不得编造精确数据、政策名称或机构结论。
"""


class DigitalEmployeeRepository:
    @staticmethod
    def list_employees():
        with get_connection() as conn:
            return conn.execute("select * from digital_employees order by is_enabled desc, id desc").fetchall()

    @staticmethod
    def get_employee(employee_id: int):
        with get_connection() as conn:
            return conn.execute("select * from digital_employees where id = ?", (employee_id,)).fetchone()

    @staticmethod
    def get_employee_by_alias(alias: str):
        with get_connection() as conn:
            return conn.execute("select * from digital_employees where alias = ? and is_enabled = 1", (alias,)).fetchone()

    @staticmethod
    def create_employee(data: dict) -> bool:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    insert into digital_employees(alias, description, employee_type, model_service_id, api_interface_id, prompt, config_json, is_enabled)
                    values(?,?,?,?,?,?,?,?)
                    """,
                    (
                        data.get("alias"),
                        data.get("description", ""),
                        data.get("employee_type", "model"),
                        data.get("model_service_id"),
                        data.get("api_interface_id"),
                        data.get("prompt", ""),
                        data.get("config_json", "{}"),
                        int(data.get("is_enabled", 1)),
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def update_employee(employee_id: int, data: dict) -> bool:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    update digital_employees set
                        alias=?, description=?, employee_type=?, model_service_id=?, api_interface_id=?, prompt=?, config_json=?, is_enabled=?, updated_at=datetime('now')
                    where id=?
                    """,
                    (
                        data.get("alias"),
                        data.get("description", ""),
                        data.get("employee_type", "model"),
                        data.get("model_service_id"),
                        data.get("api_interface_id"),
                        data.get("prompt", ""),
                        data.get("config_json", "{}"),
                        int(data.get("is_enabled", 1)),
                        employee_id,
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def delete_employee(employee_id: int) -> None:
        with get_connection() as conn:
            conn.execute("delete from digital_employees where id = ?", (employee_id,))

    @staticmethod
    def ensure_defaults():
        from app.models.api_interface import APIInterfaceRepository
        from app.models.model_service import ModelServiceRepository

        system_model = ModelServiceRepository.get_system_model()
        interfaces = {row["name"]: row["id"] for row in APIInterfaceRepository.list_interfaces()}
        defaults = [
            {
                "alias": "川小农",
                "description": "基于默认模型 + 提示词的智能对话数字员工",
                "employee_type": "model",
                "model_service_id": system_model["id"] if system_model else None,
                "api_interface_id": None,
                "prompt": DEFAULT_CHUANXIAONONG_PROMPT,
                "config_json": "{}",
                "is_enabled": 1,
            },
            {
                "alias": "天气",
                "description": "基于接口管理中的天气 API 返回数据",
                "employee_type": "api",
                "model_service_id": None,
                "api_interface_id": interfaces.get("天气 API"),
                "prompt": "仅提取城市名称，不要扩写；若未识别城市，直接提示未识别出城市。",
                "config_json": "{}",
                "is_enabled": 1,
            },
            {
                "alias": "音乐",
                "description": "基于接口管理中的音乐 API 返回数据",
                "employee_type": "api",
                "model_service_id": None,
                "api_interface_id": interfaces.get("音乐 API"),
                "prompt": "仅识别音乐请求意图，优先提取随机播放、歌名或歌手信息，不要扩写。",
                "config_json": "{}",
                "is_enabled": 1,
            },
        ]
        with get_connection() as conn:
            for item in defaults:
                existing = conn.execute("select id from digital_employees where alias = ?", (item["alias"],)).fetchone()
                if existing:
                    conn.execute(
                        """
                        update digital_employees set
                            description=?, employee_type=?, model_service_id=?, api_interface_id=?, prompt=?, config_json=?, is_enabled=?, updated_at=datetime('now')
                        where alias=?
                        """,
                        (
                            item["description"],
                            item["employee_type"],
                            item["model_service_id"],
                            item["api_interface_id"],
                            item["prompt"],
                            item["config_json"],
                            item["is_enabled"],
                            item["alias"],
                        ),
                    )
                else:
                    conn.execute(
                        """
                        insert into digital_employees(alias, description, employee_type, model_service_id, api_interface_id, prompt, config_json, is_enabled)
                        values(?,?,?,?,?,?,?,?)
                        """,
                        (
                            item["alias"],
                            item["description"],
                            item["employee_type"],
                            item["model_service_id"],
                            item["api_interface_id"],
                            item["prompt"],
                            item["config_json"],
                            item["is_enabled"],
                        ),
                    )
