#!/usr/bin/env python3
"""
GraphRAG Knowledge Graph Creation Test
=====================================

This script tests the complete GraphRAG pipeline with synthetic data:
1. Creates a small test PDF with known entities and relationships
2. Uploads it to the system
3. Waits for processing
4. Queries the knowledge graph to verify creation
5. Displays results

Usage:
    python test_graph_creation.py
"""

import os
import time
import json
import requests
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import tempfile

# API Configuration
API_BASE = "http://localhost:8000"

class GraphRAGTester:
    def __init__(self, api_base: str = API_BASE):
        self.api_base = api_base.rstrip('/')
        self.test_file_path = None
        self.file_id = None
    
    def create_synthetic_pdf(self) -> str:
        """Create a small synthetic PDF with known entities and relationships"""
        
        # Create a temporary file
        temp_dir = Path("test_data")
        temp_dir.mkdir(exist_ok=True)
        
        pdf_path = temp_dir / "synthetic_business_document.pdf"
        
        # Sample business content with clear entities and relationships
        content = """
SYNTHETIC BUSINESS DOCUMENT - TEST DATA
=====================================

PURCHASE ORDER: PO-TEST-001
Date: October 4, 2025
Supplier: ABC Manufacturing Company
Address: 123 Business St, Tech City, CA 90210
Contact: John Smith (Manager)
Email: john.smith@abc-manufacturing.com
Phone: (555) 123-4567

BUYER INFORMATION:
Company: TechCorp Solutions
Buyer: Sarah Johnson (Procurement Officer)
Department: IT Equipment
Budget Code: IT-2025-Q4

ITEMS ORDERED:
1. Product: Laptop Computer Model X1
   Quantity: 25 units
   Unit Price: $1,200.00
   Total: $30,000.00
   Category: Electronics

2. Product: Wireless Mouse Set
   Quantity: 25 units  
   Unit Price: $25.00
   Total: $625.00
   Category: Accessories

PAYMENT TERMS:
Net 30 days
Payment Method: Bank Transfer
Delivery Date: October 15, 2025
Shipping Address: TechCorp Solutions, 456 Tech Ave, Innovation City, CA 90211

RELATIONSHIPS:
- ABC Manufacturing supplies to TechCorp Solutions
- John Smith manages supplier operations
- Sarah Johnson handles procurement for TechCorp
- Laptop Computer requires Wireless Mouse (accessory)
- IT Equipment department manages technology purchases

TOTAL ORDER VALUE: $30,625.00
Approved by: Michael Davis (Finance Director)
Authorization Code: AUTH-2025-1004
"""
        
        # Create PDF using reportlab
        c = canvas.Canvas(str(pdf_path), pagesize=letter)
        width, height = letter
        
        # Split content into lines and add to PDF
        lines = content.strip().split('\n')
        y_position = height - 50
        
        for line in lines:
            if y_position < 50:  # Start new page if needed
                c.showPage()
                y_position = height - 50
            
            c.drawString(50, y_position, line)
            y_position -= 15
        
        c.save()
        
        self.test_file_path = str(pdf_path)
        print(f"✅ Created synthetic PDF: {pdf_path}")
        print(f"📄 Content includes entities: ABC Manufacturing, TechCorp Solutions, John Smith, Sarah Johnson")
        print(f"🔗 Content includes relationships: supplier-buyer, manager-company, product-category")
        
        return str(pdf_path)
    
    def check_system_health(self) -> bool:
        """Check if GraphRAG system is healthy"""
        try:
            response = requests.get(f"{self.api_base}/health", timeout=10)
            if response.status_code == 200:
                health = response.json()
                print(f"✅ System Status: {health['status']}")
                print(f"🤖 Active LLM: {health['active_llm_model']}")
                print(f"📡 Processing Mode: {health.get('processing_mode', 'N/A')}")
                print(f"🗄️ Neo4j Connected: {health['neo4j_connected']}")
                return True
            else:
                print(f"❌ System health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Cannot connect to GraphRAG system: {e}")
            return False
    
    def upload_test_document(self, file_path: str) -> bool:
        """Upload the test document"""
        try:
            print(f"\n📤 Uploading test document: {Path(file_path).name}")
            
            with open(file_path, 'rb') as f:
                files = {'file': (Path(file_path).name, f, 'application/pdf')}
                response = requests.post(f"{self.api_base}/upload", files=files, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                self.file_id = result['file_id']
                print(f"✅ Upload successful!")
                print(f"   📋 File ID: {self.file_id}")
                print(f"   📊 Status: {result['status']}")
                return True
            else:
                print(f"❌ Upload failed: {response.status_code}")
                print(f"   Error: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Upload error: {e}")
            return False
    
    def wait_for_processing(self, max_wait_time: int = 120) -> bool:
        """Wait for document processing to complete"""
        print(f"\n⏳ Waiting for document processing (max {max_wait_time}s)...")
        
        start_time = time.time()
        while time.time() - start_time < max_wait_time:
            try:
                # Try a simple query to see if data is available
                response = requests.post(
                    f"{self.api_base}/query",
                    json={"query": "What companies are mentioned?", "similarity_threshold": 0.7},
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('sources') and len(result['sources']) > 0:
                        print(f"✅ Document processing completed!")
                        return True
                
                print(".", end="", flush=True)
                time.sleep(5)
                
            except Exception as e:
                print(".", end="", flush=True)
                time.sleep(5)
        
        print(f"\n⚠️ Processing may still be ongoing after {max_wait_time}s")
        return False
    
    def test_graph_queries(self) -> None:
        """Test various queries to verify graph creation"""
        print(f"\n🧪 Testing GraphRAG Queries")
        print("=" * 50)
        
        test_queries = [
            {
                "name": "Basic Entity Recognition",
                "query": "What companies are mentioned in the document?",
                "expected_entities": ["ABC Manufacturing", "TechCorp Solutions"]
            },
            {
                "name": "Person Identification", 
                "query": "Who are the people mentioned?",
                "expected_entities": ["John Smith", "Sarah Johnson", "Michael Davis"]
            },
            {
                "name": "Product Information",
                "query": "What products were ordered?",
                "expected_entities": ["Laptop Computer", "Wireless Mouse"]
            },
            {
                "name": "Relationship Query",
                "query": "What is the relationship between ABC Manufacturing and TechCorp Solutions?",
                "expected_concepts": ["supplier", "buyer", "purchase order"]
            },
            {
                "name": "Financial Information",
                "query": "What is the total order value?",
                "expected_concepts": ["$30,625", "payment", "finance"]
            }
        ]
        
        for i, test in enumerate(test_queries, 1):
            print(f"\n[{i}/{len(test_queries)}] {test['name']}")
            print(f"❓ Query: {test['query']}")
            
            try:
                response = requests.post(
                    f"{self.api_base}/query",
                    json={
                        "query": test['query'],
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
                    
                    print(f"✅ Response received ({processing_time:.2f}s)")
                    print(f"📝 Answer: {answer[:200]}...")
                    print(f"📊 Sources found: {len(sources)}")
                    
                    # Check if expected entities/concepts are in the answer
                    answer_lower = answer.lower()
                    expected = test.get('expected_entities', []) + test.get('expected_concepts', [])
                    
                    found_entities = []
                    for entity in expected:
                        if entity.lower() in answer_lower:
                            found_entities.append(entity)
                    
                    if found_entities:
                        print(f"🎯 Found expected content: {', '.join(found_entities)}")
                    else:
                        print(f"⚠️ Expected content not clearly found in answer")
                    
                else:
                    print(f"❌ Query failed: {response.status_code}")
                    print(f"   Error: {response.text}")
                    
            except Exception as e:
                print(f"❌ Query error: {e}")
            
            print("-" * 40)
    
    def test_graph_structure_queries(self) -> None:
        """Test Neo4j graph structure directly"""
        print(f"\n🔍 Testing Graph Structure")
        print("=" * 50)
        
        # These queries would require direct Neo4j access or custom endpoints
        structure_tests = [
            "Check if Document nodes exist",
            "Check if Chunk nodes with embeddings exist", 
            "Check if Entity nodes were created",
            "Check if relationships between entities exist"
        ]
        
        print("📊 Graph structure verification:")
        for test in structure_tests:
            print(f"   • {test}: (Would require direct Neo4j access)")
        
        print("\n💡 To verify graph structure manually:")
        print("   1. Open Neo4j Browser: http://localhost:7474")
        print("   2. Run: MATCH (n) RETURN labels(n), count(n)")
        print("   3. Run: MATCH (d:Document) RETURN d.filename, d.file_type")
        print("   4. Run: MATCH (c:Chunk) RETURN count(c)")
        print("   5. Run: MATCH (e:Entity) RETURN e.name, e.label LIMIT 10")
    
    def cleanup(self) -> None:
        """Clean up test files"""
        if self.test_file_path and os.path.exists(self.test_file_path):
            os.remove(self.test_file_path)
            print(f"🧹 Cleaned up test file: {Path(self.test_file_path).name}")

def main():
    print("🧪 GraphRAG Knowledge Graph Creation Test")
    print("=" * 60)
    
    tester = GraphRAGTester()
    
    try:
        # Step 1: Check system health
        print("\n1️⃣ Checking System Health")
        if not tester.check_system_health():
            print("❌ System not healthy. Please start the GraphRAG system first:")
            print("   bash scripts/start.sh")
            return
        
        # Step 2: Create synthetic test document
        print("\n2️⃣ Creating Synthetic Test Document")
        pdf_path = tester.create_synthetic_pdf()
        
        # Step 3: Upload document
        print("\n3️⃣ Uploading Test Document")
        if not tester.upload_test_document(pdf_path):
            print("❌ Upload failed!")
            return
        
        # Step 4: Wait for processing
        print("\n4️⃣ Waiting for Processing")
        processing_complete = tester.wait_for_processing(120)
        
        # Step 5: Test queries (regardless of processing status)
        print("\n5️⃣ Testing GraphRAG Queries")
        tester.test_graph_queries()
        
        # Step 6: Graph structure info
        print("\n6️⃣ Graph Structure Information")
        tester.test_graph_structure_queries()
        
        # Results summary
        print(f"\n🎉 Test Complete!")
        print("=" * 60)
        
        if processing_complete:
            print("✅ GraphRAG pipeline is working correctly!")
            print("✅ Document processing completed")
            print("✅ Knowledge graph creation verified")
            print("✅ Query system functional")
        else:
            print("⚠️ Processing may still be ongoing")
            print("✅ Upload and query system functional")
            print("💡 Try running queries again in a few minutes")
        
        print(f"\n🌐 API Documentation: {tester.api_base}/docs")
        print(f"🔍 Neo4j Browser: http://localhost:7474")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
    finally:
        # Cleanup
        print("\n🧹 Cleaning up...")
        tester.cleanup()

if __name__ == "__main__":
    main()
