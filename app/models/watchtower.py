import json
import os
import random
import re
import sqlite3
import time
from html import unescape
from pathlib import Path
from urllib.parse import quote, urljoin, urlencode
from urllib.request import Request, urlopen

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

if load_dotenv:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    print(f"[env] watchtower TIANAPI_AREA_NEWS_KEY loaded={bool(os.getenv('TIANAPI_AREA_NEWS_KEY', '').strip())}")
    print(f"[env] watchtower JUHE_HUABIAN_KEY loaded={bool(os.getenv('JUHE_HUABIAN_KEY', '').strip())}")

from app.models.db import get_connection


class WatchtowerRepository:
    @staticmethod
    def list_sources(user_name: str | None = None):
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            if user_name:
                rows = conn.execute("select * from watch_sources where user_name = ? order by is_enabled desc, id desc", (user_name,)).fetchall()
            else:
                rows = conn.execute("select * from watch_sources order by is_enabled desc, id desc").fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_source(source_id: int, user_name: str | None = None):
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            if user_name:
                row = conn.execute("select * from watch_sources where id = ? and user_name = ?", (source_id, user_name)).fetchone()
            else:
                row = conn.execute("select * from watch_sources where id = ?", (source_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_source_by_code(source_code: str, user_name: str | None = None):
        with get_connection() as conn:
            conn.row_factory = sqlite3.Row
            if user_name:
                row = conn.execute("select * from watch_sources where source_code = ? and user_name = ?", (source_code, user_name)).fetchone()
            else:
                row = conn.execute("select * from watch_sources where source_code = ?", (source_code,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def create_default_baidu_source(user_name: str | None = None):
        data = {
            "user_name": user_name or "",
            "name": "百度新闻",
            "source_code": "baidu_news",
            "entry_urls": [
                "https://www.baidu.com/s?ie=utf-8&bsst=1&rsv_dl=news_t_sk&tn=news&cl=2&medium=0&rtt=1&wd={关键词}",
                "https://www.baidu.com/s?ie=utf-8&bsst=1&rsv_dl=news_b_pn&tn=news&cl=2&medium=0&rtt=1&wd={关键词}&pn={分页步进}",
            ],
            "headers": {},
            "keywords_label": "关键词",
            "page_param_name": "pn",
            "page_step": 10,
            "collect_limit": 10,
            "is_enabled": 1,
            "note": "百度新闻专用采集源",
            "parse_rules": {},
        }
        return WatchtowerRepository.create_source(data)

    @staticmethod
    def create_source(data: dict) -> bool:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    insert into watch_sources(user_name, name, source_code, entry_urls_json, headers_json, parse_rules_json,
                                              keywords_label, page_param_name, page_step, collect_limit, is_enabled, note)
                    values(?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        data.get("user_name", ""),
                        data.get("name"),
                        data.get("source_code"),
                        json.dumps(data.get("entry_urls", []), ensure_ascii=False),
                        json.dumps(data.get("headers", {}), ensure_ascii=False),
                        json.dumps(data.get("parse_rules", {}), ensure_ascii=False),
                        data.get("keywords_label", "关键字"),
                        data.get("page_param_name", "pn"),
                        int(data.get("page_step", 10)),
                        int(data.get("collect_limit", 10)),
                        int(data.get("is_enabled", 1)),
                        data.get("note", ""),
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
                    user_name=?, name=?, source_code=?, entry_urls_json=?, headers_json=?, parse_rules_json=?, keywords_label=?,
                    page_param_name=?, page_step=?, collect_limit=?, is_enabled=?, note=?, updated_at=datetime('now')
                where id=?
                """,
                (
                    data.get("user_name", ""),
                    data.get("name"),
                    data.get("source_code"),
                    json.dumps(data.get("entry_urls", []), ensure_ascii=False),
                    json.dumps(data.get("headers", {}), ensure_ascii=False),
                    json.dumps(data.get("parse_rules", {}), ensure_ascii=False),
                    data.get("keywords_label", "关键字"),
                    data.get("page_param_name", "pn"),
                    int(data.get("page_step", 10)),
                    int(data.get("collect_limit", 10)),
                    int(data.get("is_enabled", 1)),
                    data.get("note", ""),
                    source_id,
                ),
            )
        return True

    @staticmethod
    def delete_source(source_id: int) -> None:
        with get_connection() as conn:
            conn.execute("delete from watch_sources where id = ?", (source_id,))

    @staticmethod
    def _build_url(source, keyword: str, start_page: int, area_name: str = "", word: str = ""):
        """根据采集源配置动态构建URL"""
        entry_urls = json.loads(source.get("entry_urls_json", "[]"))
        page_param_name = source.get("page_param_name", "pn")
        page_step = source.get("page_step", 10)
        source_code = source.get("source_code", "")
        if source_code == "area_news":
            return entry_urls[0] if entry_urls else "https://apis.tianapi.com/areanews/index"
        if source_code == "huabian_news":
            return entry_urls[0] if entry_urls else "https://apis.juhe.cn/fapigx/huabian/query"
        
        if start_page <= 0:
            url = entry_urls[0] if entry_urls else ""
        else:
            url = entry_urls[1] if len(entry_urls) > 1 else entry_urls[0] if entry_urls else ""
        
        keyword_label = source.get("keywords_label", "关键字")
        url = url.replace("{" + keyword_label + "}", quote(keyword, safe=""))
        
        if start_page > 0 and page_param_name:
            page_value = (start_page - 1) * page_step
            url = url.replace("{分页步进}", str(page_value))
            url = url.replace("{" + page_param_name + "}", str(page_value))
        
        return url

    @staticmethod
    def _fetch_html(url: str, headers_json: str = "{}", method: str = "GET", data: dict | None = None):

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        try:
            extra = json.loads(headers_json or "{}")
            if isinstance(extra, dict):
                headers.update({str(k): str(v) for k, v in extra.items() if v is not None})
        except Exception:
            pass
        body = None
        if data is not None:
            body = urlencode(data).encode("utf-8")
        req = Request(url, data=body, headers=headers, method=method)
        with urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        if "百度安全验证" in html or "安全验证" in html:
            raise RuntimeError("百度安全验证拦截，无法获取新闻页")
        return html

    @staticmethod
    def _parse_items(html: str, source):
        """根据采集源配置动态解析内容"""
        parse_rules = json.loads(source.get("parse_rules_json", "{}"))
        base_url = source.get("base_url", "")
        if source.get("source_code") == "area_news":
            return WatchtowerRepository._parse_area_news_items(html, source)
        if source.get("source_code") == "huabian_news":
            return WatchtowerRepository._parse_huabian_news_items(html, source)
        
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
    def _parse_area_news_items(html: str, source):
        try:
            payload = json.loads(html)
        except Exception:
            return []
        if payload.get("code") not in (0, 200):
            return []
        result = payload.get("result") or {}
        items = result.get("list") or []
        rows = []
        for item in items:
            rows.append({
                "id": item.get("id", ""),
                "title": item.get("title", ""),
                "pic": item.get("picUrl", ""),
                "hot": "",
                "time": item.get("ctime", ""),
                "url": item.get("url", ""),
                "mobileUrl": item.get("url", ""),
                "description": item.get("description", ""),
                "source": item.get("source", source.get("name", "")),
            })
        return rows

    @staticmethod
    def _parse_huabian_news_items(html: str, source):
        try:
            payload = json.loads(html)
        except Exception:
            return []
        if payload.get("error_code") != 0:
            return []
        result = payload.get("result") or {}
        items = result.get("newslist") or []
        rows = []
        for item in items:
            rows.append({
                "id": item.get("id", ""),
                "title": item.get("title", ""),
                "pic": item.get("picUrl", ""),
                "hot": "",
                "time": item.get("ctime", ""),
                "url": item.get("url", ""),
                "mobileUrl": item.get("url", ""),
                "description": item.get("description", ""),
                "source": item.get("source", source.get("name", "")),
            })
        return rows

    @staticmethod
    def is_url_exists(url: str, user_name: str | None = None) -> bool:
        """检查URL是否已存在于数据库中（增量采集检测）"""
        with get_connection() as conn:
            if user_name:
                result = conn.execute("select id from watch_records where url = ? and user_name = ?", (url, user_name)).fetchone()
            else:
                result = conn.execute("select id from watch_records where url = ?", (url,)).fetchone()
            return result is not None

    @staticmethod
    def collect(source_id: int, keyword: str, start_page: int, item_count: int, incremental=True, user_name: str | None = None, delay_seconds: float = 1.0, area_name: str = "", word: str = ""):
        """
        采集数据
        :param incremental: 是否启用增量采集（跳过已存在的URL）
        """
        source = WatchtowerRepository.get_source(source_id, user_name=user_name)
        if not source:
            return {"records": [], "skipped": 0}
        
        rows = []
        skipped = 0
        source_code = source.get("source_code")
        if source_code == "area_news":
            api_key = os.getenv("TIANAPI_AREA_NEWS_KEY", "")
            url = "https://apis.tianapi.com/areanews/index"
            page_no = max(1, start_page or 1)
            area_clean = (area_name or keyword).replace("省", "").replace("市", "")
            word_clean = (word or "").strip()
            queries = [{"areaname": area_clean, "word": word_clean}]
            if not word_clean:
                queries.append({"areaname": area_clean, "word": ""})
            items = []
            seen_ids = set()
            for q in queries:
                post_data = {"key": api_key, "areaname": q["areaname"], "word": q["word"], "page": page_no}
                api_json = WatchtowerRepository._fetch_html(
                    url,
                    source["headers_json"],
                    method="POST",
                    data=post_data,
                )
                try:
                    dbg = json.loads(api_json)
                    print(f"[area_news] request={post_data} response_code={dbg.get('code')} msg={dbg.get('msg')}")
                except Exception:
                    print(f"[area_news] request={post_data} response={api_json[:300]}")
                batch = WatchtowerRepository._parse_items(api_json, source)
                for item in batch:
                    item_id = item.get("id") or item.get("url") or item.get("title")
                    if item_id in seen_ids:
                        continue
                    seen_ids.add(item_id)
                    items.append(item)
                if len(items) >= item_count or batch:
                    break
        elif source_code == "huabian_news":
            api_key = os.getenv("JUHE_HUABIAN_KEY", "")
            url = "https://apis.juhe.cn/fapigx/huabian/query"
            page_no = max(1, start_page or 1)
            post_data = {
                "key": api_key,
                "num": item_count,
                "page": page_no,
                "rand": random.randint(1, 9999),
                "word": keyword,
            }
            api_json = WatchtowerRepository._fetch_html(
                url,
                source["headers_json"],
                method="POST",
                data=post_data,
            )
            try:
                dbg = json.loads(api_json)
                print(f"[huabian_news] request={post_data} response_code={dbg.get('reason')} msg={dbg.get('resultcode')}")
            except Exception:
                print(f"[huabian_news] request={post_data} response={api_json[:300]}")
            items = WatchtowerRepository._parse_items(api_json, source)
            if len(items) < item_count:
                post_data["page"] = page_no + 1
                api_json2 = WatchtowerRepository._fetch_html(
                    url,
                    source["headers_json"],
                    method="POST",
                    data=post_data,
                )
                items2 = WatchtowerRepository._parse_items(api_json2, source)
                seen_ids = {item.get("id") or item.get("url") or item.get("title") for item in items}
                for item in items2:
                    item_id = item.get("id") or item.get("url") or item.get("title")
                    if item_id not in seen_ids:
                        items.append(item)
        else:
            url = WatchtowerRepository._build_url(source, keyword, start_page)
            html = WatchtowerRepository._fetch_html(url, source["headers_json"])
            items = WatchtowerRepository._parse_items(html, source)
        
        for idx, item in enumerate(items[: max(1, item_count)], start=1):
            item_url = item.get("url") or item.get("mobileUrl") or ""
            if incremental and item_url and WatchtowerRepository.is_url_exists(item_url, user_name=user_name):
                skipped += 1
                continue
            rows.append(
                {
                    "user_name": user_name or source.get("user_name", "") or "",
                    "source_id": source_id,
                    "source_name": source["name"],
                    "keyword": word or keyword,
                    "title": item.get("title", ""),
                    "content": item.get("description", ""),
                    "url": item_url,
                    "source_url": item.get("url", ""),
                    "publish_time": item.get("time", ""),
                    "region": area_name or keyword,
                    "school": "",
                    "category": "",
                    "view_count": item.get("hot", ""),
                }
            )
            if delay_seconds and delay_seconds > 0:
                time.sleep(delay_seconds)
        
        return {"records": rows, "skipped": skipped}

    @staticmethod
    def save_records(records: list[dict]):
        if not records:
            return 0
        with get_connection() as conn:
            count = 0
            for record in records:
                record_url = record.get("url", "") or record.get("source_url", "")
                exists = conn.execute(
                    "select id from watch_records where url = ? and user_name = ?",
                    (record_url, record.get("user_name", "")),
                ).fetchone()
                if not exists:
                    conn.execute(
                        """
                        insert into watch_records(user_name, source_id, source_name, keyword, title, content, url, source_url, publish_time, region, school, category, view_count)
                        values(?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            record.get("user_name", ""),
                            record.get("source_id", 0),
                            record.get("source_name", ""),
                            record.get("keyword", ""),
                            record.get("title", ""),
                            record.get("content", ""),
                            record_url,
                            record.get("source_url", record_url),
                            record.get("publish_time", ""),
                            record.get("region", ""),
                            record.get("school", ""),
                            record.get("category", ""),
                            str(record.get("view_count", "")),
                        ),
                    )
                    count += 1
            return count

    @staticmethod
    def list_records(page: int = 1, page_size: int = 20, user_name: str | None = None):
        offset = (page - 1) * page_size
        with get_connection() as conn:
            if user_name:
                total = conn.execute("select count(1) as c from watch_records where user_name = ?", (user_name,)).fetchone()["c"]
                rows = conn.execute(
                    "select * from watch_records where user_name = ? order by id desc limit ? offset ?",
                    (user_name, page_size, offset),
                ).fetchall()
            else:
                total = conn.execute("select count(1) as c from watch_records").fetchone()["c"]
                rows = conn.execute(
                    "select * from watch_records order by id desc limit ? offset ?",
                    (page_size, offset),
                ).fetchall()
        return int(total), rows

    @staticmethod
    def list_records_filtered(page: int = 1, page_size: int = 20, keyword: str = None, source_name: str = None, user_name: str | None = None):
        """支持关键词和来源筛选的查询"""
        offset = (page - 1) * page_size
        conditions = []
        params = []
        if keyword:
            conditions.append("(keyword LIKE ? OR title LIKE ?)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        if source_name:
            conditions.append("source_name = ?")
            params.append(source_name)
        if user_name:
            conditions.append("user_name = ?")
            params.append(user_name)

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        count_sql = f"select count(1) as c from watch_records{where_clause}"
        data_sql = f"select * from watch_records{where_clause} order by id desc limit ? offset ?"
        params.extend([page_size, offset])

        with get_connection() as conn:
            total = conn.execute(count_sql, params[:-2] if conditions else []).fetchone()["c"]
            rows = conn.execute(data_sql, params).fetchall()
        return int(total), rows

    @staticmethod
    def get_record(record_id: int, user_name: str | None = None):
        """获取单条采集记录"""
        with get_connection() as conn:
            if user_name:
                return conn.execute("select * from watch_records where id = ? and user_name = ?", (record_id, user_name)).fetchone()
            return conn.execute("select * from watch_records where id = ?", (record_id,)).fetchone()

    @staticmethod
    def delete_record(record_id: int, user_name: str | None = None):
        with get_connection() as conn:
            if user_name:
                conn.execute("delete from watch_records where id = ? and user_name = ?", (record_id, user_name))
            else:
                conn.execute("delete from watch_records where id = ?", (record_id,))

    @staticmethod
    def batch_delete_records(ids: list[int], user_name: str | None = None):
        if not ids:
            return
        placeholders = ",".join(["?"] * len(ids))
        with get_connection() as conn:
            if user_name:
                conn.execute(f"delete from watch_records where user_name = ? and id in ({placeholders})", [user_name, *ids])
            else:
                conn.execute(f"delete from watch_records where id in ({placeholders})", ids)

    @staticmethod
    def init_default_sources(user_name: str | None = None):
        """初始化默认采集源"""
        sources = [
            {
                "user_name": user_name or "",
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
                "user_name": user_name or "",
                "name": "地区新闻",
                "source_code": "area_news",
                "entry_urls": [
                    "https://apis.tianapi.com/areanews/index?key={key}&areaname={地区名}&page={分页步进}&word={关键词}"
                ],
                "headers": {
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                "keywords_label": "关键词",
                "page_param_name": "page",
                "page_step": 1,
                "collect_limit": 10,
                "is_enabled": 1,
                "note": "天行数据地区新闻接口",
                "parse_rules": {
                    "json_path": "result.list"
                },
                "base_url": "https://apis.tianapi.com"
            },
            {
                "user_name": user_name or "",
                "name": "娱乐新闻",
                "source_code": "huabian_news",
                "entry_urls": [
                    "https://apis.juhe.cn/fapigx/huabian/query?key={key}&num={num}&page={分页步进}&rand={rand}&word={关键词}"
                ],
                "headers": {
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                "keywords_label": "关键词",
                "page_param_name": "page",
                "page_step": 1,
                "collect_limit": 10,
                "is_enabled": 1,
                "note": "聚合平台娱乐新闻接口",
                "parse_rules": {
                    "json_path": "result.newslist"
                },
                "base_url": "https://apis.juhe.cn"
            },
            {
                "user_name": user_name or "",
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
