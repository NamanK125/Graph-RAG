# RAG-Enabled Retail Decision Making — Implementation Plan

## What We're Building

A production-grade GraphRAG system that replaces human decision-making loops in retail operations. Five AI agents — each owning a decision domain — share a common hybrid retrieval layer backed by Neo4j, vector search, and full-text indexes. Analysts and automated systems query the orchestrator in plain English; the orchestrator routes to the right agent(s), retrieves grounded context, and returns a structured decision with citations.

---

## Architecture

```
Natural Language Query
        ↓
  RetailOrchestrator
  (domain classifier)
        ↓
 ┌──────┬──────┬──────┬──────┐
 │Inven-│Pric- │Logi- │Store │Cust- │
 │tory  │ing   │stics │Ops   │omer  │
 │Agent │Agent │Agent │Agent │Agent │
 └──────┴──────┴──────┴──────┴──────┘
        ↓
  HybridRetriever
  ┌─────────────────────────────┐
  │ Semantic  │ Graph  │ Keyword │
  │ (Ollama)  │(Neo4j) │(FTS)    │
  └─────────────────────────────┘
        ↓
    Neo4j Knowledge Graph
    + Vector Indexes (APOC)
        ↓
  OpenAI GPT-4o mini
  (structured decision output)
```

---

## Graph Schema

```cypher
(:Customer   {id, name, age, location, loyalty_tier, clv_score, churn_risk})
(:Product    {id, name, category, dept, price, brand, inventory_age_days, reorder_point})
(:Store      {id, location, region, size_sqft, type, employee_count, avg_daily_transactions})
(:Transaction{id, date, total, channel, hour})
(:Category   {name, dept})
(:Promotion  {id, type, discount_pct, start_date, end_date})
(:Holiday    {name, date})
(:Supplier   {id, name, lead_time_days, reliability_score, sla_days, region})
(:Warehouse  {id, location, region, capacity_units, current_stock})
(:DelayEvent {id, type, reason, severity, start_date, resolved_date})

(Customer)-[:MADE]->(Transaction)
(Transaction)-[:CONTAINS {qty, price}]->(Product)
(Transaction)-[:AT]->(Store)
(Transaction)-[:DURING]->(Holiday)
(Promotion)-[:APPLIED_TO]->(Transaction)
(Product)-[:IN_CATEGORY]->(Category)
(Product)-[:STOCKED_AT {units, reorder_point}]->(Store)
(Product)-[:SUPPLIED_BY]->(Supplier)
(Supplier)-[:DELIVERS_TO]->(Warehouse)
(Warehouse)-[:SHIPS_TO]->(Store)
(Supplier)-[:HAS_DELAY]->(DelayEvent)
(Customer)-[:LIVES_NEAR]->(Store)
(Product)-[:FREQUENTLY_BOUGHT_WITH {confidence, lift}]->(Product)
```

---

## Phase 1 — Hybrid Retrieval Layer

**File:** `retrieval/hybrid.py`

Three retrieval modes combined into one interface:

| Mode | Mechanism | Best for |
|------|-----------|----------|
| Semantic | Ollama `nomic-embed-text` + Neo4j vector index | Conceptual/policy questions |
| Graph | Parameterised Cypher queries | Relationship traversal, exact lookups |
| Keyword | Neo4j full-text search index | SKU IDs, store codes, supplier names |

`HybridRetriever.retrieve(query, cypher, k)` — runs all three, deduplicates, scores, returns ranked `RetrievedContext` list.

---

## Phase 2 — Base Agent Framework

**File:** `agents/base.py`

`BaseRetailAgent` defines the contract every domain agent implements:

- `domain: str` — used for routing
- `system_prompt: str` — domain-specific instructions for the LLM
- `graph_context_query(question) -> str` — returns Cypher to fetch domain data
- `decide(question) -> DecisionOutput` — retrieves context + calls LLM + returns typed decision

`DecisionOutput` (Pydantic):
```python
{
  domain: str,
  action: str,          # human-readable recommended action
  reasoning: str,       # chain-of-thought explanation
  confidence: float,    # 0–1
  data: dict,           # structured decision payload (domain-specific)
  citations: list[str]  # source nodes / documents used
}
```

---

## Phase 3 — Domain Agents (5)

### 3a. InventoryAgent (`agents/inventory.py`)

**Retrieves:** historical sales, seasonal demand, vendor lead times, warehouse stock, promotion calendars, weather/events, supply chain disruptions

**Graph query focus:**
```cypher
MATCH (p:Product)-[:STOCKED_AT]->(s:Store)
MATCH (p)-[:SUPPLIED_BY]->(sup:Supplier)
OPTIONAL MATCH (t:Transaction)-[:CONTAINS]->(p)
WHERE t.date >= date() - duration({days: 90})
RETURN p, s, sup, count(t) as recent_sales
```

**Decision payload:**
```json
{
  "sku": "ITEM_123",
  "store": "TX_1",
  "action": "reorder",
  "quantity": 240,
  "urgency": "high",
  "stockout_probability": 0.87,
  "suggested_transfer_from": "TX_2"
}
```

---

### 3b. PricingAgent (`agents/pricing.py`)

**Retrieves:** inventory aging, recent sales velocity, category demand trends, active promotions

**Graph query focus:**
```cypher
MATCH (p:Product)
OPTIONAL MATCH (t:Transaction)-[:CONTAINS]->(p)
WHERE t.date >= date() - duration({days: 30})
RETURN p.id, p.name, p.current_price, p.inventory_age_days,
       count(t) as sales_30d, avg(t.total) as avg_basket
```

**Decision payload:**
```json
{
  "sku": "ITEM_456",
  "store": "CA_1",
  "price_change_pct": -7.0,
  "trigger": "inventory_age_gt_40_days",
  "expected_velocity_lift": "18%",
  "margin_impact": "-2.1%"
}
```

---

### 3c. LogisticsAgent (`agents/logistics.py`)

**Retrieves:** supplier delay events, warehouse routes, shipment priorities, SLA history

**Graph query focus:**
```cypher
MATCH (sup:Supplier)-[:DELIVERS_TO]->(w:Warehouse)-[:SHIPS_TO]->(s:Store)
OPTIONAL MATCH (sup)-[:HAS_DELAY]->(d:DelayEvent)
WHERE d.start_date >= date() - duration({days: 7})
RETURN sup, w, s, collect(d) as active_delays
```

**Decision payload:**
```json
{
  "shipment_id": "SHP_789",
  "action": "reroute",
  "alternate_hub": "Warehouse_B",
  "delay_avoided_days": 2,
  "affected_skus": ["ITEM_001", "ITEM_002"],
  "urgency": "critical"
}
```

---

### 3d. StoreOpsAgent (`agents/store_ops.py`)

**Retrieves:** transaction volume by hour, store load vs. baseline, employee schedule, day-of-week patterns

**Graph query focus:**
```cypher
MATCH (s:Store)
OPTIONAL MATCH (t:Transaction)-[:AT]->(s)
WHERE t.date = date() AND t.hour >= (localtime().hour - 2)
WITH s, count(t) as recent_txn_rate
RETURN s.id, s.location, s.employee_count, recent_txn_rate,
       s.avg_daily_transactions,
       recent_txn_rate * 1.0 / s.avg_daily_transactions as load_ratio
ORDER BY load_ratio DESC
```

**Decision payload:**
```json
{
  "store": "CA_2",
  "action": "open_checkouts",
  "additional_counters": 3,
  "time_window": "18:00–20:00",
  "trigger": "load_ratio_1.8x_baseline"
}
```

---

### 3e. CustomerAgent (`agents/customer.py`)

**Retrieves:** purchase history, loyalty tier, churn risk score, CLV, product affinity graph

**Graph query focus:**
```cypher
MATCH (c:Customer {id: $customer_id})
OPTIONAL MATCH (c)-[:MADE]->(t:Transaction)-[:CONTAINS]->(p:Product)
WHERE t.date >= date() - duration({days: 180})
WITH c, collect(distinct p.category) as categories,
     count(t) as purchases, max(t.date) as last_purchase
RETURN c, categories, purchases, last_purchase
```

**Decision payload:**
```json
{
  "customer_id": "CUST_101",
  "action": "churn_prevention",
  "offer": "15% off next purchase in Electronics",
  "channel": "email",
  "predicted_churn_probability": 0.73,
  "clv_segment": "high_value"
}
```

---

## Phase 4 — Orchestrator

**File:** `agents/orchestrator.py`

1. **Domain classification** — LLM call with all 5 domain descriptions → returns list of relevant domains
2. **Parallel dispatch** — calls each relevant agent concurrently (`asyncio.gather`)
3. **Synthesis** — final LLM call merges multi-domain decisions into a unified narrative response

Example multi-domain query:
> "Why are beverage sales dropping in South Kolkata stores?"
→ routes to: `inventory` + `pricing` + `store_ops`

---

## Phase 5 — API Endpoints

New endpoints added to `main.py`:

```
POST /decide                    — Orchestrator: full NL → decision pipeline
POST /decide/inventory          — Inventory-specific decision
POST /decide/pricing            — Pricing-specific decision
POST /decide/logistics          — Supply chain decision
POST /decide/store-ops          — Store operations decision
POST /decide/customer/{id}      — Customer-specific recommendation

GET  /graph/inventory/status    — Current stock levels by store/SKU
GET  /graph/pricing/aging       — Products with high inventory age
GET  /graph/logistics/delays    — Active supply chain delays
GET  /graph/stores/load         — Real-time store transaction load
GET  /graph/customers/at-risk   — High churn-risk customers
```

---

## Phase 6 — Schema Extensions + ETL Update

Extend `data/etl.py` to load new node types:
- `Supplier` nodes with lead time, reliability, SLA
- `Warehouse` nodes with region + capacity
- `DelayEvent` nodes (synthetic, event-driven)
- Add `inventory_age_days`, `reorder_point` to Product
- Add `hour` field to Transaction for intraday store ops queries
- New relationships: `STOCKED_AT`, `SUPPLIED_BY`, `DELIVERS_TO`, `SHIPS_TO`, `HAS_DELAY`

---

## Phase 7 — README + Docker Update

- Complete README rewrite reflecting decision-making focus
- Add `langgraph` to requirements (for future agentic scaling)
- No new Docker services needed for MVP

---

## Implementation Order

| Step | Task | File(s) | Est. |
|------|------|---------|------|
| 1 | Hybrid retriever | `retrieval/hybrid.py` | 0.5d |
| 2 | Base agent + DecisionOutput schema | `agents/base.py` | 0.5d |
| 3 | 5 domain agents | `agents/*.py` | 1.5d |
| 4 | Orchestrator + routing | `agents/orchestrator.py` | 1d |
| 5 | New API endpoints | `main.py` | 0.5d |
| 6 | ETL schema extensions | `data/etl.py` | 1d |
| 7 | README + docs | `README.md` | 0.5d |

**Total: ~5.5 days for a complete working system.**
