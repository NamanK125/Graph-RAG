# Enhanced GraphRAG System with OpenAI and Ollama Integration
# Based on neo4j-labs/llm-graph-builder with OpenAI GPT-4o mini and Ollama embeddings

import os
import asyncio
import json
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from pathlib import Path
import hashlib
import uuid

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Core libraries
import pandas as pd
import numpy as np
from neo4j import GraphDatabase
import requests
# FastAPI imports
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager
import uvicorn

# LangChain imports for document processing
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_neo4j import Neo4jGraph
from langchain_experimental.graph_transformers import LLMGraphTransformer

# OpenAI imports
from openai import OpenAI
import ollama

# =============================================================================
# Configuration and Models
# =============================================================================

@dataclass
class Config:
    # Neo4j Configuration
    NEO4J_URI: str = "neo4j://localhost:7687"
    NEO4J_USERNAME: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    NEO4J_DATABASE: str = "neo4j"
    
    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_MAX_TOKENS: int = 2048
    OPENAI_TEMPERATURE: float = 0.1
    
    # Ollama Configuration
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    OLLAMA_LLM_FALLBACK_MODEL: str = "llava"
    EMBEDDING_DIMENSION: int = 768
    
    # Processing Configuration
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    MAX_WORKERS: int = 4
    SIMILARITY_THRESHOLD: float = 0.85

config = Config()

# =============================================================================
# Pydantic Models for API
# =============================================================================

class FileUploadResponse(BaseModel):
    file_id: str
    filename: str
    status: str
    message: str

class GraphExtractionRequest(BaseModel):
    file_id: str
    extraction_schema: Optional[Dict[str, Any]] = None
    custom_instructions: Optional[str] = None

class QueryRequest(BaseModel):
    query: str
    max_context_tokens: int = 6000
    max_hops: int = 3
    similarity_threshold: float = 0.85

class QueryResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    graph_context: List[Dict[str, Any]]
    processing_time: float

# =============================================================================
# OpenAI Integration Class
# =============================================================================

class OpenAIInference:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", fallback_model: str = "llava"):
        """Initialize OpenAI client for inference with Ollama fallback"""
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.fallback_model = fallback_model
        self.use_fallback = False
        
        try:
            # Test the API key by making a simple request
            self.client.models.list()
            print(f"✅ OpenAI model {model} initialized successfully")
        except Exception as e:
            print(f"❌ Error initializing OpenAI model: {e}")
            print(f"⚠️ Will use Ollama {fallback_model} as fallback when needed")
            # Don't raise - allow fallback to work
    
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate response using OpenAI with Ollama fallback"""
        try:
            # Try OpenAI first if not using fallback
            if not self.use_fallback:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=kwargs.get('max_tokens', config.OPENAI_MAX_TOKENS),
                    temperature=kwargs.get('temperature', config.OPENAI_TEMPERATURE),
                )
                return response.choices[0].message.content.strip()
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "quota" in error_str.lower() or "insufficient_quota" in error_str.lower():
                print(f"⚠️ OpenAI quota exceeded (Error 429), switching to Ollama {self.fallback_model}")
                self.use_fallback = True
            else:
                print(f"❌ OpenAI error: {e}, trying Ollama fallback")
        
        # Use Ollama fallback
        try:
            print(f"🔄 Using Ollama {self.fallback_model} as fallback")
            response = ollama.chat(
                model=self.fallback_model,
                messages=[{"role": "user", "content": prompt}]
            )
            return response['message']['content'].strip()
        except Exception as fallback_error:
            print(f"❌ Both OpenAI and Ollama failed. OpenAI error: {e}, Ollama error: {fallback_error}")
            return f"Error: Unable to generate response. Please check your OpenAI quota and ensure Ollama is running with {self.fallback_model} model."
    
    def extract_entities_relationships(self, text: str, schema: Optional[Dict] = None) -> Dict[str, Any]:
        """Extract entities and relationships from text using OpenAI with Ollama fallback"""
        
        # Create extraction prompt based on schema
        if schema:
            node_types = schema.get('nodes', [])
            relationship_types = schema.get('relationships', [])
            schema_prompt = f"""
            Extract entities of these types: {', '.join(node_types)}
            Extract relationships of these types: {', '.join(relationship_types)}
            """
        else:
            schema_prompt = "Extract all entities and their relationships."
        
        prompt = f"""
        You are an expert knowledge graph extractor. Analyze the following text and extract entities and relationships.
        
        {schema_prompt}
        
        Text to analyze:
        {text}
        
        Return your response in this exact JSON format:
        {{
            "entities": [
                {{
                    "id": "unique_id",
                    "label": "EntityType",
                    "properties": {{
                        "name": "entity_name",
                        "description": "entity_description"
                    }}
                }}
            ],
            "relationships": [
                {{
                    "source": "source_entity_id",
                    "target": "target_entity_id",
                    "type": "RELATIONSHIP_TYPE",
                    "properties": {{
                        "description": "relationship_description"
                    }}
                }}
            ]
        }}
        
        Important: Return only valid JSON, no additional text.
        """
        
        response = self.generate(prompt)
        
        # Handle error responses
        if response.startswith("Error:"):
            print(f"❌ Failed to extract entities: {response}")
            return {"entities": [], "relationships": []}
        
        try:
            # Parse the JSON response
            extracted_data = json.loads(response)
            return extracted_data
        except json.JSONDecodeError:
            print(f"❌ Failed to parse JSON from response: {response}")
            # Try to extract JSON from response if it's wrapped in other text
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    extracted_data = json.loads(json_match.group())
                    return extracted_data
                except json.JSONDecodeError:
                    pass
            return {"entities": [], "relationships": []}

# =============================================================================
# Ollama Embedding Integration
# =============================================================================

class OllamaEmbedding:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "nomic-embed-text"):
        """Initialize Ollama embedding client"""
        self.base_url = base_url
        self.model = model
        
        try:
            # Test connection to Ollama
            response = requests.get(f"{base_url}/api/tags")
            if response.status_code == 200:
                print(f"✅ Ollama embedding model {model} initialized successfully")
            else:
                raise Exception(f"Ollama server not accessible at {base_url}")
        except Exception as e:
            print(f"❌ Error initializing Ollama embedding: {e}")
            print("Make sure Ollama is running and the model is pulled:")
            print(f"  ollama pull {model}")
            raise
    
    def encode(self, texts: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        """Create embeddings using Ollama"""
        try:
            if isinstance(texts, str):
                single_text = True
                texts = [texts]
            else:
                single_text = False
            
            embeddings = []
            for text in texts:
                response = ollama.embeddings(
                    model=self.model,
                    prompt=text
                )
                embeddings.append(response['embedding'])
            
            return embeddings[0] if single_text else embeddings
        except Exception as e:
            print(f"❌ Error creating embeddings with Ollama: {e}")
            if isinstance(texts, list) and len(texts) > 1:
                return [None] * len(texts)
            else:
                return None

# =============================================================================
# Neo4j Graph Manager
# =============================================================================

class Neo4jGraphManager:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD)
        )
        # Remove Neo4jGraph dependency for now since it requires APOC
        self._setup_indexes()
    
    def _setup_indexes(self):
        """Setup necessary indexes and constraints"""
        with self.driver.session(database=config.NEO4J_DATABASE) as session:
            # Create text indexes for search (no vector indexes for now)
            try:
                # Create text index for full-text search on entities
                session.run("""
                    CREATE FULLTEXT INDEX entity_search IF NOT EXISTS
                    FOR (n:Entity) ON EACH [n.name, n.description]
                """)
                
                # Create text index for chunk content search
                session.run("""
                    CREATE FULLTEXT INDEX chunk_search IF NOT EXISTS
                    FOR (c:Chunk) ON EACH [c.text]
                """)
                
                # Create constraints
                session.run("CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE")
                session.run("CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE")
                session.run("CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE")
                
                print("✅ Neo4j indexes and constraints created successfully")
            except Exception as e:
                print(f"⚠️ Warning: Some indexes may already exist: {e}")
    
    def create_document_node(self, file_id: str, filename: str, file_type: str, metadata: Dict) -> str:
        """Create a document node in Neo4j"""
        with self.driver.session(database=config.NEO4J_DATABASE) as session:
            result = session.run("""
                CREATE (d:Document {
                    id: $file_id,
                    filename: $filename,
                    file_type: $file_type,
                    created_at: datetime(),
                    page_count: $page_count,
                    file_size: $file_size
                })
                RETURN d.id as id
            """, 
            file_id=file_id, 
            filename=filename, 
            file_type=file_type,
            page_count=metadata.get('page_count', 0),
            file_size=metadata.get('file_size', 0)
            )
            return result.single()["id"]
    
    def create_chunk_nodes(self, file_id: str, chunks: List[Dict]) -> List[str]:
        """Create chunk nodes and link them to document (without embeddings)"""
        chunk_ids = []
        with self.driver.session(database=config.NEO4J_DATABASE) as session:
            for i, chunk in enumerate(chunks):
                chunk_id = f"{file_id}_chunk_{i}"
                session.run("""
                    MATCH (d:Document {id: $file_id})
                    CREATE (c:Chunk {
                        id: $chunk_id,
                        text: $text,
                        chunk_index: $chunk_index,
                        token_count: $token_count
                    })
                    CREATE (d)-[:HAS_CHUNK]->(c)
                """, 
                file_id=file_id,
                chunk_id=chunk_id,
                text=chunk['text'],
                chunk_index=i,
                token_count=chunk.get('token_count', 0)
                )
                chunk_ids.append(chunk_id)
        return chunk_ids
    
    def create_entities_and_relationships(self, file_id: str, extracted_data: Dict):
        """Create entity and relationship nodes from extracted data"""
        with self.driver.session(database=config.NEO4J_DATABASE) as session:
            # Create entities
            for entity in extracted_data.get("entities", []):
                session.run("""
                    MERGE (e:Entity {id: $id})
                    SET e.label = $label,
                        e.name = $name,
                        e.description = $description,
                        e.source_document = $file_id
                """, 
                id=entity["id"],
                label=entity["label"],
                name=entity["properties"]["name"],
                description=entity["properties"].get("description", ""),
                file_id=file_id
                )
            
            # Create relationships
            for rel in extracted_data.get("relationships", []):
                session.run("""
                    MATCH (source:Entity {id: $source_id})
                    MATCH (target:Entity {id: $target_id})
                    MERGE (source)-[r:RELATED {type: $rel_type}]->(target)
                    SET r.description = $description,
                        r.source_document = $file_id
                """,
                source_id=rel["source"],
                target_id=rel["target"],
                rel_type=rel["type"],
                description=rel["properties"].get("description", ""),
                file_id=file_id
                )
    
    def text_similarity_search(self, query: str, k: int = 10) -> List[Dict]:
        """Perform text-based similarity search using Neo4j full-text search"""
        with self.driver.session(database=config.NEO4J_DATABASE) as session:
            # Use full-text search on chunk content
            result = session.run("""
                CALL db.index.fulltext.queryNodes('chunk_search', $search_query)
                YIELD node, score
                MATCH (d:Document)-[:HAS_CHUNK]->(node)
                RETURN node.id as chunk_id, node.text as text, score, d.filename as source_file
                ORDER BY score DESC
                LIMIT $k
            """, search_query=query, k=k)
            
            return [record.data() for record in result]
    
    def search_entities_by_text(self, query: str, k: int = 10) -> List[Dict]:
        """Search entities using full-text search"""
        with self.driver.session(database=config.NEO4J_DATABASE) as session:
            result = session.run("""
                CALL db.index.fulltext.queryNodes('entity_search', $search_query)
                YIELD node, score
                RETURN node.name AS entity_name, node.description AS description, score
                ORDER BY score DESC
                LIMIT $k
            """, search_query=query, k=k)
            
            return [record.data() for record in result]
    
    def graph_traversal_search(self, entity_ids: List[str], max_hops: int = 3) -> List[Dict]:
        """Perform graph traversal from given entity IDs (simplified without APOC)"""
        with self.driver.session(database=config.NEO4J_DATABASE) as session:
            # Simple traversal without APOC - get direct relationships up to max_hops
            result = session.run("""
                MATCH (start:Entity)
                WHERE start.id IN $entity_ids
                MATCH path = (start)-[*1..$max_hops]-(connected)
                RETURN DISTINCT start, connected, relationships(path) as rels
                LIMIT 100
            """, entity_ids=entity_ids, max_hops=max_hops)
            
            graph_data = []
            nodes_seen = set()
            relationships_seen = set()
            
            for record in result:
                start_node = dict(record["start"])
                connected_node = dict(record["connected"])
                
                # Add nodes if not already seen
                if start_node.get("id") not in nodes_seen:
                    nodes_seen.add(start_node["id"])
                    graph_data.append({"type": "node", "data": start_node})
                
                if connected_node.get("id") not in nodes_seen:
                    nodes_seen.add(connected_node["id"])
                    graph_data.append({"type": "node", "data": connected_node})
                
                # Add relationships
                for rel in record["rels"]:
                    rel_data = dict(rel)
                    rel_key = f"{rel.start_node.id}-{rel.end_node.id}-{rel.type}"
                    if rel_key not in relationships_seen:
                        relationships_seen.add(rel_key)
                        graph_data.append({"type": "relationship", "data": rel_data})
            
            return graph_data

# =============================================================================
# Document Processing Pipeline
# =============================================================================

class DocumentProcessor:
    def __init__(self, openai_inference: OpenAIInference, graph_manager: Neo4jGraphManager):
        self.openai = openai_inference
        self.graph_manager = graph_manager
        # Remove embedding model initialization
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP
        )
    
    def process_pdf(self, file_path: str) -> List[str]:
        """Extract text from PDF"""
        try:
            loader = PyPDFLoader(file_path)
            documents = loader.load()
            return [doc.page_content for doc in documents]
        except Exception as e:
            print(f"❌ Error processing PDF {file_path}: {e}")
            return []
    
    def process_excel(self, file_path: str) -> List[str]:
        """Process Excel file and convert to text chunks"""
        try:
            # Read all sheets
            excel_file = pd.ExcelFile(file_path)
            text_chunks = []
            
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                
                # Convert DataFrame to text representation
                sheet_text = f"Sheet: {sheet_name}\n\n"
                
                # Add column headers
                sheet_text += "Columns: " + ", ".join(df.columns.tolist()) + "\n\n"
                
                # Add data rows
                for idx, row in df.iterrows():
                    row_text = f"Row {idx + 1}: "
                    row_items = []
                    for col, value in row.items():
                        if pd.notna(value):
                            row_items.append(f"{col}: {str(value)}")
                    sheet_text += "; ".join(row_items) + "\n"
                
                text_chunks.append(sheet_text)
            
            return text_chunks
        except Exception as e:
            print(f"❌ Error processing Excel {file_path}: {e}")
            return []
    
    def process_file(self, file_path: str, file_id: str, filename: str, extraction_schema: Optional[Dict] = None) -> bool:
        """Main file processing pipeline"""
        try:
            # Determine file type and extract text
            file_extension = Path(filename).suffix.lower()
            
            if file_extension == '.pdf':
                text_pages = self.process_pdf(file_path)
                file_type = 'pdf'
            elif file_extension in ['.xlsx', '.xls']:
                text_pages = self.process_excel(file_path)
                file_type = 'excel'
            else:
                raise ValueError(f"Unsupported file type: {file_extension}")
            
            if not text_pages:
                raise ValueError("No text extracted from file")
            
            # Create document node
            metadata = {
                "file_type": file_type,
                "page_count": len(text_pages),
                "file_size": os.path.getsize(file_path)
            }
            
            self.graph_manager.create_document_node(file_id, filename, file_type, metadata)
            
            # Split text into chunks
            all_chunks = []
            for page_text in text_pages:
                page_chunks = self.text_splitter.split_text(page_text)
                all_chunks.extend(page_chunks)
            
            # Prepare chunk data (without embeddings)
            chunk_data = []
            for i, chunk_text in enumerate(all_chunks):
                chunk_data.append({
                    'text': chunk_text,
                    'token_count': len(chunk_text.split())
                })
            
            # Create chunk nodes
            chunk_ids = self.graph_manager.create_chunk_nodes(file_id, chunk_data)
            
            # Extract entities and relationships using OpenAI
            full_text = "\n\n".join(all_chunks[:5])  # Use first 5 chunks for entity extraction
            extracted_data = self.openai.extract_entities_relationships(full_text, extraction_schema)
            
            # Create entities and relationships in graph
            if extracted_data:
                self.graph_manager.create_entities_and_relationships(file_id, extracted_data)
            
            print(f"✅ Successfully processed {filename} with {len(chunk_ids)} chunks and {len(extracted_data.get('entities', []))} entities")
            return True
            
        except Exception as e:
            print(f"❌ Error processing file {filename}: {e}")
            return False

# =============================================================================
# GraphRAG Query Engine
# =============================================================================

class GraphRAGEngine:
    def __init__(self, openai_inference: OpenAIInference, graph_manager: Neo4jGraphManager):
        self.openai = openai_inference
        self.graph_manager = graph_manager
        # Remove embedding model - we'll use text search instead
    
    def query(self, query: str, max_context_tokens: int = 6000, max_hops: int = 3, similarity_threshold: float = 0.85) -> Dict[str, Any]:
        """Execute GraphRAG query using text search and entity extraction"""
        import time
        start_time = time.time()
        
        try:
            # 1. Use text-based search instead of vector search
            print(f"🔍 Searching for: {query}")
            similar_chunks = self.graph_manager.text_similarity_search(query, k=10)
            
            # Filter by similarity threshold (score from full-text search)
            filtered_chunks = [
                chunk for chunk in similar_chunks 
                if chunk['score'] >= similarity_threshold
            ]
            
            print(f"📊 Found {len(similar_chunks)} chunks, {len(filtered_chunks)} after filtering")
            
            # 2. Get entities related to the query using full-text search
            entity_search_results = self.graph_manager.search_entities_by_text(query)
            
            # 3. Graph traversal from found entities
            graph_context = []
            if entity_search_results:
                entity_ids = [entity['entity_name'] for entity in entity_search_results[:5]]
                if entity_ids:
                    graph_context = self.graph_manager.graph_traversal_search(entity_ids, max_hops)
            
            # 4. Assemble context with token budget management
            context_parts = []
            token_count = 0
            
            for chunk in filtered_chunks:
                chunk_tokens = len(chunk['text'].split())
                if token_count + chunk_tokens <= max_context_tokens:
                    context_parts.append(f"Source: {chunk['source_file']}\n{chunk['text']}")
                    token_count += chunk_tokens
                else:
                    break
            
            final_context = "\n\n---\n\n".join(context_parts)
            
            # 5. Generate answer using LLM
            if final_context.strip():
                rag_prompt = f"""
                You are a helpful assistant that answers questions based on the provided context.
                Use only the information from the context to answer the question.
                If the answer is not in the context, say "I don't have enough information to answer this question."
                
                Context:
                {final_context}
                
                Question: {query}
                
                Answer:"""
                
                answer = self.openai.generate(rag_prompt)
            else:
                answer = "I don't have enough information to answer this question. No relevant documents were found."
            
            # 6. Prepare response
            processing_time = time.time() - start_time
            
            return {
                "answer": answer,
                "sources": [{"file": chunk["source_file"], "score": chunk["score"]} for chunk in filtered_chunks],
                "graph_context": graph_context,
                "processing_time": processing_time,
                "context_token_count": token_count
            }
            
        except Exception as e:
            print(f"❌ Error executing GraphRAG query: {e}")
            return {
                "answer": f"Error processing query: {str(e)}",
                "sources": [],
                "graph_context": [],
                "processing_time": time.time() - start_time
            }

# =============================================================================
# FastAPI Application
# =============================================================================

# Global instances
openai_inference = None
graph_manager = None
document_processor = None
graphrag_engine = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan event handler"""
    # Startup
    global openai_inference, graph_manager, document_processor, graphrag_engine
    
    print("🚀 Starting Enhanced GraphRAG System...")
    
    # Initialize OpenAI
    openai_inference = OpenAIInference(config.OPENAI_API_KEY, config.OPENAI_MODEL, config.OLLAMA_LLM_FALLBACK_MODEL)
    
    # Initialize Neo4j
    graph_manager = Neo4jGraphManager()
    
    # Initialize processors
    document_processor = DocumentProcessor(openai_inference, graph_manager)
    graphrag_engine = GraphRAGEngine(openai_inference, graph_manager)
    
    print("✅ System initialized successfully!")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down Enhanced GraphRAG System...")
    if graph_manager:
        graph_manager.driver.close()
    print("✅ Shutdown complete!")

app = FastAPI(
    title="Enhanced GraphRAG System with OpenAI & Ollama", 
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/upload", response_model=FileUploadResponse)
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Upload and process a file"""
    
    # Validate file type
    if not file.filename.lower().endswith(('.pdf', '.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only PDF and Excel files are supported")
    
    # Generate unique file ID
    file_id = str(uuid.uuid4())
    
    # Save uploaded file
    upload_dir = Path("uploads")
    upload_dir.mkdir(exist_ok=True)
    file_path = upload_dir / f"{file_id}_{file.filename}"
    
    try:
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Schedule background processing
        background_tasks.add_task(
            document_processor.process_file,
            str(file_path),
            file_id,
            file.filename
        )
        
        return FileUploadResponse(
            file_id=file_id,
            filename=file.filename,
            status="processing",
            message="File uploaded and processing started"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")

@app.post("/extract", response_model=FileUploadResponse)
async def extract_graph(request: GraphExtractionRequest):
    """Extract graph from uploaded file with custom schema"""
    
    # This would trigger re-processing with custom schema
    # Implementation would depend on your specific requirements
    
    return FileUploadResponse(
        file_id=request.file_id,
        filename="",
        status="processing",
        message="Graph extraction started with custom schema"
    )

@app.post("/query", response_model=QueryResponse)
async def query_graph(request: QueryRequest):
    """Query the knowledge graph using GraphRAG"""
    
    try:
        result = graphrag_engine.query(
            query=request.query,
            max_context_tokens=request.max_context_tokens,
            max_hops=request.max_hops,
            similarity_threshold=request.similarity_threshold
        )
        
        return QueryResponse(
            answer=result["answer"],
            sources=result["sources"],
            graph_context=result["graph_context"],
            processing_time=result["processing_time"]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    fallback_status = "active" if openai_inference and openai_inference.use_fallback else "standby"
    active_model = config.OLLAMA_LLM_FALLBACK_MODEL if (openai_inference and openai_inference.use_fallback) else config.OPENAI_MODEL
    
    # Test Neo4j connection
    neo4j_connected = False
    if graph_manager:
        try:
            with graph_manager.driver.session(database=config.NEO4J_DATABASE) as session:
                session.run("RETURN 1 as test")
            neo4j_connected = True
        except Exception:
            neo4j_connected = False
    
    return {
        "status": "healthy",
        "active_llm_model": active_model,
        "openai_model": config.OPENAI_MODEL,
        "fallback_model": config.OLLAMA_LLM_FALLBACK_MODEL,
        "fallback_status": fallback_status,
        "processing_mode": "text_search_with_entities",
        "neo4j_connected": neo4j_connected
    }

# =============================================================================
# Cypher Query Templates
# =============================================================================

CYPHER_QUERIES = {
    "find_similar_entities": """
        MATCH (e1:Entity {name: $entity_name})
        MATCH (e2:Entity)
        WHERE e1 <> e2 AND e2.embedding IS NOT NULL AND e1.embedding IS NOT NULL
        WITH e1, e2, gds.similarity.cosine(e1.embedding, e2.embedding) AS similarity
        WHERE similarity > $threshold
        RETURN e2.name AS similar_entity, similarity
        ORDER BY similarity DESC
        LIMIT $limit
    """,
    
    "get_entity_neighborhood": """
        MATCH (e:Entity {name: $entity_name})
        CALL apoc.path.subgraphAll(e, {
            maxLevel: $max_hops,
            relationshipFilter: "RELATED"
        })
        YIELD nodes, relationships
        RETURN nodes, relationships
    """,
    
    "find_path_between_entities": """
        MATCH (start:Entity {name: $start_entity})
        MATCH (end:Entity {name: $end_entity})
        MATCH path = shortestPath((start)-[*..5]-(end))
        RETURN path
    """,
    
    "get_document_entities": """
        MATCH (d:Document {id: $document_id})
        MATCH (e:Entity {source_document: $document_id})
        RETURN e.name AS entity_name, e.label AS entity_type, e.description AS description
    """,
    
    "search_entities_by_text": """
        CALL db.index.fulltext.queryNodes("entity_search", $search_term)
        YIELD node, score
        RETURN node.name AS entity_name, node.description AS description, score
        ORDER BY score DESC
        LIMIT $limit
    """
}

@app.get("/cypher/templates")
async def get_cypher_templates():
    """Get available Cypher query templates"""
    return {
        "templates": list(CYPHER_QUERIES.keys()),
        "queries": CYPHER_QUERIES
    }

@app.post("/cypher/execute")
async def execute_cypher(query: str, parameters: Dict[str, Any] = None):
    """Execute custom Cypher query"""
    try:
        with graph_manager.driver.session(database=config.NEO4J_DATABASE) as session:
            result = session.run(query, parameters or {})
            return {"result": [record.data() for record in result]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cypher execution error: {str(e)}")

# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    # Create necessary directories
    Path("uploads").mkdir(exist_ok=True)
    Path("models").mkdir(exist_ok=True)
    
    print("🚀 Starting Enhanced GraphRAG System with OpenAI and Ollama...")
    print(f"📊 Neo4j URI: {config.NEO4J_URI}")
    print(f"🤖 Primary LLM: {config.OPENAI_MODEL}")
    print(f"🔄 Fallback LLM: {config.OLLAMA_LLM_FALLBACK_MODEL}")
    print(f"📡 Embedding Model: {config.OLLAMA_EMBEDDING_MODEL}")
    print("🌐 Starting web server on http://0.0.0.0:8000")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)