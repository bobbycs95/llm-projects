-- Gold layer materialized views for LLM Stats

-- 1. Main comparison view: model x benchmark scores (flat, denormalized)
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

-- 2. Model summary for filters / dropdowns
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
    )::numeric, 4) AS avg_score_pct
FROM scores s
LEFT JOIN models m ON m.id = s.model_id
GROUP BY s.model_id, s.model_name, s.organization, m.open_weight, m.release_date, m.model_type;

CREATE UNIQUE INDEX IF NOT EXISTS idx_gold_ms_pk
    ON gold_model_summary (model_id);

-- 3. Category leaderboard
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
