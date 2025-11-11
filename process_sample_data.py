#!/usr/bin/env python3
"""
Process sample data files for GraphRAG
"""

import os
import sys
from pathlib import Path
import uuid

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import DocumentProcessor, OpenAIInference, Neo4jGraphManager, Config

def process_sample_files():
    """Process all files in the sample_data directory"""
    
    print("🔄 Processing Sample Data Files")
    print("=" * 40)
    
    # Initialize components
    config = Config()
    openai_inference = OpenAIInference(config.OPENAI_API_KEY, config.OPENAI_MODEL, config.OLLAMA_LLM_FALLBACK_MODEL)
    graph_manager = Neo4jGraphManager()
    document_processor = DocumentProcessor(openai_inference, graph_manager)
    
    # Sample data directory
    sample_data_dir = Path("examples/sample_data")
    
    if not sample_data_dir.exists():
        print(f"❌ Sample data directory not found: {sample_data_dir}")
        return
    
    # Process each file
    for file_path in sample_data_dir.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in ['.pdf', '.xlsx', '.xls']:
            print(f"\n📄 Processing: {file_path.name}")
            
            # Generate unique file ID
            file_id = str(uuid.uuid4())
            
            # Process the file
            success = document_processor.process_file(
                str(file_path),
                file_id,
                file_path.name
            )
            
            if success:
                print(f"✅ Successfully processed {file_path.name}")
            else:
                print(f"❌ Failed to process {file_path.name}")
    
    print(f"\n🎉 Sample data processing completed!")

if __name__ == "__main__":
    process_sample_files()
