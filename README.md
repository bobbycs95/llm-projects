# LLM Stats Pipeline & Dashboard

End-to-end data pipeline that ingests LLM benchmark data from [llm-stats.com](https://llm-stats.com) API, stores it in PostgreSQL, orchestrates daily ingestion with Apache Airflow, and visualizes insights through an interactive Plotly/Dash dashboard.

**Live Demo:** [llm.xoneprojects.com](http://llm.xoneprojects.com)

---

## Data Engineering Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           LLM Stats API (Source)                              │
│        6 REST endpoints @ https://api.zeroeval.com/stats/v1/                 │
└──────────────────┬───────────────────────────────────────────────────────────┘
                   │  Bearer Token Auth
                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                        INGESTION LAYER (ETL)                                  │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  scripts/etl.py                                                      │    │
│  │                                                                      │    │
│  │  • Fetches all 6 endpoints with pagination handling                  │    │
│  │  • Deduplicates records by composite primary keys                    │    │
│  │  • Upserts (INSERT ... ON CONFLICT DO UPDATE)                        │    │
│  │  • Tracks createdAt / updatedAt per row                              │    │
│  │  • Rate-limited (200ms between paginated calls)                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  Orchestrated by Apache Airflow                                              │
│  Schedule: Daily @ 01:00 WIB (18:00 UTC) — cron: 0 18 * * *                │
│  Retries: 2 (5 min delay)                                                   │
└──────────────────┬───────────────────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                        STORAGE LAYER (PostgreSQL 16)                          │
│                                                                              │
│  ┌─── Bronze (Raw Tables) ────────────────────────────────────────────┐     │
│  │                                                                     │     │
│  │  models          319 rows   Model catalog, metadata, pricing        │     │
│  │  model_details   319 rows   Full detail with all benchmark scores   │     │
│  │  benchmarks      568 rows   Benchmark definitions & categories      │     │
│  │  scores         4793 rows   Score matrix (model × benchmark × cat)  │     │
│  │  rankings        180 rows   TrueSkill rankings per category         │     │
│  │  updates          22 rows   Recently added models (1/7/30d)         │     │
│  │                                                                     │     │
│  │  All tables: createdAt + updatedAt timestamps                       │     │
│  │  Merge strategy: UPSERT on primary key                              │     │
│  └─────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ┌─── Gold (Materialized Views) ──────────────────────────────────────┐     │
│  │                                                                     │     │
│  │  gold_model_benchmark_scores                                        │     │
│  │    → Denormalized: scores + model metadata + computed score_pct     │     │
│  │    → score_pct = score/max_score normalized to 0-1 range            │     │
│  │                                                                     │     │
│  │  gold_model_summary                                                 │     │
│  │    → Per-model aggregation: avg score, rank, coverage stats         │     │
│  │                                                                     │     │
│  │  gold_category_leaderboard                                          │     │
│  │    → Rankings enriched with model metadata                          │     │
│  │                                                                     │     │
│  │  gold_category_stats                                                │     │
│  │    → Category-level KPIs (model count, avg/max/min scores)          │     │
│  │                                                                     │     │
│  │  gold_org_summary                                                   │     │
│  │    → Organization-level performance aggregation                     │     │
│  │                                                                     │     │
│  │  gold_model_pricing                                                 │     │
│  │    → Cost efficiency metrics (score_per_dollar, throughput)          │     │
│  └─────────────────────────────────────────────────────────────────────┘     │
└──────────────────┬───────────────────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                      PRESENTATION LAYER (Dash)                                │
│                                                                              │
│  Plotly/Dash app with 6 interactive pages                                    │
│  In-memory cache (5 min TTL) for fast page transitions                       │
│  Dark theme with indigo/purple/cyan color palette                            │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Extract** — ETL script calls 6 API endpoints with cursor-based pagination, collecting all available data
2. **Transform** — Deduplication by composite keys, normalization of nested JSON (organization, license, providers), score percentage calculation
3. **Load** — Upsert into PostgreSQL raw tables (Bronze layer)
4. **Transform (Gold)** — Materialized views join and aggregate raw data into analysis-ready datasets
5. **Serve** — Dash app queries gold views with in-memory caching for responsive UX

### Incremental Strategy

The pipeline uses **merge incremental (upsert)** pattern:
- Each table has a composite or natural primary key
- `INSERT ... ON CONFLICT (pk) DO UPDATE SET ... updatedAt = now()`
- New models/scores are inserted; existing ones get their values refreshed
- `createdAt` is set only on first insert; `updatedAt` reflects last ETL run
- This allows daily runs without duplicates or data loss

---

## Dashboard Pages

### Page 1: LLM Leaderboard (`/`)

The main overview page showing all models ranked by average benchmark score.

**Features:**
- Filterable by category, license type (open/proprietary), and organization
- Highlight cards showing best overall, best open-weight, most tested, and best proprietary models
- Sortable data table with model rankings (default: highest score first)
- Organization performance bar chart (avg score by org)
- Heatmap showing top 15 models across 8 key categories — quickly spot strengths and gaps

**Use case:** "Which models are leading right now? Who's the best in each category?"

---

### Page 2: Model Deep Dive (`/model`)

Detailed single-model analysis page with a model selector dropdown.

**Features:**
- Model info card with organization, license, rank, and overall score
- Horizontal bar chart showing score per category with global average reference line (dashed)
- Radar/polar chart comparing the model's profile against the global average shape
- Full benchmark detail table (sortable, filterable) with columns: Benchmark, Category, Score %, vs Avg, Raw Score, Max Score, Verified

**Use case:** "I'm considering Claude Opus 4.6 — where does it excel and where does it fall short?"

---

### Page 3: Category Leaderboard (`/category`)

Per-category deep dive with TrueSkill rankings.

**Features:**
- Category selector dropdown (32 categories available)
- KPI cards: model count, benchmark count, avg score, top score
- TrueSkill ranking bar chart (top 15) color-coded by open/proprietary
- Open vs Proprietary comparison bar (which license type wins in this category?)
- Price vs Performance scatter plot (find underpriced performers)
- Full ranking table with conservative TrueSkill rating, pricing, benchmark count

**Use case:** "For coding tasks, which model gives the best TrueSkill rating? Is open-weight competitive here?"

---

### Page 4: Market Trends (`/trends`)

Temporal analysis of the LLM ecosystem.

**Features:**
- Performance evolution line chart by release quarter (All / Open / Proprietary)
- Release velocity bar chart (how many models ship per quarter?)
- Open vs Proprietary gap grouped bar chart across top categories
- Recently added models table (last 30 days) — what's new in the market

**Use case:** "Is the gap between open and proprietary models closing? Is the market accelerating?"

---

### Page 5: Cost Efficiency (`/cost`)

Value-for-money analysis with pricing data.

**Features:**
- Price vs Performance scatter plot with efficiency frontier (Pareto optimal line)
- Bubble size = number of benchmarks, color = open/proprietary
- Price tier breakdown (Budget <$1, Mid $1-5, Premium >$5) with avg scores
- Score-per-dollar ranking bar chart (top 15 best-value models)
- Full pricing table with input/output costs, throughput, and efficiency metric

**Use case:** "Which model gives me the most performance per dollar? Is premium pricing justified?"

---

### Page 6: Model Comparison (`/compare`)

Side-by-side comparison of up to 3 models with independent selectors.

**Features:**
- 3 separate dropdown filters (Model A, B, C) — no interference between selections
- Summary cards for each model showing rank, score, org, license
- Radar chart overlay — all selected models on one polar plot for profile comparison
- Grouped bar chart by category (which model wins in each domain?)
- Grouped bar chart by benchmark (only common benchmarks shown)
- Pivot table: benchmark × model scores with "Winner" column highlighted

**Use case:** "Claude vs GPT vs Gemini — which one should I pick for my use case?"

---

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

2. Create your environment file:
```bash
cp .env.example .env
# Edit .env with your API key and desired credentials
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
docker compose exec postgres psql -U $DB_USER -d $DB_NAME -f /docker-entrypoint-initdb.d/gold_views.sql
```

6. Access the dashboard at `http://localhost:8050`

### Services

| Service | Port | Description |
|---------|------|-------------|
| Dashboard | 8050 | Plotly/Dash analytics UI |
| PostgreSQL | 5434 | Data warehouse |
| Airflow Webserver | 8080 | DAG monitoring & management |

Credentials are configured via `.env` file (see `.env.example`).

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Database | PostgreSQL 16 | Raw storage + gold materialized views |
| Orchestration | Apache Airflow 2.9 | Daily ETL scheduling & monitoring |
| Dashboard | Plotly Dash 2.17 | Interactive analytics & visualization |
| ETL | Python (requests + psycopg2) | API ingestion with upsert logic |
| Infrastructure | Docker Compose | Single-command deployment |
| Proxy | Nginx Proxy Manager | Domain routing + SSL |

---

## Project Structure

```
├── dags/
│   └── llm_stats_dag.py          # Airflow DAG (daily 01:00 WIB)
├── dashboard/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py               # Dash app entry + layout + styling
│       ├── data.py               # Data layer with 5-min cache
│       ├── theme.py              # Color palette & chart helpers
│       └── pages/
│           ├── leaderboard.py    # Page 1: LLM Leaderboard
│           ├── model_deep_dive.py # Page 2: Model Deep Dive
│           ├── category.py       # Page 3: Category Leaderboard
│           ├── trends.py         # Page 4: Market Trends
│           ├── cost.py           # Page 5: Cost Efficiency
│           └── compare.py        # Page 6: Model Comparison
├── scripts/
│   ├── init.sql                  # Bronze layer DDL (6 tables)
│   ├── gold_views.sql            # Gold layer (6 materialized views)
│   └── etl.py                    # ETL pipeline (6 API endpoints)
├── docker-compose.yml            # Full stack orchestration
├── .env.example                  # Environment template
└── .gitignore
```

---

## API Endpoints Consumed

| # | Endpoint | Data | Merge Key |
|---|----------|------|-----------|
| 1 | `GET /stats/v1/models` | Model catalog + pricing | `id` |
| 2 | `GET /stats/v1/models/{id}` | Full model detail + all scores | `id` |
| 3 | `GET /stats/v1/benchmarks` | Benchmark definitions | `id` |
| 4 | `GET /stats/v1/scores` | Score matrix | `(model_id, benchmark_id, category)` |
| 5 | `GET /stats/v1/rankings?category=X` | TrueSkill rankings | `(category, model_id)` |
| 6 | `GET /stats/v1/updates?days=N` | Recently added models | `(id, days)` |

---

## Data Models

### Bronze Layer (Raw Tables)

6 tables storing raw API data with `createdAt`/`updatedAt` audit columns.

```
┌─────────────────────────────────────────────────────────────────┐
│ models                          PK: id                          │
├─────────────────────────────────────────────────────────────────┤
│ id                VARCHAR(255)   Model unique identifier         │
│ name              VARCHAR(500)   Display name                    │
│ organization_id   VARCHAR(255)   Org FK                          │
│ organization_name VARCHAR(500)   Org display name                │
│ family            VARCHAR(255)   Model family (GPT, Claude, etc) │
│ license_id        VARCHAR(255)   License identifier              │
│ license_name      VARCHAR(255)   License display name            │
│ open_weight       BOOLEAN        Open-weight flag                │
│ model_type        VARCHAR(100)   chat, completion, embedding     │
│ modalities        JSONB          [text, image, audio, ...]       │
│ context_window    INTEGER        Max context tokens              │
│ param_count       BIGINT         Parameter count                 │
│ release_date      DATE           Public release date             │
│ providers         JSONB          Available API providers         │
│ inference         JSONB          Pricing & throughput info        │
│ top_scores        JSONB          Best scores per category        │
│ createdAt         TIMESTAMPTZ    First ingestion time            │
│ updatedAt         TIMESTAMPTZ    Last refresh time               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ scores                          PK: (model_id, benchmark_id,    │
│                                      category)                  │
├─────────────────────────────────────────────────────────────────┤
│ model_id          VARCHAR(255)   FK → models.id                  │
│ benchmark_id      VARCHAR(255)   FK → benchmarks.id              │
│ category          VARCHAR(255)   Score category context          │
│ model_name        VARCHAR(500)   Denormalized model name         │
│ organization      VARCHAR(255)   Denormalized org name           │
│ benchmark_name    VARCHAR(500)   Denormalized benchmark name     │
│ score             FLOAT          Raw score value                 │
│ normalized_score  FLOAT          0-1 normalized score            │
│ max_score         FLOAT          Maximum possible score          │
│ is_self_reported  BOOLEAN        Self-reported flag              │
│ verified          BOOLEAN        Independently verified          │
│ scored_at         TIMESTAMPTZ    When the score was recorded     │
│ createdAt         TIMESTAMPTZ    First ingestion time            │
│ updatedAt         TIMESTAMPTZ    Last refresh time               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ benchmarks                      PK: id                          │
├─────────────────────────────────────────────────────────────────┤
│ id                VARCHAR(255)   Benchmark unique identifier     │
│ name              VARCHAR(500)   Display name                    │
│ description       TEXT           What the benchmark measures     │
│ categories        JSONB          Associated categories           │
│ modality          VARCHAR(100)   text, multimodal, etc           │
│ max_score         FLOAT          Maximum possible score          │
│ language          VARCHAR(50)    Benchmark language              │
│ verified          BOOLEAN        Verified benchmark              │
│ model_count       INTEGER        # models evaluated             │
│ createdAt         TIMESTAMPTZ    First ingestion time            │
│ updatedAt         TIMESTAMPTZ    Last refresh time               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ rankings                        PK: (category, model_id)        │
├─────────────────────────────────────────────────────────────────┤
│ category             VARCHAR(255)   Ranking category             │
│ model_id             VARCHAR(255)   FK → models.id              │
│ rank                 INTEGER        Position in leaderboard      │
│ model_name           VARCHAR(500)   Denormalized name            │
│ organization         VARCHAR(255)   Denormalized org             │
│ score                FLOAT          TrueSkill score              │
│ conservative_rating  FLOAT          Lower-bound TrueSkill        │
│ open_weight          BOOLEAN        Open-weight flag             │
│ min_input_price      FLOAT          Cheapest input price ($/M)   │
│ benchmarks_evaluated INTEGER        # benchmarks in ranking      │
│ method               VARCHAR(100)   Ranking methodology          │
│ ranked_at            TIMESTAMPTZ    When ranking was computed     │
│ createdAt            TIMESTAMPTZ    First ingestion time          │
│ updatedAt            TIMESTAMPTZ    Last refresh time             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ model_details                   PK: id                          │
├─────────────────────────────────────────────────────────────────┤
│ id                VARCHAR(255)   Same as models.id               │
│ (same columns as models)                                         │
│ all_scores        JSONB          Complete score array per model  │
│ createdAt         TIMESTAMPTZ    First ingestion time            │
│ updatedAt         TIMESTAMPTZ    Last refresh time               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ updates                         PK: (id, days)                  │
├─────────────────────────────────────────────────────────────────┤
│ id                VARCHAR(255)   Model ID                        │
│ days              INTEGER        Lookback window (1, 7, 30)      │
│ name              VARCHAR(500)   Model name                      │
│ organization_name VARCHAR(500)   Org name                        │
│ model_type        VARCHAR(100)   Model type                      │
│ release_date      DATE           Release date                    │
│ open_weight       BOOLEAN        Open-weight flag                │
│ added_at          TIMESTAMPTZ    When model was added            │
│ createdAt         TIMESTAMPTZ    First ingestion time            │
│ updatedAt         TIMESTAMPTZ    Last refresh time               │
└─────────────────────────────────────────────────────────────────┘
```

### Gold Layer (Materialized Views)

6 materialized views that join and aggregate Bronze tables into analysis-ready datasets.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         GOLD LAYER DEPENDENCY GRAPH                          │
│                                                                             │
│   Bronze Tables              Gold Views                                     │
│   ──────────────             ──────────                                     │
│                                                                             │
│   scores ─────────┬────→ gold_model_benchmark_scores                        │
│   models ─────────┘          │                                              │
│                              ├────→ gold_category_stats                      │
│                              └────→ gold_org_summary                         │
│                                                                             │
│   scores ─────────┬────→ gold_model_summary ────→ gold_model_pricing        │
│   models ─────────┘                         ←──── models                    │
│                                                                             │
│   rankings ───────┬────→ gold_category_leaderboard                          │
│   models ─────────┘                                                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### View 1: `gold_model_benchmark_scores`

Flat denormalized table joining `scores` with `models`. Adds computed `score_pct` (0–1 normalized).

| Column | Type | Description |
|--------|------|-------------|
| model_id | VARCHAR | Model identifier |
| model_name | VARCHAR | Display name |
| organization | VARCHAR | Organization name |
| open_weight | BOOLEAN | Open-weight flag |
| release_date | DATE | Release date |
| model_type | VARCHAR | Model type |
| benchmark_id | VARCHAR | Benchmark identifier |
| benchmark_name | VARCHAR | Benchmark name |
| category | VARCHAR | Category context |
| score | FLOAT | Raw score |
| normalized_score | FLOAT | Pre-normalized score |
| max_score | FLOAT | Max possible score |
| **score_pct** | **NUMERIC** | **Computed: score/max_score (0–1)** |
| is_self_reported | BOOLEAN | Self-reported flag |
| verified | BOOLEAN | Independently verified |
| scored_at | TIMESTAMPTZ | Score timestamp |

**Used by:** Leaderboard, Model Deep Dive, Category, Comparison pages

---

#### View 2: `gold_model_summary`

Per-model aggregation with overall rank across all benchmarks.

| Column | Type | Description |
|--------|------|-------------|
| model_id | VARCHAR | Model identifier |
| model_name | VARCHAR | Display name |
| organization | VARCHAR | Organization name |
| open_weight | BOOLEAN | Open-weight flag |
| release_date | DATE | Release date |
| model_type | VARCHAR | Model type |
| num_benchmarks | INTEGER | Distinct benchmarks evaluated |
| num_categories | INTEGER | Distinct categories covered |
| **avg_score_pct** | **NUMERIC** | **Mean score_pct across all benchmarks** |
| **overall_rank** | **INTEGER** | **RANK() by avg_score_pct DESC** |

**Used by:** Leaderboard (highlight cards, main table), Model Deep Dive (info card), Comparison (summary cards)

---

#### View 3: `gold_category_leaderboard`

TrueSkill rankings enriched with model metadata from `rankings` + `models`.

| Column | Type | Description |
|--------|------|-------------|
| category | VARCHAR | Ranking category |
| rank | INTEGER | Position in leaderboard |
| model_id | VARCHAR | Model identifier |
| model_name | VARCHAR | Display name |
| organization | VARCHAR | Organization name |
| score | FLOAT | TrueSkill score |
| conservative_rating | FLOAT | Lower-bound TrueSkill |
| open_weight | BOOLEAN | Open-weight flag |
| min_input_price | FLOAT | Cheapest input price ($/M tokens) |
| benchmarks_evaluated | INTEGER | Benchmarks in this ranking |
| method | VARCHAR | Ranking methodology |
| ranked_at | TIMESTAMPTZ | Ranking computation time |
| release_date | DATE | Model release date |
| model_type | VARCHAR | Model type |

**Used by:** Category Leaderboard page (TrueSkill chart, ranking table, price scatter)

---

#### View 4: `gold_category_stats`

Category-level KPIs aggregated from `gold_model_benchmark_scores`.

| Column | Type | Description |
|--------|------|-------------|
| category | VARCHAR | Category name |
| num_models | INTEGER | Distinct models in category |
| num_benchmarks | INTEGER | Distinct benchmarks in category |
| avg_score_pct | NUMERIC | Mean score across all models |
| max_score_pct | NUMERIC | Best score in category |
| min_score_pct | NUMERIC | Worst score in category |

**Used by:** Category Leaderboard page (KPI cards)

---

#### View 5: `gold_org_summary`

Organization-level performance aggregation from `gold_model_benchmark_scores`.

| Column | Type | Description |
|--------|------|-------------|
| organization | VARCHAR | Organization name |
| num_models | INTEGER | Models from this org |
| num_categories | INTEGER | Categories covered |
| avg_score_pct | NUMERIC | Mean score across all org models |
| max_score_pct | NUMERIC | Best score from org |
| model_names | TEXT[] | Array of model names |

**Used by:** Leaderboard page (organization bar chart)

---

#### View 6: `gold_model_pricing`

Cost efficiency metrics joining `models` (pricing) with `gold_model_summary` (performance).

| Column | Type | Description |
|--------|------|-------------|
| model_id | VARCHAR | Model identifier |
| model_name | VARCHAR | Display name |
| organization | VARCHAR | Organization name |
| open_weight | BOOLEAN | Open-weight flag |
| input_price | FLOAT | Input cost ($/M tokens) |
| output_price | FLOAT | Output cost ($/M tokens) |
| tokens_per_second | FLOAT | Inference throughput |
| avg_score_pct | NUMERIC | From gold_model_summary |
| overall_rank | INTEGER | From gold_model_summary |
| num_benchmarks | INTEGER | From gold_model_summary |
| **score_per_dollar** | **NUMERIC** | **avg_score_pct / input_price** |

**Used by:** Cost Efficiency page (scatter, tier breakdown, score-per-dollar ranking)

---

## ETL Pipeline Details

### Extraction

The ETL script (`scripts/etl.py`) fetches data from 6 API endpoints:

```
┌────────────────────────────────────────────────────────────────────┐
│                        ETL PIPELINE FLOW                            │
│                                                                    │
│  ┌──────────┐     ┌────────────────┐     ┌───────────────────┐   │
│  │ API Call  │────→│ Deduplicate    │────→│ Upsert to Postgres│   │
│  │ (paginated)│    │ (by PK in-mem) │     │ (ON CONFLICT)     │   │
│  └──────────┘     └────────────────┘     └───────────────────┘   │
│       │                                         │                  │
│       │ 200ms delay                             │ SET updatedAt    │
│       │ between pages                           │ = NOW()          │
│       ▼                                         ▼                  │
│  ┌──────────┐                           ┌───────────────────┐     │
│  │ Next page│                           │ createdAt only on │     │
│  │ (cursor) │                           │ first INSERT      │     │
│  └──────────┘                           └───────────────────┘     │
└────────────────────────────────────────────────────────────────────┘
```

### Pagination Strategy

| Endpoint | Pagination | Method |
|----------|-----------|--------|
| `/models` | Cursor-based | `cursor` param from response |
| `/scores` | Cursor-based | `cursor` param from response |
| `/benchmarks` | Single page | No pagination needed |
| `/rankings` | Per-category | Loop over 18+ categories |
| `/updates` | Per-window | Loop over days=[1, 7, 30] |
| `/models/{id}` | Per-model | Loop over all model IDs |

### Deduplication

Before upserting, records are deduplicated in-memory by their composite primary key. This prevents `CardinalityViolation` errors when the API returns duplicate records in paginated results.

### Orchestration (Airflow)

```
DAG: llm_stats_daily_ingestion
Schedule: 0 18 * * * (01:00 WIB / 18:00 UTC)
Retries: 2 (5 min delay between retries)
Task: run_etl (PythonOperator → etl.py main())
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LLM_STATS_API_KEY` | Yes | Bearer token for API authentication |
| `DB_NAME` | No | Database name (default: `llm`) |
| `DB_USER` | No | PostgreSQL username (default: `admin`) |
| `DB_PASS` | No | PostgreSQL password (default: `admin`) |
| `AIRFLOW_USER` | No | Airflow web UI username (default: `admin`) |
| `AIRFLOW_PASS` | No | Airflow web UI password (default: `admin`) |
