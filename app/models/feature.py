import sqlite3

from app.models.db import get_connection


class FeatureRepository:
    @staticmethod
    def list_features():
        with get_connection() as conn:
            return conn.execute("select * from features order by sort_no asc, id asc").fetchall()

    @staticmethod
    def get_feature(feature_id: int):
        with get_connection() as conn:
            return conn.execute("select * from features where id = ?", (feature_id,)).fetchone()

    @staticmethod
    def update_feature(feature_id: int, data: dict) -> bool:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    update features set
                        name=?, route_path=?, sort_no=?, is_enabled=?, updated_at=datetime('now')
                    where id=?
                    """,
                    (
                        data.get("name"),
                        data.get("route_path"),
                        int(data.get("sort_no", 0)),
                        int(data.get("is_enabled", 1)),
                        feature_id,
                    ),
                )
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def get_enabled_features_for_role(role_code: str | None):
        with get_connection() as conn:
            return conn.execute(
                "select * from features where is_enabled = 1 order by sort_no asc, id asc"
            ).fetchall()
