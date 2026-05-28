import json
import re
import sqlite3
from html import unescape
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen

from app.models.db import get_connection


class WatchtowerRepository:
    @staticmethod
    def list_sources():
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("select * from watch_sources order by is_enabled desc, id desc").fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_source(source_id: int):
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("select * from watch_sources where id = ?", (source_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def create_source(data: dict) -> bool:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    insert into watch_sources(name, source_code, entry_urls_json, headers_json, keywords_label,
                                              page_param_name, page_step, collect_limit, is_enabled, note,
                                              parse_rules_json, base_url)
                    values(?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        data.get("name"),
                        data.get("source_code"),
                        json.dumps(data.get("entry_urls", []), ensure_ascii=False),
                        json.dumps(data.get("headers", {}), ensure_ascii=False),
                        data.get("keywords_label", "关键字"),
                        data.get("page_param_name", "pn"),
                        int(data.get("page_step", 10)),
                        int(data.get("collect_limit", 10)),
                        int(data.get("is_enabled", 1)),
                        data.get("note", ""),
                        json.dumps(data.get("parse_rules", {}), ensure_ascii=False),
                        data.get("base_url", ""),
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def update_source(source_id: int, data: dict) -> bool:
        with get_connection() as conn:
            conn.execute(
                """
                update watch_sources set
                    name=?, source_code=?, entry_urls_json=?, headers_json=?, keywords_label=?,
                    page_param_name=?, page_step=?, collect_limit=?, is_enabled=?, note=?, 
                    parse_rules_json=?, base_url=?, updated_at=datetime('now')
                where id=?
                """,
                (
                    data.get("name"),
                    data.get("source_code"),
                    json.dumps(data.get("entry_urls", []), ensure_ascii=False),
                    json.dumps(data.get("headers", {}), ensure_ascii=False),
                    data.get("keywords_label", "关键字"),
                    data.get("page_param_name", "pn"),
                    int(data.get("page_step", 10)),
                    int(data.get("collect_limit", 10)),
                    int(data.get("is_enabled", 1)),
                    data.get("note", ""),
                    json.dumps(data.get("parse_rules", {}), ensure_ascii=False),
                    data.get("base_url", ""),
                    source_id,
                ),
            )
        return True

    @staticmethod
    def delete_source(source_id: int) -> None:
        with get_connection() as conn:
            conn.execute("delete from watch_sources where id = ?", (source_id,))

    @staticmethod
    def _build_url(source, keyword: str, start_page: int):
        """根据采集源配置动态构建URL"""
        entry_urls = json.loads(source.get("entry_urls_json", "[]"))
        page_param_name = source.get("page_param_name", "pn")
        page_step = source.get("page_step", 10)
        
        if start_page <= 0:
            url = entry_urls[0] if entry_urls else ""
        else:
            url = entry_urls[1] if len(entry_urls) > 1 else entry_urls[0] if entry_urls else ""
        
        # 替换关键字
        keyword_label = source.get("keywords_label", "关键字")
        url = url.replace("{" + keyword_label + "}", quote(keyword, safe=""))
        
        # 替换分页参数
        if start_page > 0 and page_param_name:
            page_value = (start_page - 1) * page_step
            url = url.replace("{分页步进}", str(page_value))
            url = url.replace("{" + page_param_name + "}", str(page_value))
        
        return url

    @staticmethod
    def _fetch_html(url: str, headers_json: str = "{}"):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        try:
            extra = json.loads(headers_json or "{}")
            if isinstance(extra, dict):
                headers.update({str(k): str(v) for k, v in extra.items() if v is not None})
        except Exception:
            pass
        req = Request(url, headers=headers)
        with urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="ignore")

    @staticmethod
    def _parse_items(html: str, source):
        """根据采集源配置动态解析内容"""
        parse_rules = json.loads(source.get("parse_rules_json", "{}"))
        base_url = source.get("base_url", "")
        
        # 使用配置的解析规则或默认规则
        patterns = parse_rules.get("title_patterns", [])
        if not patterns:
            # 默认规则
            patterns = [
                r"<h3[^>]*class=\"[^\"]*news-title[^\"]*\"[^>]*>.*?<a[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>",
                r"<h3[^>]*>.*?<a[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>",
                r"<a[^>]*class=\"[^\"]*news-title[^\"]*\"[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>",
                r"<a[^>]*class=\"[^\"]*title[^\"]*\"[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>",
            ]
        
        items = []
        seen_titles = set()
        
        for pat in patterns:
            matches = re.findall(pat, html, flags=re.S | re.I)
            for href, m in matches:
                text = re.sub(r"<[^>]+>", "", m)
                text = unescape(re.sub(r"\s+", " ", text)).strip()
                if text and text not in seen_titles:
                    seen_titles.add(text)
                    # 处理相对链接
                    if href.startswith("/"):
                        href = urljoin(base_url or "https://www.baidu.com", href)
                    elif not href.startswith("http"):
                        href = urljoin(base_url or "https://www.baidu.com", href)
                    items.append({"title": text, "url": href})
        
        # 如果没有找到结果，使用通用规则
        if not items:
            generic = re.findall(r"<a[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", html, flags=re.S | re.I)
            for href, m in generic:
                text = re.sub(r"<[^>]+>", "", m)
                text = unescape(re.sub(r"\s+", " ", text)).strip()
                if len(text) >= 6 and text not in seen_titles:
                    seen_titles.add(text)
                    if href.startswith("/"):
                        href = urljoin(base_url or "https://www.baidu.com", href)
                    elif not href.startswith("http"):
                        href = urljoin(base_url or "https://www.baidu.com", href)
                    items.append({"title": text, "url": href})
        
        return items

    @staticmethod
    def is_url_exists(url: str) -> bool:
        """检查URL是否已存在于数据库中（增量采集检测）"""
        with get_connection() as conn:
            result = conn.execute("select id from watch_records where url = ?", (url,)).fetchone()
            return result is not None

    @staticmethod
    def collect(source_id: int, keyword: str, start_page: int, item_count: int, incremental=True):
        """
        采集数据
        :param incremental: 是否启用增量采集（跳过已存在的URL）
        """
        source = WatchtowerRepository.get_source(source_id)
        if not source:
            return {"records": [], "skipped": 0}
        
        url = WatchtowerRepository._build_url(source, keyword, start_page)
        html = WatchtowerRepository._fetch_html(url, source["headers_json"])
        items = WatchtowerRepository._parse_items(html, source)
        
        rows = []
        skipped = 0
        
        for idx, item in enumerate(items[: max(1, item_count)], start=1):
            # 增量采集：检查URL是否已存在
            if incremental and WatchtowerRepository.is_url_exists(item["url"]):
                skipped += 1
                continue
                
            rows.append(
                {
                    "source_id": source_id,
                    "source_name": source["name"],
                    "keyword": keyword,
                    "title": item["title"],
                    "content": "",
                    "url": item["url"],
                }
            )
        
        return {"records": rows, "skipped": skipped}

    @staticmethod
    def save_records(records: list[dict]):
        if not records:
            return 0
        with get_connection() as conn:
            count = 0
            for record in records:
                # 再次检查避免竞态条件
                exists = conn.execute("select id from watch_records where url = ?", (record["url"],)).fetchone()
                if not exists:
                    conn.execute(
                        """
                        insert into watch_records(source_id, source_name, keyword, title, content, url)
                        values(?,?,?,?,?,?)
                        """,
                        (
                            record["source_id"],
                            record["source_name"],
                            record["keyword"],
                            record["title"],
                            record["content"],
                            record["url"],
                        ),
                    )
                    count += 1
            return count

    @staticmethod
    def list_records(page: int = 1, page_size: int = 20):
        offset = (page - 1) * page_size
        with get_connection() as conn:
            total = conn.execute("select count(1) as c from watch_records").fetchone()["c"]
            rows = conn.execute(
                "select * from watch_records order by id desc limit ? offset ?",
                (page_size, offset),
            ).fetchall()
        return int(total), rows

    @staticmethod
    def list_records_filtered(page: int = 1, page_size: int = 20, keyword: str = None, source_id: int = None):
        """支持关键词和来源筛选的查询"""
        offset = (page - 1) * page_size
        conditions = []
        params = []
        if keyword:
            conditions.append("keyword LIKE ? OR title LIKE ?")
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        if source_id:
            conditions.append("source_id = ?")
            params.append(source_id)

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        count_sql = f"select count(1) as c from watch_records{where_clause}"
        data_sql = f"select * from watch_records{where_clause} order by id desc limit ? offset ?"
        params.extend([page_size, offset])

        with get_connection() as conn:
            total = conn.execute(count_sql, params[:-2] if conditions else []).fetchone()["c"]
            rows = conn.execute(data_sql, params).fetchall()
        return int(total), rows

    @staticmethod
    def get_record(record_id: int):
        """获取单条采集记录"""
        with get_connection() as conn:
            return conn.execute("select * from watch_records where id = ?", (record_id,)).fetchone()

    @staticmethod
    def delete_record(record_id: int):
        with get_connection() as conn:
            conn.execute("delete from watch_records where id = ?", (record_id,))

    @staticmethod
    def batch_delete_records(ids: list[int]):
        if not ids:
            return
        placeholders = ",".join(["?"] * len(ids))
        with get_connection() as conn:
            conn.execute(f"delete from watch_records where id in ({placeholders})", ids)

    @staticmethod
    def init_default_sources():
        """初始化默认采集源"""
        sources = [
            {
                "name": "百度新闻",
                "source_code": "baidu_news",
                "entry_urls": [
                    "https://www.baidu.com/s?ie=utf-8&bsst=1&rsv_dl=news_t_sk&tn=news&cl=2&medium=0&rtt=1&wd={关键词}",
                    "https://www.baidu.com/s?ie=utf-8&bsst=1&rsv_dl=news_b_pn&tn=news&cl=2&medium=0&rtt=1&wd={关键词}&pn={分页步进}"
                ],
                "headers": {},
                "keywords_label": "关键词",
                "page_param_name": "pn",
                "page_step": 10,
                "collect_limit": 10,
                "is_enabled": 1,
                "note": "百度新闻专用采集源",
                "parse_rules": {},
                "base_url": "https://www.baidu.com"
            },
            {
                "name": "新浪新闻",
                "source_code": "sina_news",
                "entry_urls": [
                    "https://search.sina.com.cn/?q={关键词}&c=news&from=channel&ie=utf-8",
                    "https://search.sina.com.cn/?q={关键词}&c=news&from=channel&ie=utf-8&page={分页步进}"
                ],
                "headers": {},
                "keywords_label": "关键词",
                "page_param_name": "page",
                "page_step": 1,
                "collect_limit": 10,
                "is_enabled": 1,
                "note": "新浪新闻搜索采集源",
                "parse_rules": {
                    "title_patterns": [
                        r"<h2[^>]*>.*?<a[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>",
                        r"<a[^>]*class=\"[^\"]*news-item-title[^\"]*\"[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>",
                        r"<a[^>]*class=\"[^\"]*title[^\"]*\"[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>"
                    ]
                },
                "base_url": "https://search.sina.com.cn"
            },
            {
                "name": "腾讯新闻",
                "source_code": "qq_news",
                "entry_urls": [
                    "https://news.qq.com/search?query={关键词}",
                    "https://news.qq.com/search?query={关键词}&page={分页步进}"
                ],
                "headers": {},
                "keywords_label": "关键词",
                "page_param_name": "page",
                "page_step": 1,
                "collect_limit": 10,
                "is_enabled": 1,
                "note": "腾讯新闻搜索采集源",
                "parse_rules": {
                    "title_patterns": [
                        r"<div[^>]*class=\"[^\"]*news-item[^\"]*\"[^>]*>.*?<a[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>",
                        r"<a[^>]*class=\"[^\"]*title-link[^\"]*\"[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>",
                        r"<h3[^>]*>.*?<a[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>"
                    ]
                },
                "base_url": "https://news.qq.com"
            },
            {
                "name": "网易新闻",
                "source_code": "netease_news",
                "entry_urls": [
                    "https://news.163.com/search/?keyword={关键词}",
                    "https://news.163.com/search/?keyword={关键词}&page={分页步进}"
                ],
                "headers": {},
                "keywords_label": "关键词",
                "page_param_name": "page",
                "page_step": 1,
                "collect_limit": 10,
                "is_enabled": 0,
                "note": "网易新闻搜索采集源",
                "parse_rules": {},
                "base_url": "https://news.163.com"
            }
        ]
        
        with get_connection() as conn:
            for source_data in sources:
                exists = conn.execute("select id from watch_sources where source_code = ?", 
                                    (source_data["source_code"],)).fetchone()
                if not exists:
                    WatchtowerRepository.create_source(source_data)
