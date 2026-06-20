# LLM Stats Pipeline & Dashboard

End-to-end data pipeline that ingests LLM benchmark data from [llm-stats.com](https://llm-stats.com) API, stores it in PostgreSQL, orchestrates daily ingestion with Apache Airflow, and visualizes insights through an interactive Plotly/Dash dashboard.

**Live:** [llm.xoneprojects.com](http://llm.xoneprojects.com)

## Architecture

```
LLM Stats API (6 endpoints)
        │
        ▼
  ETL Script (Python)
        │
        ▼
  PostgreSQL (raw + gold views)
        │
        ├──▶ Airflow (daily @ 01:00 WIB)
        │
        ▼
  Dash Dashboard (6 pages)
        │
        ▼
  Nginx Proxy Manager → llm.xoneprojects.com
```

## Data Sources

| Endpoint | Description | Table |
|----------|-------------|-------|
| `/stats/v1/models` | Model catalog with metadata & pricing | `models` |
| `/stats/v1/models/{id}` | Full model detail with all benchmark scores | `model_details` |
| `/stats/v1/benchmarks` | All benchmarks with categories | `benchmarks` |
| `/stats/v1/scores` | Score matrix across models and benchmarks | `scores` |
| `/stats/v1/rankings` | TrueSkill rankings by category | `rankings` |
| `/stats/v1/updates` | Recently added models | `updates` |

## Gold Layer (Materialized Views)

| View | Purpose |
|------|---------|
| `gold_model_benchmark_scores` | Denormalized scores with model metadata and score_pct |
| `gold_model_summary` | Aggregated per-model stats with overall rank |
| `gold_category_leaderboard` | Rankings per category with model metadata |
| `gold_category_stats` | Category-level aggregations |
| `gold_org_summary` | Organization-level performance |
| `gold_model_pricing` | Cost efficiency metrics (score per dollar) |

## Dashboard Pages

| Page | URL Path | Description |
|------|----------|-------------|
| Leaderboard | `/` | Overall rankings, heatmap, org performance |
| Model Deep Dive | `/model` | Single model analysis — strengths, radar chart, benchmarks |
| Category | `/category` | TrueSkill leaderboard per category, open vs proprietary |
| Trends | `/trends` | Performance evolution, release velocity, ecosystem trends |
| Cost Efficiency | `/cost` | Price vs performance scatter, efficiency frontier |
| Compare | `/compare` | Side-by-side comparison of 3 models |

## Quick Start

### Prerequisites
- Docker & Docker Compose
- LLM Stats API key (free from https://llm-stats.com/settings?tab=api-keys)

### Setup

1. Clone the repo:
```bash
git clone https://github.com/bobbycs95/llm-projects.git
cd llm-projects
```

2. Set your API key in `docker-compose.yml`:
```yaml
LLM_STATS_API_KEY: your_api_key_here
```

3. Start all services:
```bash
docker compose up -d
```

4. Run initial ingestion:
```bash
docker compose exec airflow-scheduler python /opt/airflow/scripts/etl.py
```

5. Create gold views:
```bash
docker compose exec postgres psql -U admin -d llm -f /docker-entrypoint-initdb.d/gold_views.sql
```

### Services

| Service | Port | Credentials |
|---------|------|-------------|
| Dashboard | 8050 | — (no auth) |
| PostgreSQL | 5434 | admin / admin |
| Airflow | 8080 | admin / admin |

## ETL Process

- **Schedule:** Daily at 01:00 WIB (18:00 UTC) via Airflow
- **Strategy:** Upsert (merge incremental) — new models are inserted, existing ones updated
- **Tracking:** Each table has `createdAt` and `updatedAt` timestamps
- **Deduplication:** Scores are deduplicated by (model_id, benchmark_id, category)

## Tech Stack

- **Database:** PostgreSQL 16
- **Orchestration:** Apache Airflow 2.9
- **Dashboard:** Plotly Dash 2.17 (Python)
- **ETL:** Python (requests + psycopg2)
- **Infrastructure:** Docker Compose
- **Proxy:** Nginx Proxy Manager

## Project Structure

```
├── dags/
│   └── llm_stats_dag.py        # Airflow DAG (daily 01:00 WIB)
├── dashboard/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py             # Dash app entry point
│       ├── data.py             # Data layer with caching
│       ├── theme.py            # Color palette & chart styling
│       └── pages/
│           ├── leaderboard.py  # Page 1: LLM Leaderboard
│           ├── model_deep_dive.py  # Page 2: Model Deep Dive
│           ├── category.py     # Page 3: Category Leaderboard
│           ├── trends.py       # Page 4: Market Trends
│           ├── cost.py         # Page 5: Cost Efficiency
│           └── compare.py      # Page 6: Model Comparison
├── scripts/
│   ├── init.sql                # Database schema (6 tables)
│   ├── gold_views.sql          # Materialized views
│   └── etl.py                  # ETL script (6 API endpoints)
└── docker-compose.yml          # Full stack orchestration
```
