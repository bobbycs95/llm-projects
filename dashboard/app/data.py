import os
import pandas as pd
import psycopg2
from functools import lru_cache
import time

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "postgres"),
    "port": int(os.environ.get("DB_PORT", "5432")),
    "dbname": os.environ.get("DB_NAME", "llm"),
    "user": os.environ.get("DB_USER", "admin"),
    "password": os.environ.get("DB_PASS", "admin"),
}

_cache = {}
_cache_ts = {}
CACHE_TTL = 300  # 5 minutes


def query(sql, params=None):
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        df = pd.read_sql(sql, conn, params=params)
    finally:
        conn.close()
    return df


def _cached_query(key, sql, params=None):
    now = time.time()
    if key in _cache and (now - _cache_ts.get(key, 0)) < CACHE_TTL:
        return _cache[key]
    df = query(sql, params)
    _cache[key] = df
    _cache_ts[key] = now
    return df


def get_scores():
    return _cached_query("scores", "SELECT * FROM gold_model_benchmark_scores WHERE score_pct IS NOT NULL")


def get_model_summary():
    return _cached_query("model_summary", "SELECT * FROM gold_model_summary ORDER BY overall_rank")


def get_category_leaderboard(category=None):
    if category:
        return _cached_query(f"cat_lb_{category}", "SELECT * FROM gold_category_leaderboard WHERE category = %s ORDER BY rank", (category,))
    return _cached_query("cat_lb_all", "SELECT * FROM gold_category_leaderboard ORDER BY category, rank")


def get_category_stats():
    return _cached_query("cat_stats", "SELECT * FROM gold_category_stats ORDER BY num_models DESC")


def get_org_summary():
    return _cached_query("org_summary", "SELECT * FROM gold_org_summary ORDER BY avg_score_pct DESC")


def get_pricing():
    return _cached_query("pricing", "SELECT * FROM gold_model_pricing ORDER BY score_per_dollar DESC NULLS LAST")


def get_updates():
    return _cached_query("updates", "SELECT * FROM updates WHERE days = 30 ORDER BY added_at DESC")


def get_categories():
    return _cached_query("categories", "SELECT DISTINCT category FROM gold_model_benchmark_scores ORDER BY category")["category"].tolist()


def get_model_names():
    return _cached_query("model_names", "SELECT DISTINCT model_name FROM gold_model_summary ORDER BY model_name")["model_name"].tolist()
