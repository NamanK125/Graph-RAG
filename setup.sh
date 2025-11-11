#!/bin/bash

# Enhanced GraphRAG System Setup Script
# This script sets up the complete environment for the GraphRAG system

set -e  # Exit on any error

echo "🚀 Enhanced GraphRAG System Setup"
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root"
   exit 1
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check system requirements
check_requirements() {
    print_step "Checking system requirements..."
    
    # Check Python version
    if command_exists python3; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        print_status "Python version: $PYTHON_VERSION"
        
        # Check if Python version is 3.8 or higher
        if python3 -c 'import sys; exit(0 if sys.version_info >= (3, 8) else 1)'; then
            print_status "Python version is compatible"
        else
            print_error "Python 3.8 or higher is required"
            exit 1
        fi
    else
        print_error "Python 3 is not installed"
        exit 1
    fi
    
    # Check for pip
    if ! command_exists pip3; then
        print_error "pip3 is not installed"
        exit 1
    fi
    
    # Check for Docker
    if command_exists docker; then
        print_status "Docker is installed"
    else
        print_warning "Docker is not installed. Some features may not work."
    fi
    
    # Check for Docker Compose
    if command_exists docker-compose || docker compose version >/dev/null 2>&1; then
        print_status "Docker Compose is available"
    else
        print_warning "Docker Compose is not installed. Using local setup only."
    fi
    
    # Check for Git
    if command_exists git; then
        print_status "Git is installed"
    else
        print_error "Git is required for installation"
        exit 1
    fi
}

# Create project structure
create_project_structure() {
    print_step "Creating project structure..."
    
    # Create directories
    mkdir -p uploads
    mkdir -p models
    mkdir -p logs
    mkdir -p data/neo4j
    mkdir -p monitoring/grafana
    mkdir -p monitoring/prometheus
    mkdir -p tests
    mkdir -p scripts
    
    # Create logs directory with proper permissions
    chmod 755 logs
    
    print_status "Project structure created"
}

# Setup Python environment
setup_python_env() {
    print_step "Setting up Python virtual environment..."
    
    # Create virtual environment
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        print_status "Virtual environment created"
    else
        print_status "Virtual environment already exists"
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install requirements in stages to avoid conflicts
    if [ -f "requirements.txt" ]; then
        print_step "Installing Python dependencies..."
        
        # First, upgrade essential tools
        pip install --upgrade setuptools wheel pip
        
        # Install core dependencies first
        print_step "Installing core dependencies..."
        pip install fastapi uvicorn python-multipart python-dotenv pydantic
        
        # Install PyTorch first (common source of conflicts)
        print_step "Installing PyTorch..."
        pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
        
        # Install remaining requirements, but continue on errors
        print_step "Installing remaining dependencies..."
        if ! pip install -r requirements.txt --no-deps; then
            print_warning "Some packages failed to install. Trying individual installation..."
            
            # Try installing packages individually
            while IFS= read -r line; do
                # Skip comments and empty lines
                if [[ ! "$line" =~ ^[[:space:]]*# ]] && [[ -n "$line" ]]; then
                    package=$(echo "$line" | cut -d'#' -f1 | xargs)
                    if [[ -n "$package" ]]; then
                        echo "Installing: $package"
                        pip install "$package" || print_warning "Failed to install: $package"
                    fi
                fi
            done < requirements.txt
        fi
        
        print_status "Core Python dependencies installed"
        
        # Optionally install advanced packages
        if [ -f "requirements-optional.txt" ]; then
            read -p "Install optional packages (vLLM, spacy, etc.)? [y/N]: " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                print_step "Installing optional dependencies..."
                pip install -r requirements-optional.txt || print_warning "Some optional packages failed to install"
            fi
        fi
    else
        print_warning "requirements.txt not found"
    fi
}

# Setup environment configuration
setup_environment() {
    print_step "Setting up environment configuration..."
    
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example .env
            print_status "Created .env file from .env.example"
            print_warning "Please edit .env file with your configuration"
        else
            # Create basic .env file
            cat > .env << EOF
# Basic configuration for Enhanced GraphRAG System
NEO4J_URI=neo4j://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
NEO4J_DATABASE=neo4j

OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_TOKENS=2048
OPENAI_TEMPERATURE=0.1

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIMENSION=768

CHUNK_SIZE=1000
CHUNK_OVERLAP=200

DEBUG=false
LOG_LEVEL=INFO
EOF
            print_status "Created basic .env file"
        fi
    else
        print_status ".env file already exists"
    fi
}

# Setup Neo4j with Docker
setup_neo4j() {
    print_step "Setting up Neo4j database..."
    
    if command_exists docker; then
        # Check if Neo4j container is already running
        if docker ps | grep -q "graphrag_neo4j"; then
            print_status "Neo4j container is already running"
        else
            # Start Neo4j container
            docker run -d \
                --name graphrag_neo4j \
                -p 7474:7474 -p 7687:7687 \
                -e NEO4J_AUTH=neo4j/graphrag_password \
                -e NEO4J_PLUGINS='["apoc","graph-data-science"]' \
                -e NEO4J_dbms_security_procedures_unrestricted=apoc.*,gds.* \
                -e NEO4J_dbms_security_procedures_allowlist=apoc.*,gds.* \
                -e NEO4J_ACCEPT_LICENSE_AGREEMENT=yes \
                -v neo4j_data:/data \
                -v neo4j_logs:/logs \
                -v neo4j_import:/var/lib/neo4j/import \
                -v neo4j_plugins:/plugins \
                neo4j:5.15-enterprise
            
            print_status "Neo4j container started"
            print_status "Neo4j Browser: http://localhost:7474"
            print_status "Username: neo4j, Password: graphrag_password"
            
            # Wait for Neo4j to be ready
            print_step "Waiting for Neo4j to be ready..."
            sleep 30
        fi
    else
        print_warning "Docker not available. Please install Neo4j manually."
        print_warning "Visit: https://neo4j.com/download/"
    fi
}

# Setup OpenAI and Ollama
setup_models() {
    print_step "Setting up AI models..."
    
    # Create script to check and setup models
    cat > scripts/setup_models.sh << 'EOF'
#!/bin/bash

echo "🤖 Setting up AI Models"
echo "======================="

# Check OpenAI API key
if [ -z "$OPENAI_API_KEY" ] || [ "$OPENAI_API_KEY" = "your_openai_api_key_here" ]; then
    echo "⚠️  Please set your OpenAI API key in the .env file"
    echo "   Get your API key from: https://platform.openai.com/api-keys"
else
    echo "✅ OpenAI API key configured"
fi

# Check if Ollama is installed and running
if command -v ollama >/dev/null 2>&1; then
    echo "✅ Ollama is installed"
    
    # Check if Ollama is running
    if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        echo "✅ Ollama server is running"
        
        # Check if embedding model is available
        if ollama list | grep -q "nomic-embed-text"; then
            echo "✅ Embedding model (nomic-embed-text) is available"
        else
            echo "📥 Installing embedding model..."
            ollama pull nomic-embed-text
        fi
    else
        echo "❌ Ollama server is not running. Please start it with: ollama serve"
    fi
else
    echo "❌ Ollama is not installed"
    echo "   Install from: https://ollama.ai"
    echo "   After installation, run: ollama pull nomic-embed-text"
fi

echo ""
echo "🎉 Model setup completed!"
echo ""
echo "Required setup:"
echo "1. Set OPENAI_API_KEY in .env file"
echo "2. Install Ollama: https://ollama.ai"
echo "3. Start Ollama: ollama serve"
echo "4. Pull embedding model: ollama pull nomic-embed-text"
EOF
    
    # Make script executable
    chmod +x scripts/setup_models.sh
    
    # Run the script
    bash scripts/setup_models.sh
}

# Setup monitoring
setup_monitoring() {
    print_step "Setting up monitoring configuration..."
    
    # Create Prometheus configuration
    cat > monitoring/prometheus/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  # - "first_rules.yml"
  # - "second_rules.yml"

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'graphrag-app'
    static_configs:
      - targets: ['graphrag_app:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'neo4j'
    static_configs:
      - targets: ['neo4j:2004']
    metrics_path: '/metrics'
    scrape_interval: 30s
EOF

    # Create Grafana datasource configuration
    mkdir -p monitoring/grafana/provisioning/datasources
    cat > monitoring/grafana/provisioning/datasources/prometheus.yml << 'EOF'
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
EOF

    print_status "Monitoring configuration created"
}

# Create helper scripts
create_helper_scripts() {
    print_step "Creating helper scripts..."
    
    # Start script
    cat > scripts/start.sh << 'EOF'
#!/bin/bash
echo "🚀 Starting Enhanced GraphRAG System"

# Check if virtual environment exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo "✅ Virtual environment activated"
else
    echo "❌ Virtual environment not found. Run setup.sh first."
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found. Run setup.sh first."
    exit 1
fi

# Start the application
echo "Starting GraphRAG application..."
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
EOF

    # Stop script
    cat > scripts/stop.sh << 'EOF'
#!/bin/bash
echo "🛑 Stopping Enhanced GraphRAG System"

# Stop Docker containers
if command -v docker >/dev/null 2>&1; then
    echo "Stopping Docker containers..."
    docker stop graphrag_neo4j 2>/dev/null || true
    docker-compose down 2>/dev/null || true
fi

echo "✅ System stopped"
EOF

    # Development script
    cat > scripts/dev.sh << 'EOF'
#!/bin/bash
echo "🔧 Starting Development Environment"

# Activate virtual environment
source venv/bin/activate

# Set development environment variables
export DEBUG=true
export LOG_LEVEL=DEBUG

# Start with hot reload
uvicorn main:app --host 0.0.0.0 --port 8000 --reload --log-level debug
EOF

    # Test script
    cat > scripts/test.sh << 'EOF'
#!/bin/bash
echo "🧪 Running Tests"

# Activate virtual environment
source venv/bin/activate

# Run tests
pytest tests/ -v --cov=. --cov-report=html

echo "✅ Tests completed. Check htmlcov/index.html for coverage report."
EOF

    # Docker script
    cat > scripts/docker.sh << 'EOF'
#!/bin/bash
echo "🐳 Starting with Docker Compose"

# Check if docker-compose.yml exists
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ docker-compose.yml not found"
    exit 1
fi

# Start with Docker Compose
if command -v docker-compose >/dev/null 2>&1; then
    docker-compose up -d
elif docker compose version >/dev/null 2>&1; then
    docker compose up -d
else
    echo "❌ Docker Compose not found"
    exit 1
fi

echo "✅ System started with Docker Compose"
echo "🌐 Application: http://localhost:8000"
echo "🗄️  Neo4j Browser: http://localhost:7474"
echo "📊 Grafana: http://localhost:3000 (admin/graphrag_admin)"
EOF

    # Make all scripts executable
    chmod +x scripts/*.sh
    
    print_status "Helper scripts created"
}

# Create basic tests
create_tests() {
    print_step "Creating test files..."
    
    # Test configuration
    cat > tests/conftest.py << 'EOF'
import pytest
import asyncio
from fastapi.testclient import TestClient
from main import app

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
EOF

    # Basic API tests
    cat > tests/test_api.py << 'EOF'
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health_check():
    """Test the health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data

def test_cypher_templates():
    """Test getting Cypher templates"""
    response = client.get("/cypher/templates")
    assert response.status_code == 200
    data = response.json()
    assert "templates" in data
    assert "queries" in data

@pytest.mark.asyncio
async def test_upload_invalid_file():
    """Test uploading invalid file type"""
    files = {"file": ("test.txt", b"test content", "text/plain")}
    response = client.post("/upload", files=files)
    assert response.status_code == 400
EOF

    # Neo4j tests
    cat > tests/test_neo4j.py << 'EOF'
import pytest
from unittest.mock import Mock, patch
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@pytest.mark.skip(reason="Requires Neo4j connection")
def test_neo4j_connection():
    """Test Neo4j database connection"""
    from main import Neo4jGraphManager
    
    # This test requires a running Neo4j instance
    graph_manager = Neo4jGraphManager()
    # Add actual connection test here
    pass

@patch('main.GraphDatabase.driver')
def test_neo4j_manager_init(mock_driver):
    """Test Neo4j manager initialization"""
    from main import Neo4jGraphManager
    
    mock_driver.return_value = Mock()
    graph_manager = Neo4jGraphManager()
    
    assert graph_manager.driver is not None
    mock_driver.assert_called_once()
EOF

    print_status "Test files created"
}

# Final setup and verification
final_setup() {
    print_step "Performing final setup..."
    
    # Create README
    cat > README.md << 'EOF'
# Enhanced GraphRAG System with vLLM Integration

A comprehensive GraphRAG (Graph Retrieval Augmented Generation) system that processes both structured (Excel) and unstructured (PDF) data to create knowledge graphs using Neo4j and vLLM for inference.

## Features

- 📄 **Multi-format Support**: Process PDFs and Excel files
- 🧠 **vLLM Integration**: High-performance LLM inference
- 🗄️ **Neo4j Knowledge Graph**: Advanced graph database with APOC support
- 🔍 **Vector Search**: Semantic similarity search with embeddings
- 🕸️ **Graph Traversal**: Multi-hop relationship exploration
- 🚀 **FastAPI Backend**: Modern async Python web framework
- 🐳 **Docker Support**: Complete containerized deployment
- 📊 **Monitoring**: Grafana and Prometheus integration

## Quick Start

1. **Setup the environment:**
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

2. **Start the system:**
   ```bash
   ./scripts/start.sh
   ```

3. **Or use Docker:**
   ```bash
   ./scripts/docker.sh
   ```

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
EOF

    # Create .gitignore
    cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/

# Environment
.env
.env.local

# Data and uploads
uploads/
models/
data/
logs/
*.log

# Testing
.pytest_cache/
htmlcov/
.coverage

# IDEs
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Docker
.dockerignore

# Neo4j
neo4j_data/
neo4j_logs/
EOF

    print_status "Documentation and configuration files created"
}

# Main installation flow
main() {
    print_step "Starting Enhanced GraphRAG System setup..."
    
    check_requirements
    create_project_structure
    setup_environment
    setup_python_env
    setup_neo4j
    setup_models
    setup_monitoring
    create_helper_scripts
    create_tests
    final_setup
    
    echo ""
    echo "🎉 Enhanced GraphRAG System setup completed!"
    echo "=================================="
    echo ""
    echo "Next steps:"
    echo "1. Edit .env file with your configuration"
    echo "2. Start the system: ./scripts/start.sh"
    echo "3. Or use Docker: ./scripts/docker.sh"
    echo ""
    echo "URLs:"
    echo "• Application: http://localhost:8000"
    echo "• API Docs: http://localhost:8000/docs"
    echo "• Neo4j Browser: http://localhost:7474"
    echo "• Grafana: http://localhost:3000 (if using Docker)"
    echo ""
    echo "For development: ./scripts/dev.sh"
    echo "For testing: ./scripts/test.sh"
    echo ""
    print_status "Setup complete! 🚀"
}

# Run main function
main "$@"