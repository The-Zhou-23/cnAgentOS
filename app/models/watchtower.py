import json
import re
import sqlite3
from html import unescape
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.models.db import get_connection


class WatchtowerRepository:
    @staticmethod
    def list_sources():
        with get_connection() as conn:
            return conn.execute("select * from watch_sources order by is_enabled desc, id desc").fetchall()

    @staticmethod
    def get_source(source_id: int):
        with get_connection() as conn:
            return conn.execute("select * from watch_sources where id = ?", (source_id,)).fetchone()

    @staticmethod
    def create_source(data: dict) -> bool:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    insert into watch_sources(name, source_code, entry_urls_json, headers_json, keywords_label,
                                              page_param_name, page_step, collect_limit, is_enabled, note)
                    values(?,?,?,?,?,?,?,?,?,?)
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
                    page_param_name=?, page_step=?, collect_limit=?, is_enabled=?, note=?, updated_at=datetime('now')
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
                    source_id,
                ),
            )
        return True

    @staticmethod
    def delete_source(source_id: int) -> None:
        with get_connection() as conn:
            conn.execute("delete from watch_sources where id = ?", (source_id,))

    @staticmethod
    def _build_baidu_news_url(keyword: str, start_page: int):
        query = quote(keyword, safe="")
        if start_page <= 0:
            return f"https://www.baidu.com/s?ie=utf-8&bsst=1&rsv_dl=news_t_sk&tn=news&cl=2&medium=0&rtt=1&wd={query}"
        return f"https://www.baidu.com/s?ie=utf-8&bsst=1&rsv_dl=news_b_pn&tn=news&cl=2&medium=0&rtt=1&wd={query}&pn={start_page}"

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
    def _parse_titles(html: str):
        titles = []
        patterns = [
            r"<h3[^>]*class=\"[^\"]*news-title[^\"]*\"[^>]*>.*?<a[^>]*>(.*?)</a>",
            r"<h3[^>]*>.*?<a[^>]*>(.*?)</a>",
            r"<a[^>]*class=\"[^\"]*news-title[^\"]*\"[^>]*>(.*?)</a>",
        ]
        for pat in patterns:
            matches = re.findall(pat, html, flags=re.S | re.I)
            for m in matches:
                text = re.sub(r"<[^>]+>", "", m)
                text = unescape(re.sub(r"\s+", " ", text)).strip()
                if text and text not in titles:
                    titles.append(text)
        if not titles:
            generic = re.findall(r"<a[^>]*>(.*?)</a>", html, flags=re.S | re.I)
            for m in generic:
                text = re.sub(r"<[^>]+>", "", m)
                text = unescape(re.sub(r"\s+", " ", text)).strip()
                if len(text) >= 6 and text not in titles:
                    titles.append(text)
        return titles

    @staticmethod
    def collect(source_id: int, keyword: str, start_page: int, item_count: int):
        source = WatchtowerRepository.get_source(source_id)
        if not source:
            return []
        url = WatchtowerRepository._build_baidu_news_url(keyword, start_page)
        html = WatchtowerRepository._fetch_html(url, source["headers_json"])
        titles = WatchtowerRepository._parse_titles(html)
        rows = []
        for idx, title in enumerate(titles[: max(1, item_count)], start=1):
            rows.append(
                {
                    "source_id": source_id,
                    "source_name": source["name"],
                    "keyword": keyword,
                    "title": title,
                    "content": "",
                    "url": url,
                }
            )
        return rows

    @staticmethod
    def save_records(records: list[dict]):
        if not records:
            return
        with get_connection() as conn:
            for record in records:
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
