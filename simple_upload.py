#!/usr/bin/env python3
"""
Simple Document Upload Script
============================

Quick and easy document upload to GraphRAG system.
Just specify the paths to your documents or folders.

Usage:
    python simple_upload.py /path/to/your/documents/
    python simple_upload.py document1.pdf document2.xlsx
"""

import os
import sys
from pathlib import Path

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the main uploader
from upload_documents import DocumentUploader, SUPPORTED_EXTENSIONS

def simple_upload():
    """Simple upload interface"""
    
    print("📁 Simple Document Upload for GraphRAG")
    print("=" * 40)
    
    # Get paths from command line or prompt user
    if len(sys.argv) > 1:
        paths = sys.argv[1:]
        print(f"📍 Using paths from command line: {len(paths)} items")
    else:
        print("📝 Enter document paths or folders (one per line, empty line to finish):")
        paths = []
        while True:
            path = input("Path: ").strip()
            if not path:
                break
            paths.append(path)
        
        if not paths:
            print("❌ No paths provided. Exiting.")
            return
    
    print(f"\n📊 Processing {len(paths)} path(s)...")
    
    # Initialize uploader
    uploader = DocumentUploader()
    
    # Check system
    print("\n🔍 Checking GraphRAG system...")
    if not uploader.check_system_health():
        print("\n💡 To start the system, run: bash scripts/start.sh")
        return
    
    # Collect files (automatically recursive for directories)
    files = uploader.collect_files(paths, recursive=True)
    
    if not files:
        print(f"\n⚠️ No supported files found!")
        print(f"📄 Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}")
        return
    
    # Show files to be uploaded
    print(f"\n📋 Found {len(files)} files to upload:")
    for i, file_path in enumerate(files, 1):
        print(f"   {i}. {file_path.name} ({file_path.suffix})")
    
    # Confirm upload
    confirm = input(f"\n❓ Upload these {len(files)} files? (y/N): ").strip().lower()
    if confirm not in ['y', 'yes']:
        print("❌ Upload cancelled.")
        return
    
    # Upload with minimal delay
    print(f"\n🚀 Starting upload...")
    uploader.upload_batch(files, delay=0.5)
    
    # Show next steps
    if uploader.uploaded_files:
        print(f"\n🎯 Next Steps:")
        print(f"   • Query your documents: http://localhost:8000/docs")
        print(f"   • Test with: python example_upload_query.py")
        print(f"   • View API docs: http://localhost:8000/docs")

if __name__ == "__main__":
    try:
        simple_upload()
    except KeyboardInterrupt:
        print(f"\n\n❌ Upload cancelled by user.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
