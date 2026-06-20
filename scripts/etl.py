"""
ETL script for LLM Stats API -> Postgres
Fetches from 6 endpoints and upserts into corresponding tables.
"""

import os
import json
import time
import requests
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timezone

API_BASE = "https://api.zeroeval.com/stats/v1"
API_KEY = os.environ.get("LLM_STATS_API_KEY")
DB_CONFIG = {
    "host": os.environ.get("LLM_STATS_DB_HOST", "localhost"),
    "port": int(os.environ.get("LLM_STATS_DB_PORT", "5432")),
    "dbname": os.environ.get("LLM_STATS_DB_NAME", "llm"),
    "user": os.environ.get("LLM_STATS_DB_USER", "admin"),
    "password": os.environ.get("LLM_STATS_DB_PASS", "admin"),
}

RANKING_CATEGORIES = [
    "coding", "reasoning", "math", "general", "language",
    "agents", "vision", "long_context", "biology", "chemistry",
    "physics", "healthcare", "finance", "legal", "communication",
    "frontend_development", "tool_calling", "code",
]

HEADERS = {"Authorization": f"Bearer {API_KEY}"}


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def api_get(endpoint, params=None):
    url = f"{API_BASE}/{endpoint}"
    resp = requests.get(url, headers=HEADERS, params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def fetch_all_paginated(endpoint, key, params=None):
    all_items = []
    cursor = None
    base_params = params or {}
    while True:
        p = {**base_params, "limit": 100}
        if cursor:
            p["cursor"] = cursor
        data = api_get(endpoint, p)
        items = data.get(key, [])
        all_items.extend(items)
        cursor = data.get("next_cursor")
        if not cursor or not items:
            break
        time.sleep(0.2)
    return all_items


def upsert_models(conn):
    print("[ETL] Fetching models...")
    models = fetch_all_paginated("models", "models")
    print(f"[ETL] Got {len(models)} models")
    now = datetime.now(timezone.utc)
    rows = []
    for m in models:
        org = m.get("organization") or {}
        lic = m.get("license") or {}
        rows.append((
            m.get("id"), m.get("name"), m.get("description"),
            org.get("id"), org.get("name"),
            m.get("family"),
            lic.get("id"), lic.get("name"), lic.get("allow_commercial"),
            m.get("open_weight"), m.get("model_type"),
            json.dumps(m.get("modalities")),
            m.get("context_window"), m.get("param_count"), m.get("training_tokens"),
            m.get("knowledge_cutoff"), m.get("release_date"),
            json.dumps(m.get("providers")),
            json.dumps(m.get("top_scores")),
            json.dumps(m.get("inference")),
            m.get("source"), m.get("url"),
            now, now,
        ))
    with conn.cursor() as cur:
        execute_values(cur, """
            INSERT INTO models (
                id, name, description, organization_id, organization_name,
                family, license_id, license_name, license_allow_commercial,
                open_weight, model_type, modalities, context_window,
                param_count, training_tokens, knowledge_cutoff, release_date,
                providers, top_scores, inference, source, url,
                "createdAt", "updatedAt"
            ) VALUES %s
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                organization_id = EXCLUDED.organization_id,
                organization_name = EXCLUDED.organization_name,
                family = EXCLUDED.family,
                license_id = EXCLUDED.license_id,
                license_name = EXCLUDED.license_name,
                license_allow_commercial = EXCLUDED.license_allow_commercial,
                open_weight = EXCLUDED.open_weight,
                model_type = EXCLUDED.model_type,
                modalities = EXCLUDED.modalities,
                context_window = EXCLUDED.context_window,
                param_count = EXCLUDED.param_count,
                training_tokens = EXCLUDED.training_tokens,
                knowledge_cutoff = EXCLUDED.knowledge_cutoff,
                release_date = EXCLUDED.release_date,
                providers = EXCLUDED.providers,
                top_scores = EXCLUDED.top_scores,
                inference = EXCLUDED.inference,
                source = EXCLUDED.source,
                url = EXCLUDED.url,
                "updatedAt" = EXCLUDED."updatedAt"
        """, rows)
    conn.commit()
    print(f"[ETL] Upserted {len(rows)} models")


def upsert_benchmarks(conn):
    print("[ETL] Fetching benchmarks...")
    benchmarks = api_get("benchmarks").get("benchmarks", [])
    print(f"[ETL] Got {len(benchmarks)} benchmarks")
    now = datetime.now(timezone.utc)
    rows = []
    for b in benchmarks:
        rows.append((
            b.get("id"), b.get("name"), b.get("description"),
            json.dumps(b.get("categories")),
            b.get("modality"), b.get("max_score"), b.get("language"),
            b.get("verified"), b.get("model_count"),
            b.get("paper_link"), b.get("implementation_link"),
            b.get("source"), b.get("url"),
            now, now,
        ))
    with conn.cursor() as cur:
        execute_values(cur, """
            INSERT INTO benchmarks (
                id, name, description, categories, modality, max_score,
                language, verified, model_count, paper_link,
                implementation_link, source, url,
                "createdAt", "updatedAt"
            ) VALUES %s
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                categories = EXCLUDED.categories,
                modality = EXCLUDED.modality,
                max_score = EXCLUDED.max_score,
                language = EXCLUDED.language,
                verified = EXCLUDED.verified,
                model_count = EXCLUDED.model_count,
                paper_link = EXCLUDED.paper_link,
                implementation_link = EXCLUDED.implementation_link,
                source = EXCLUDED.source,
                url = EXCLUDED.url,
                "updatedAt" = EXCLUDED."updatedAt"
        """, rows)
    conn.commit()
    print(f"[ETL] Upserted {len(rows)} benchmarks")


def upsert_scores(conn):
    print("[ETL] Fetching scores...")
    scores = fetch_all_paginated("scores", "scores")
    now = datetime.now(timezone.utc)
    seen = {}
    for s in scores:
        key = (s.get("model_id"), s.get("benchmark_id"), s.get("category"))
        seen[key] = s
    deduped = list(seen.values())
    print(f"[ETL] Got {len(scores)} scores ({len(deduped)} unique)")
    rows = []
    for s in deduped:
        rows.append((
            s.get("model_id"), s.get("benchmark_id"), s.get("category"),
            s.get("model_name"), s.get("organization"), s.get("benchmark_name"),
            s.get("score"), s.get("normalized_score"), s.get("max_score"),
            s.get("is_self_reported"), s.get("verified"),
            s.get("scored_at"),
            s.get("source"), s.get("url"),
            now, now,
        ))
    with conn.cursor() as cur:
        execute_values(cur, """
            INSERT INTO scores (
                model_id, benchmark_id, category, model_name, organization,
                benchmark_name, score, normalized_score, max_score,
                is_self_reported, verified, scored_at, source, url,
                "createdAt", "updatedAt"
            ) VALUES %s
            ON CONFLICT (model_id, benchmark_id, category) DO UPDATE SET
                model_name = EXCLUDED.model_name,
                organization = EXCLUDED.organization,
                benchmark_name = EXCLUDED.benchmark_name,
                score = EXCLUDED.score,
                normalized_score = EXCLUDED.normalized_score,
                max_score = EXCLUDED.max_score,
                is_self_reported = EXCLUDED.is_self_reported,
                verified = EXCLUDED.verified,
                scored_at = EXCLUDED.scored_at,
                source = EXCLUDED.source,
                url = EXCLUDED.url,
                "updatedAt" = EXCLUDED."updatedAt"
        """, rows)
    conn.commit()
    print(f"[ETL] Upserted {len(rows)} scores")


def upsert_rankings(conn):
    print("[ETL] Fetching rankings...")
    now = datetime.now(timezone.utc)
    all_rows = []
    for cat in RANKING_CATEGORIES:
        try:
            data = api_get("rankings", {"category": cat})
            method = data.get("method")
            ranked_at = data.get("ranked_at")
            models = data.get("models", [])
            for m in models:
                all_rows.append((
                    cat, m.get("model_id"), m.get("rank"),
                    m.get("model_name"), m.get("organization"),
                    m.get("score"), m.get("conservative_rating"),
                    m.get("open_weight"), m.get("min_input_price"),
                    m.get("benchmarks_evaluated"),
                    method, ranked_at,
                    m.get("source"), m.get("url"),
                    now, now,
                ))
            time.sleep(0.2)
        except Exception as e:
            print(f"[ETL] Warning: rankings for '{cat}' failed: {e}")
    print(f"[ETL] Got {len(all_rows)} ranking entries across categories")
    with conn.cursor() as cur:
        execute_values(cur, """
            INSERT INTO rankings (
                category, model_id, rank, model_name, organization,
                score, conservative_rating, open_weight, min_input_price,
                benchmarks_evaluated, method, ranked_at, source, url,
                "createdAt", "updatedAt"
            ) VALUES %s
            ON CONFLICT (category, model_id) DO UPDATE SET
                rank = EXCLUDED.rank,
                model_name = EXCLUDED.model_name,
                organization = EXCLUDED.organization,
                score = EXCLUDED.score,
                conservative_rating = EXCLUDED.conservative_rating,
                open_weight = EXCLUDED.open_weight,
                min_input_price = EXCLUDED.min_input_price,
                benchmarks_evaluated = EXCLUDED.benchmarks_evaluated,
                method = EXCLUDED.method,
                ranked_at = EXCLUDED.ranked_at,
                source = EXCLUDED.source,
                url = EXCLUDED.url,
                "updatedAt" = EXCLUDED."updatedAt"
        """, all_rows)
    conn.commit()
    print(f"[ETL] Upserted {len(all_rows)} rankings")


def upsert_updates(conn):
    print("[ETL] Fetching updates...")
    now = datetime.now(timezone.utc)
    all_rows = []
    for days in [1, 7, 30]:
        data = api_get("updates", {"days": days})
        models = data.get("models", [])
        for m in models:
            org = m.get("organization") or {}
            all_rows.append((
                m.get("id"), days,
                m.get("name"),
                org.get("id") if isinstance(org, dict) else org,
                org.get("name") if isinstance(org, dict) else None,
                m.get("model_type"),
                json.dumps(m.get("modalities")),
                m.get("context_window"), m.get("release_date"),
                m.get("open_weight"), m.get("added_at"),
                m.get("source"), m.get("url"),
                now, now,
            ))
        time.sleep(0.2)
    print(f"[ETL] Got {len(all_rows)} update entries")
    with conn.cursor() as cur:
        execute_values(cur, """
            INSERT INTO updates (
                id, days, name, organization_id, organization_name,
                model_type, modalities, context_window, release_date,
                open_weight, added_at, source, url,
                "createdAt", "updatedAt"
            ) VALUES %s
            ON CONFLICT (id, days) DO UPDATE SET
                name = EXCLUDED.name,
                organization_id = EXCLUDED.organization_id,
                organization_name = EXCLUDED.organization_name,
                model_type = EXCLUDED.model_type,
                modalities = EXCLUDED.modalities,
                context_window = EXCLUDED.context_window,
                release_date = EXCLUDED.release_date,
                open_weight = EXCLUDED.open_weight,
                added_at = EXCLUDED.added_at,
                source = EXCLUDED.source,
                url = EXCLUDED.url,
                "updatedAt" = EXCLUDED."updatedAt"
        """, all_rows)
    conn.commit()
    print(f"[ETL] Upserted {len(all_rows)} updates")


def upsert_model_details(conn):
    print("[ETL] Fetching model details...")
    models = fetch_all_paginated("models", "models")
    now = datetime.now(timezone.utc)
    rows = []
    count = 0
    for m in models:
        model_id = m.get("id")
        try:
            detail = api_get(f"models/{model_id}")
            org = detail.get("organization") or {}
            lic = detail.get("license") or {}
            rows.append((
                detail.get("id"), detail.get("name"), detail.get("description"),
                org.get("id"), org.get("name"),
                detail.get("family"),
                lic.get("id"), lic.get("name"), lic.get("allow_commercial"),
                detail.get("open_weight"), detail.get("model_type"),
                json.dumps(detail.get("modalities")),
                detail.get("context_window"), detail.get("param_count"),
                detail.get("training_tokens"), detail.get("knowledge_cutoff"),
                detail.get("release_date"),
                json.dumps(detail.get("providers")),
                json.dumps(detail.get("scores") or detail.get("all_scores")),
                json.dumps(detail.get("inference")),
                detail.get("source"), detail.get("url"),
                now, now,
            ))
            count += 1
            if count % 20 == 0:
                print(f"[ETL] Fetched {count}/{len(models)} model details...")
            time.sleep(0.15)
        except Exception as e:
            print(f"[ETL] Warning: model detail '{model_id}' failed: {e}")
    print(f"[ETL] Got {len(rows)} model details")
    with conn.cursor() as cur:
        execute_values(cur, """
            INSERT INTO model_details (
                id, name, description, organization_id, organization_name,
                family, license_id, license_name, license_allow_commercial,
                open_weight, model_type, modalities, context_window,
                param_count, training_tokens, knowledge_cutoff, release_date,
                providers, all_scores, inference, source, url,
                "createdAt", "updatedAt"
            ) VALUES %s
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                organization_id = EXCLUDED.organization_id,
                organization_name = EXCLUDED.organization_name,
                family = EXCLUDED.family,
                license_id = EXCLUDED.license_id,
                license_name = EXCLUDED.license_name,
                license_allow_commercial = EXCLUDED.license_allow_commercial,
                open_weight = EXCLUDED.open_weight,
                model_type = EXCLUDED.model_type,
                modalities = EXCLUDED.modalities,
                context_window = EXCLUDED.context_window,
                param_count = EXCLUDED.param_count,
                training_tokens = EXCLUDED.training_tokens,
                knowledge_cutoff = EXCLUDED.knowledge_cutoff,
                release_date = EXCLUDED.release_date,
                providers = EXCLUDED.providers,
                all_scores = EXCLUDED.all_scores,
                inference = EXCLUDED.inference,
                source = EXCLUDED.source,
                url = EXCLUDED.url,
                "updatedAt" = EXCLUDED."updatedAt"
        """, rows)
    conn.commit()
    print(f"[ETL] Upserted {len(rows)} model details")


def run_etl():
    print(f"[ETL] Starting at {datetime.now(timezone.utc).isoformat()}")
    conn = get_conn()
    try:
        upsert_models(conn)
        upsert_benchmarks(conn)
        upsert_scores(conn)
        upsert_rankings(conn)
        upsert_updates(conn)
        upsert_model_details(conn)
    finally:
        conn.close()
    print(f"[ETL] Completed at {datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    run_etl()
