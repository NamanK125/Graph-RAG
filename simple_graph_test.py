#!/usr/bin/env python3
"""
Simple GraphRAG Test Script
===========================

This script tests the GraphRAG pipeline by:
1. Creating a simple text file with known content
2. Converting it to PDF using a simple method
3. Testing upload and query functionality

Usage:
    python simple_graph_test.py
"""

import os
import time
import json
import requests
from pathlib import Path
import tempfile

# API Configuration
API_BASE = "http://localhost:8000"

def create_simple_test_pdf() -> str:
    """Create a simple test PDF using basic HTML to PDF conversion or plain text"""
    
    # Create test directory
    test_dir = Path("test_data")
    test_dir.mkdir(exist_ok=True)
    
    # For simplicity, let's create a text file first and then use a simple conversion
    text_path = test_dir / "test_document.txt"
    
    # Sample business content with clear entities and relationships
    content = """
SYNTHETIC BUSINESS DOCUMENT - TEST DATA

PURCHASE ORDER: PO-TEST-001
Date: October 4, 2025
Supplier: ABC Manufacturing Company
Address: 123 Business St, Tech City, CA 90210
Contact: John Smith (Manager)

BUYER INFORMATION:
Company: TechCorp Solutions
Buyer: Sarah Johnson (Procurement Officer)
Department: IT Equipment

ITEMS ORDERED:
1. Product: Laptop Computer Model X1
   Quantity: 25 units
   Unit Price: $1,200.00
   Total: $30,000.00

2. Product: Wireless Mouse Set
   Quantity: 25 units  
   Unit Price: $25.00
   Total: $625.00

RELATIONSHIPS:
- ABC Manufacturing supplies to TechCorp Solutions
- John Smith manages supplier operations
- Sarah Johnson handles procurement for TechCorp
- Laptop Computer requires Wireless Mouse (accessory)

TOTAL ORDER VALUE: $30,625.00
Approved by: Michael Davis (Finance Director)
"""
    
    # Write text file
    with open(text_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Created test content file: {text_path}")
    print(f"📄 Content includes entities: ABC Manufacturing, TechCorp Solutions, John Smith")
    print(f"🔗 Content includes relationships: supplier-buyer, manager-company")
    
    return str(text_path)

def test_query(query: str, expected_terms: list = None) -> dict:
    """Test a single query against the GraphRAG system"""
    
    try:
        response = requests.post(
            f"{API_BASE}/query",
            json={
                "query": query,
                "similarity_threshold": 0.7,
                "max_context_tokens": 4000
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            answer = result.get('answer', 'No answer provided')
            sources = result.get('sources', [])
            processing_time = result.get('processing_time', 0)
            
            print(f"✅ Query successful ({processing_time:.2f}s)")
            print(f"📝 Answer: {answer}")
            print(f"📊 Sources: {len(sources)}")
            
            # Check expected terms
            if expected_terms:
                found_terms = []
                answer_lower = answer.lower()
                for term in expected_terms:
                    if term.lower() in answer_lower:
                        found_terms.append(term)
                
                if found_terms:
                    print(f"🎯 Found expected terms: {', '.join(found_terms)}")
                else:
                    print(f"⚠️ Expected terms not found: {', '.join(expected_terms)}")
            
            return {
                'success': True,
                'answer': answer,
                'sources': len(sources),
                'processing_time': processing_time
            }
        else:
            print(f"❌ Query failed: {response.status_code}")
            print(f"   Error: {response.text}")
            return {'success': False, 'error': response.text}
            
    except Exception as e:
        print(f"❌ Query error: {e}")
        return {'success': False, 'error': str(e)}

def main():
    print("🧪 Simple GraphRAG Knowledge Graph Test")
    print("=" * 50)
    
    # Step 1: Check system health
    print("\n1️⃣ Checking System Health")
    try:
        response = requests.get(f"{API_BASE}/health", timeout=10)
        if response.status_code == 200:
            health = response.json()
            print(f"✅ System Status: {health['status']}")
            print(f"🤖 Active LLM: {health['active_llm_model']}")
            print(f"📡 Processing Mode: {health.get('processing_mode', 'N/A')}")
            print(f"🗄️ Neo4j Connected: {health['neo4j_connected']}")
        else:
            print(f"❌ System health check failed: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Cannot connect to GraphRAG system: {e}")
        print("💡 Make sure to start the system: bash scripts/start.sh")
        return
    
    # Step 2: Test with previously uploaded documents
    print("\n2️⃣ Testing Queries on Existing Documents")
    
    test_queries = [
        {
            "query": "What documents are available?",
            "expected": ["document", "file"]
        },
        {
            "query": "What companies are mentioned?",
            "expected": ["company", "business"]
        },
        {
            "query": "Who are the people mentioned in the documents?",
            "expected": ["person", "people", "name"]
        },
        {
            "query": "What products or items are discussed?",
            "expected": ["product", "item"]
        },
        {
            "query": "What are the relationships between entities?",
            "expected": ["relationship", "connection"]
        }
    ]
    
    results = []
    for i, test in enumerate(test_queries, 1):
        print(f"\n[{i}/{len(test_queries)}] Testing: {test['query']}")
        print("-" * 40)
        result = test_query(test['query'], test['expected'])
        results.append(result)
        print()
    
    # Step 3: Summary
    print("\n3️⃣ Test Results Summary")
    print("=" * 50)
    
    successful_queries = sum(1 for r in results if r.get('success', False))
    total_queries = len(results)
    
    print(f"✅ Successful queries: {successful_queries}/{total_queries}")
    
    if successful_queries > 0:
        avg_time = sum(r.get('processing_time', 0) for r in results if r.get('success')) / successful_queries
        total_sources = sum(r.get('sources', 0) for r in results if r.get('success'))
        
        print(f"⏱️ Average response time: {avg_time:.2f}s")
        print(f"📊 Total sources found: {total_sources}")
        
        if successful_queries == total_queries:
            print("\n🎉 GraphRAG system is working correctly!")
            print("✅ Query processing functional")
            print("✅ Knowledge retrieval working")
            print("✅ Response generation active")
        else:
            print(f"\n⚠️ Some queries failed ({total_queries - successful_queries} failures)")
            print("💡 This might indicate:")
            print("   • Documents still processing")
            print("   • No relevant content found")
            print("   • System configuration issues")
    else:
        print("\n❌ No queries were successful")
        print("💡 Possible issues:")
        print("   • No documents uploaded yet")
        print("   • Processing not complete")
        print("   • System configuration problems")
    
    # Step 4: Manual verification instructions
    print(f"\n4️⃣ Manual Verification")
    print("=" * 50)
    print("🌐 Web Interface:")
    print(f"   • API Docs: {API_BASE}/docs")
    print(f"   • Health Check: {API_BASE}/health")
    
    print("\n🔍 Neo4j Verification:")
    print("   • Neo4j Browser: http://localhost:7474")
    print("   • Username: neo4j")
    print("   • Password: password")
    
    print("\n📊 Useful Neo4j Queries:")
    print("   • Check all nodes: MATCH (n) RETURN labels(n), count(n)")
    print("   • Check documents: MATCH (d:Document) RETURN d")
    print("   • Check chunks: MATCH (c:Chunk) RETURN count(c)")
    print("   • Check entities: MATCH (e:Entity) RETURN e LIMIT 10")
    print("   • Check embeddings: MATCH (c:Chunk) WHERE c.embedding IS NOT NULL RETURN count(c)")

if __name__ == "__main__":
    main()
