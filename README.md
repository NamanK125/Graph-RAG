# Walmart Graph Analytics Platform

A Graph-powered Customer Intelligence Platform built on Neo4j, LangChain, and OpenAI. Ingests Walmart public datasets, builds a rich knowledge graph of customers → products → stores → transactions, and lets analysts query it in plain English via a GraphRAG engine.

---

## Architecture

```
Walmart Datasets (Kaggle M5 + Store Sales + Synthetic Customers)
        ↓
   [ETL Pipeline]  ──→  Neo4j Knowledge Graph
        ↓
[Analytics Modules]   [GraphRAG NL Query Engine]   [FastAPI]
        ↓                       ↓                      ↓
  ML models               GPT-4o mini           REST API / Streamlit
```

**Stack:** FastAPI · Neo4j 5 · LangChain · OpenAI GPT-4o mini · Ollama (nomic-embed-text) · Docker

---

## Quick Start

### 1. Prerequisites

- Docker & Docker Compose
- Python 3.11+
- OpenAI API key
- Kaggle API credentials (for dataset download)

### 2. Clone & configure

```bash
git clone <repo-url>
cd Graph-RAG
cp .env.example .env
# Edit .env and set OPENAI_API_KEY, NEO4J_PASSWORD
```

### 3. Download datasets

Add your Kaggle credentials to `~/.kaggle/kaggle.json`, then:

```bash
python data/download_datasets.py
```

This downloads the Walmart M5 Forecasting dataset, Walmart Store Sales dataset, and generates 50k synthetic customer profiles into `data/raw/`.

### 4. Start services

```bash
docker compose up -d
```

Services started:
- **Neo4j** — `http://localhost:7474` (browser) · `bolt://localhost:7687`
- **Ollama** — `http://localhost:11434`
- **GraphRAG API** — `http://localhost:8000`

### 5. Pull embedding model

```bash
docker exec graphrag_ollama ollama pull nomic-embed-text
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service health check |
| `POST` | `/upload` | Upload & process a PDF or Excel file |
| `POST` | `/extract` | Extract entities/relationships from a file |
| `POST` | `/query` | Natural language GraphRAG query |
| `GET` | `/cypher/templates` | List available Cypher query templates |
| `POST` | `/cypher/execute` | Execute a raw Cypher query |

### Example — NL query

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Which customers bought electronics last quarter but haven'\''t returned?"}'
```

---

## Data Layer (`data/`)

| File | Purpose |
|------|---------|
| `download_datasets.py` | Kaggle API downloader for M5 + Store Sales datasets |
| `synthetic_customers.py` | Faker-based generator for 50k customer profiles |
| `etl.py` | Transform raw CSVs into Neo4j-ready format |

---

## Graph Schema

```
(:Customer {id, name, age, location, loyalty_tier, clv_score, churn_risk})
(:Product  {id, name, category, dept, price, brand})
(:Store    {id, location, region, size_sqft, type})
(:Transaction {id, date, total, channel})
(:Category {name, dept})
(:Promotion {id, type, discount_pct, start_date, end_date})
(:Holiday  {name, date})

(Customer)-[:MADE]->(Transaction)
(Transaction)-[:CONTAINS {qty, price}]->(Product)
(Transaction)-[:AT]->(Store)
(Transaction)-[:DURING]->(Holiday)
(Promotion)-[:APPLIED_TO]->(Transaction)
(Product)-[:IN_CATEGORY]->(Category)
(Customer)-[:LIVES_NEAR]->(Store)
(Product)-[:FREQUENTLY_BOUGHT_WITH {confidence, lift}]->(Product)
```

---

## Configuration

All configuration lives in `.env`. Key variables:

```env
OPENAI_API_KEY=sk-...
NEO4J_PASSWORD=your_password
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
OPENAI_MODEL=gpt-4o-mini
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
SIMILARITY_THRESHOLD=0.85
```

See `.env.example` for all available options.

---

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run API locally (Neo4j + Ollama must be running)
uvicorn main:app --reload --port 8000

# Run tests
pytest
```

---

## License

MIT
