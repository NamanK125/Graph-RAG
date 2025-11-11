#!/usr/bin/env python3
"""
Configuration-based Document Upload Script
==========================================

This script reads document paths from upload_config.txt and uploads them
to your GraphRAG system. Simply edit the config file with your document
locations and run this script.

Usage:
    python config_upload.py
    python config_upload.py --config custom_config.txt
"""

import os
import sys
import argparse
from pathlib import Path

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from upload_documents import DocumentUploader, SUPPORTED_EXTENSIONS

def read_config_file(config_path: str) -> list:
    """Read document paths from configuration file"""
    try:
        with open(config_path, 'r') as f:
            lines = f.readlines()
        
        paths = []
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            paths.append(line)
        
        return paths
    
    except FileNotFoundError:
        print(f"❌ Config file not found: {config_path}")
        print(f"💡 Create the file with your document paths, one per line")
        return []
    except Exception as e:
        print(f"❌ Error reading config file: {e}")
        return []

def config_upload():
    """Upload documents based on configuration file"""
    
    parser = argparse.ArgumentParser(description="Upload documents using configuration file")
    parser.add_argument('--config', default='upload_config.txt', 
                       help='Configuration file with document paths')
    args = parser.parse_args()
    
    print("📋 Configuration-based Document Upload")
    print("=" * 40)
    
    # Read configuration
    config_path = args.config
    print(f"📄 Reading config: {config_path}")
    
    paths = read_config_file(config_path)
    
    if not paths:
        print(f"\n⚠️ No paths found in configuration file")
        print(f"💡 Edit {config_path} and add your document paths")
        print(f"📝 Example:")
        print(f"   /path/to/your/documents/")
        print(f"   /path/to/specific/file.pdf")
        return
    
    print(f"✅ Found {len(paths)} paths in configuration:")
    for i, path in enumerate(paths, 1):
        print(f"   {i}. {path}")
    
    # Initialize uploader
    uploader = DocumentUploader()
    
    # Check system
    print(f"\n🔍 Checking GraphRAG system...")
    if not uploader.check_system_health():
        print(f"\n💡 To start the system, run: bash scripts/start.sh")
        return
    
    # Collect files
    print(f"\n📁 Scanning for supported files...")
    files = uploader.collect_files(paths, recursive=True)
    
    if not files:
        print(f"\n⚠️ No supported files found in configured paths!")
        print(f"📄 Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}")
        print(f"💡 Check your paths in {config_path}")
        return
    
    # Upload files
    print(f"\n🚀 Uploading {len(files)} files...")
    uploader.upload_batch(files, delay=0.5)
    
    # Show results
    if uploader.uploaded_files:
        print(f"\n🎯 Upload completed! Your documents are being processed.")
        print(f"💡 You can now query them through the GraphRAG API")

if __name__ == "__main__":
    try:
        config_upload()
    except KeyboardInterrupt:
        print(f"\n\n❌ Upload cancelled by user.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
