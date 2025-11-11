# Enhanced GraphRAG System with OpenAI and Ollama

A comprehensive GraphRAG (Graph Retrieval Augmented Generation) system that processes both structured (Excel) and unstructured (PDF) data to create knowledge graphs using Neo4j, OpenAI GPT-4o mini for LLM tasks, and Ollama for embeddings.

## Features

- 📄 **Multi-format Support**: Process PDFs and Excel files
- 🧠 **OpenAI Integration**: GPT-4o mini for high-quality text processing
- 🦙 **Ollama Embeddings**: Local embedding generation with nomic-embed-text
- 🗄️ **Neo4j Knowledge Graph**: Advanced graph database with APOC support
- 🔍 **Vector Search**: Semantic similarity search with embeddings
- 🕸️ **Graph Traversal**: Multi-hop relationship exploration
- 🚀 **FastAPI Backend**: Modern async Python web framework
- 🐳 **Docker Support**: Complete containerized deployment

## Quick Start

1. **Setup the environment:**
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

2. **Configure AI services:**
   ```bash
   # Get OpenAI API key from https://platform.openai.com/api-keys
   # Edit .env file and set OPENAI_API_KEY
   
   # Install Ollama from https://ollama.ai
   ollama serve
   ollama pull nomic-embed-text
   ```

3. **Test the setup:**
   ```bash
   ./scripts/test_models.py
   ```

4. **Start the system:**
   ```bash
   ./scripts/start.sh
   ```

## AI Models Used

- **LLM**: OpenAI GPT-4o mini - Cost-effective, fast, and capable
- **Embeddings**: Ollama nomic-embed-text - Local, private, and efficient
- **Benefits**: No GPU required, lower costs, privacy for embeddings

## API Endpoints

- `POST /upload` - Upload and process files
- `POST /query` - Query the knowledge graph
- `GET /health` - System health check
- `GET /cypher/templates` - Available Cypher queries
- `POST /cypher/execute` - Execute custom Cypher queries

## Configuration

Edit the `.env` file to configure:
- Neo4j connection settings
- vLLM model configuration
- Embedding model settings
- Processing parameters

## Development

Start development environment:
```bash
./scripts/dev.sh
```

Run tests:
```bash
./scripts/test.sh
```

## Architecture

The system consists of:
- **Document Processor**: Handles PDF/Excel ingestion and chunking
- **vLLM Inference**: Entity and relationship extraction
- **Neo4j Graph Manager**: Graph database operations
- **GraphRAG Engine**: Query processing and response generation
- **FastAPI Application**: REST API interface

## License

MIT License - see LICENSE file for details.
