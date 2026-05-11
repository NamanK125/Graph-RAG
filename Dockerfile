# ── Builder ───────────────────────────────────────────────────────────────────
FROM python:3.13-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# ── Runtime ───────────────────────────────────────────────────────────────────
FROM python:3.13-slim

# ── Python runtime flags ──────────────────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# ── Neo4j defaults (overridden by compose / docker run -e) ───────────────────
ENV NEO4J_URI=neo4j://localhost:7687 \
    NEO4J_USERNAME=neo4j \
    NEO4J_PASSWORD=graphrag_password \
    NEO4J_DATABASE=neo4j

# ── Ollama defaults ───────────────────────────────────────────────────────────
ENV OLLAMA_BASE_URL=http://localhost:11434 \
    OLLAMA_EMBEDDING_MODEL=nomic-embed-text \
    OLLAMA_LLM_FALLBACK_MODEL=llama3.2

# ── OpenAI defaults ───────────────────────────────────────────────────────────
ENV OPENAI_API_KEY="" \
    OPENAI_MODEL=gpt-4o-mini

# ── App tuning defaults ───────────────────────────────────────────────────────
ENV CHUNK_SIZE=1000 \
    CHUNK_OVERLAP=200 \
    SIMILARITY_THRESHOLD=0.85

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

RUN groupadd -r app && useradd -r -g app -d /app app \
 && chown app:app /app

COPY --chown=app:app entrypoint.sh .
COPY --chown=app:app main.py       .
COPY --chown=app:app data/         ./data/

USER app

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
