#!/usr/bin/env python3
"""
Complete example: Upload data and query GraphRAG system
"""

import requests
import json
import time
from pathlib import Path

def upload_and_query_example():
    """Complete example of uploading data and querying"""
    
    BASE_URL = "http://localhost:8000"
    
    print("🧪 GraphRAG Data Upload and Query Example")
    print("=" * 50)
    
    # 1. Check system health
    print("\n1️⃣ Checking system health...")
    health_response = requests.get(f"{BASE_URL}/health")
    if health_response.status_code == 200:
        health_data = health_response.json()
        print(f"✅ System healthy: {health_data['status']}")
        print(f"🤖 Active LLM: {health_data['active_llm_model']}")
        print(f"📡 Embedding model: {health_data['embedding_model']}")
        print(f"🗄️ Neo4j connected: {health_data['neo4j_connected']}")
    else:
        print("❌ System not healthy. Make sure to run 'bash scripts/start.sh' first")
        return
    
    # 2. Upload a sample file
    print("\n2️⃣ Uploading sample file...")
    sample_file = Path("examples/sample_data/research_paper.pdf")
    
    if sample_file.exists():
        with open(sample_file, 'rb') as f:
            files = {'file': (sample_file.name, f, 'application/pdf')}
            upload_response = requests.post(f"{BASE_URL}/upload", files=files)
        
        if upload_response.status_code == 200:
            upload_data = upload_response.json()
            print(f"✅ File uploaded: {upload_data['filename']}")
            print(f"📋 File ID: {upload_data['file_id']}")
            print(f"📊 Status: {upload_data['status']}")
        else:
            print(f"❌ Upload failed: {upload_response.text}")
            return
    else:
        print(f"⚠️ Sample file not found: {sample_file}")
        print("📁 You can place your own PDF or Excel files in the examples/sample_data/ directory")
        return
    
    # 3. Wait for processing
    print("\n3️⃣ Waiting for file processing...")
    print("⏳ This may take a minute for entity extraction and embedding creation...")
    time.sleep(10)  # Give time for background processing
    
    # 4. Query the knowledge graph
    print("\n4️⃣ Querying the knowledge graph...")
    
    queries = [
        "What is this document about?",
        "What are the main entities mentioned?",
        "Summarize the key findings",
    ]
    
    for query in queries:
        print(f"\n❓ Query: {query}")
        
        query_data = {
            "query": query,
            "max_context_tokens": 3000,
            "similarity_threshold": 0.75
        }
        
        query_response = requests.post(f"{BASE_URL}/query", json=query_data)
        
        if query_response.status_code == 200:
            result = query_response.json()
            print(f"💬 Answer: {result['answer'][:200]}...")
            print(f"📚 Sources: {len(result['sources'])} documents")
            print(f"⏱️ Processing time: {result['processing_time']:.2f}s")
        else:
            print(f"❌ Query failed: {query_response.text}")
    
    print(f"\n🎉 Example completed!")
    print(f"\n📋 Summary:")
    print(f"  • Upload files via: POST {BASE_URL}/upload")
    print(f"  • Query graph via: POST {BASE_URL}/query")
    print(f"  • View API docs: {BASE_URL}/docs")

if __name__ == "__main__":
    upload_and_query_example()
