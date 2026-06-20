-- Gold layer materialized views for LLM Stats
-- These views denormalize and aggregate Bronze tables into analysis-ready datasets.
-- Refresh strategy: REFRESH MATERIALIZED VIEW CONCURRENTLY after each ETL run.

-- 1. Denormalized score matrix (model x benchmark with computed score_pct)
CREATE MATERIALIZED VIEW IF NOT EXISTS gold_model_benchmark_scores AS
SELECT
    s.model_id,
    s.model_name,
    s.organization,
    m.open_weight,
    m.release_date,
    m.model_type,
    s.benchmark_id,
    s.benchmark_name,
    s.category,
    s.score,
    s.normalized_score,
    s.max_score,
    CASE
        WHEN s.max_score IS NOT NULL AND s.max_score > 0 AND s.score <= s.max_score
        THEN ROUND((s.score / s.max_score)::numeric, 4)
        WHEN s.normalized_score IS NOT NULL
        THEN ROUND(s.normalized_score::numeric, 4)
        ELSE NULL
    END AS score_pct,
    s.is_self_reported,
    s.verified,
    s.scored_at
FROM scores s
LEFT JOIN models m ON m.id = s.model_id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_gold_mbs_pk
    ON gold_model_benchmark_scores (model_id, benchmark_id, category);
CREATE INDEX IF NOT EXISTS idx_gold_mbs_model
    ON gold_model_benchmark_scores (model_id);
CREATE INDEX IF NOT EXISTS idx_gold_mbs_category
    ON gold_model_benchmark_scores (category);

-- 2. Per-model summary with overall rank
CREATE MATERIALIZED VIEW IF NOT EXISTS gold_model_summary AS
SELECT
    s.model_id,
    s.model_name,
    s.organization,
    m.open_weight,
    m.release_date,
    m.model_type,
    COUNT(DISTINCT s.benchmark_id) AS num_benchmarks,
    COUNT(DISTINCT s.category) AS num_categories,
    ROUND(AVG(
        CASE
            WHEN s.max_score IS NOT NULL AND s.max_score > 0 AND s.score <= s.max_score
            THEN (s.score / s.max_score)
            WHEN s.normalized_score IS NOT NULL
            THEN s.normalized_score
            ELSE NULL
        END
    )::numeric, 4) AS avg_score_pct,
    RANK() OVER (ORDER BY AVG(
        CASE
            WHEN s.max_score IS NOT NULL AND s.max_score > 0 AND s.score <= s.max_score
            THEN (s.score / s.max_score)
            WHEN s.normalized_score IS NOT NULL
            THEN s.normalized_score
            ELSE NULL
        END
    ) DESC NULLS LAST) AS overall_rank
FROM scores s
LEFT JOIN models m ON m.id = s.model_id
GROUP BY s.model_id, s.model_name, s.organization, m.open_weight, m.release_date, m.model_type;

CREATE UNIQUE INDEX IF NOT EXISTS idx_gold_ms_pk
    ON gold_model_summary (model_id);

-- 3. Category leaderboard (TrueSkill rankings enriched with model metadata)
CREATE MATERIALIZED VIEW IF NOT EXISTS gold_category_leaderboard AS
SELECT
    r.category,
    r.rank,
    r.model_id,
    r.model_name,
    r.organization,
    r.score,
    r.conservative_rating,
    r.open_weight,
    r.min_input_price,
    r.benchmarks_evaluated,
    r.method,
    r.ranked_at,
    m.release_date,
    m.model_type
FROM rankings r
LEFT JOIN models m ON m.id = r.model_id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_gold_cl_pk
    ON gold_category_leaderboard (category, model_id);
CREATE INDEX IF NOT EXISTS idx_gold_cl_category
    ON gold_category_leaderboard (category);

-- 4. Category-level KPIs (model count, avg/max/min scores per category)
CREATE MATERIALIZED VIEW IF NOT EXISTS gold_category_stats AS
SELECT
    category,
    COUNT(DISTINCT model_id) AS num_models,
    COUNT(DISTINCT benchmark_id) AS num_benchmarks,
    ROUND(AVG(score_pct)::numeric, 4) AS avg_score_pct,
    ROUND(MAX(score_pct)::numeric, 4) AS max_score_pct,
    ROUND(MIN(score_pct)::numeric, 4) AS min_score_pct
FROM gold_model_benchmark_scores
WHERE score_pct IS NOT NULL
GROUP BY category;

CREATE UNIQUE INDEX IF NOT EXISTS idx_gold_cs_pk
    ON gold_category_stats (category);

-- 5. Organization-level performance aggregation
CREATE MATERIALIZED VIEW IF NOT EXISTS gold_org_summary AS
SELECT
    organization,
    COUNT(DISTINCT model_id) AS num_models,
    COUNT(DISTINCT category) AS num_categories,
    ROUND(AVG(score_pct)::numeric, 4) AS avg_score_pct,
    ROUND(MAX(score_pct)::numeric, 4) AS max_score_pct,
    ARRAY_AGG(DISTINCT model_name) AS model_names
FROM gold_model_benchmark_scores
WHERE score_pct IS NOT NULL AND organization IS NOT NULL
GROUP BY organization;

CREATE UNIQUE INDEX IF NOT EXISTS idx_gold_os_pk
    ON gold_org_summary (organization);

-- 6. Cost efficiency metrics (score per dollar, throughput)
CREATE MATERIALIZED VIEW IF NOT EXISTS gold_model_pricing AS
SELECT
    m.id AS model_id,
    m.name AS model_name,
    m.organization_name AS organization,
    m.open_weight,
    (m.inference->>'input_price')::float AS input_price,
    (m.inference->>'output_price')::float AS output_price,
    (m.inference->>'tokens_per_second')::float AS tokens_per_second,
    ms.avg_score_pct,
    ms.overall_rank,
    ms.num_benchmarks,
    CASE
        WHEN (m.inference->>'input_price')::float > 0
        THEN ROUND((ms.avg_score_pct / (m.inference->>'input_price')::float)::numeric, 4)
        ELSE NULL
    END AS score_per_dollar
FROM models m
JOIN gold_model_summary ms ON ms.model_id = m.id
WHERE m.inference IS NOT NULL
  AND (m.inference->>'input_price') IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_gold_mp_pk
    ON gold_model_pricing (model_id);
