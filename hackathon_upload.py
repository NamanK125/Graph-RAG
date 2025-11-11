#!/usr/bin/env python3
"""
Hackathon Files Upload Script
============================

This script uploads all files from your Hackathon folder to create embeddings
and build a comprehensive knowledge graph for your business data.

Found structure:
- GRN Copies (Goods Receipt Notes)
- Purchase Invoices
- Purchase Orders  
- Sales Invoices
- Inventory Register
- Process Documentation
"""

import os
import sys
from pathlib import Path
import time

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from upload_documents import DocumentUploader, SUPPORTED_EXTENSIONS

def upload_hackathon_files():
    """Upload all hackathon files with organized processing"""
    
    print("🏆 Hackathon Files - GraphRAG Upload")
    print("=" * 50)
    
    hackathon_path = Path("Hackathon")
    
    if not hackathon_path.exists():
        print(f"❌ Hackathon folder not found at: {hackathon_path}")
        print(f"💡 Make sure you're running from the correct directory")
        return
    
    # Initialize uploader
    uploader = DocumentUploader()
    
    # Check system health
    print("🔍 Checking GraphRAG system...")
    if not uploader.check_system_health():
        print(f"\n💡 Please start the GraphRAG system first:")
        print(f"   bash scripts/start.sh")
        return
    
    # Collect all files from Hackathon folder
    print(f"\n📁 Scanning Hackathon folder...")
    hackathon_files = uploader.collect_files([str(hackathon_path)], recursive=True)
    
    if not hackathon_files:
        print(f"⚠️ No supported files found in Hackathon folder")
        print(f"📄 Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}")
        return
    
    # Organize files by type for better visibility
    file_types = {}
    for file_path in hackathon_files:
        category = "Other"
        path_str = str(file_path)
        
        if "GRN" in path_str:
            category = "GRN (Goods Receipt Notes)"
        elif "Purchase Invoice" in path_str:
            category = "Purchase Invoices"
        elif "Purchase Order" in path_str:
            category = "Purchase Orders"
        elif "Sales Invoice" in path_str:
            category = "Sales Invoices"
        elif "Inventory" in path_str:
            category = "Inventory Register"
        elif "Output" in path_str:
            category = "Process Documentation"
        
        if category not in file_types:
            file_types[category] = []
        file_types[category].append(file_path)
    
    # Display summary
    print(f"\n📊 Found {len(hackathon_files)} files across categories:")
    total_count = 0
    for category, files in file_types.items():
        print(f"   📂 {category}: {len(files)} files")
        total_count += len(files)
    
    print(f"\n💼 Business Document Types:")
    print(f"   • Financial records (invoices, orders)")
    print(f"   • Inventory management data")
    print(f"   • Goods receipt documentation")
    print(f"   • Process workflows")
    
    # Confirm upload
    print(f"\n❓ This will create embeddings and knowledge graph from {total_count} business documents.")
    print(f"⏱️ Estimated processing time: {total_count * 2} minutes (2 min per file average)")
    
    confirm = input(f"\n🚀 Proceed with upload? (y/N): ").strip().lower()
    if confirm not in ['y', 'yes']:
        print("❌ Upload cancelled.")
        return
    
    # Upload files with category organization
    print(f"\n🏗️ Starting comprehensive upload...")
    print(f"📈 This will enable:")
    print(f"   • Cross-document search and analysis")
    print(f"   • Business process mapping")
    print(f"   • Financial data correlation")
    print(f"   • Inventory tracking insights")
    print("=" * 50)
    
    # Upload with minimal delay for efficiency
    uploader.upload_batch(hackathon_files, delay=0.3)
    
    # Show specialized summary for business use case
    if uploader.uploaded_files:
        print(f"\n🎯 Hackathon Knowledge Graph Ready!")
        print(f"=" * 50)
        print(f"✅ Uploaded: {len(uploader.uploaded_files)} business documents")
        print(f"🧠 Embeddings created for cross-document analysis")
        print(f"📊 Neo4j graph database populated")
        
        print(f"\n💡 What you can now do:")
        print(f"   🔍 Query: 'What are the main suppliers in my purchase orders?'")
        print(f"   📈 Analyze: 'Show relationships between GRNs and invoices'")
        print(f"   💰 Track: 'What items have inventory discrepancies?'")
        print(f"   📋 Process: 'Map the purchase-to-payment workflow'")
        
        print(f"\n🌐 Access your business intelligence:")
        print(f"   • API Documentation: http://localhost:8000/docs")
        print(f"   • Query endpoint: POST http://localhost:8000/query")
        print(f"   • Health check: http://localhost:8000/health")
        
        print(f"\n🔬 Test queries with:")
        print(f"   python example_upload_query.py")
        
        if len(uploader.failed_files) > 0:
            print(f"\n⚠️ Note: {len(uploader.failed_files)} files failed to upload")
            print(f"💡 Check file formats and try individual uploads if needed")

if __name__ == "__main__":
    try:
        upload_hackathon_files()
    except KeyboardInterrupt:
        print(f"\n\n❌ Upload cancelled by user.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print(f"💡 Try running: python upload_documents.py Hackathon/ --recursive")
