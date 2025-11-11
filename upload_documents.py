#!/usr/bin/env python3
"""
Document Upload Script for GraphRAG System
==========================================

This script allows you to easily upload documents to your GraphRAG system
by simply specifying the file paths or directories containing your documents.

Usage Examples:
    python upload_documents.py /path/to/document.pdf
    python upload_documents.py /path/to/folder/
    python upload_documents.py /path/to/doc1.pdf /path/to/doc2.xlsx /path/to/folder/
    python upload_documents.py --recursive /path/to/main/folder/
"""

import os
import sys
import argparse
import requests
import json
import time
from pathlib import Path
from typing import List, Optional
import uuid

# Supported file extensions
SUPPORTED_EXTENSIONS = {'.pdf', '.xlsx', '.xls'}

# Default GraphRAG API endpoint
DEFAULT_API_BASE = "http://localhost:8000"

class DocumentUploader:
    def __init__(self, api_base: str = DEFAULT_API_BASE):
        self.api_base = api_base.rstrip('/')
        self.uploaded_files = []
        self.failed_files = []
    
    def check_system_health(self) -> bool:
        """Check if the GraphRAG system is running and healthy"""
        try:
            response = requests.get(f"{self.api_base}/health", timeout=5)
            if response.status_code == 200:
                health_data = response.json()
                print(f"✅ System Status: {health_data['status']}")
                print(f"🤖 Active LLM: {health_data['active_llm_model']}")
                print(f"📡 Embedding Model: {health_data['embedding_model']}")
                print(f"🗄️ Neo4j Connected: {health_data['neo4j_connected']}")
                return True
            else:
                print(f"❌ System health check failed: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"❌ Cannot connect to GraphRAG system: {e}")
            print(f"💡 Make sure to start the system first: bash scripts/start.sh")
            return False
    
    def is_supported_file(self, file_path: Path) -> bool:
        """Check if file type is supported"""
        return file_path.suffix.lower() in SUPPORTED_EXTENSIONS
    
    def collect_files(self, paths: List[str], recursive: bool = False) -> List[Path]:
        """Collect all supported files from given paths"""
        files_to_upload = []
        
        for path_str in paths:
            path = Path(path_str).expanduser().resolve()
            
            if not path.exists():
                print(f"⚠️ Path does not exist: {path}")
                continue
            
            if path.is_file():
                if self.is_supported_file(path):
                    files_to_upload.append(path)
                else:
                    print(f"⚠️ Unsupported file type: {path}")
            
            elif path.is_dir():
                print(f"📁 Scanning directory: {path}")
                pattern = "**/*" if recursive else "*"
                
                for file_path in path.glob(pattern):
                    if file_path.is_file() and self.is_supported_file(file_path):
                        files_to_upload.append(file_path)
        
        # Remove duplicates
        files_to_upload = list(set(files_to_upload))
        return files_to_upload
    
    def upload_file(self, file_path: Path) -> bool:
        """Upload a single file to the GraphRAG system"""
        try:
            print(f"📤 Uploading: {file_path.name}")
            
            with open(file_path, 'rb') as f:
                files = {'file': (file_path.name, f, self._get_content_type(file_path))}
                response = requests.post(f"{self.api_base}/upload", files=files, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Success: {file_path.name}")
                print(f"   📋 File ID: {result['file_id']}")
                print(f"   📊 Status: {result['status']}")
                self.uploaded_files.append({
                    'path': str(file_path),
                    'file_id': result['file_id'],
                    'filename': result['filename']
                })
                return True
            else:
                print(f"❌ Failed: {file_path.name} - {response.status_code}")
                print(f"   Error: {response.text}")
                self.failed_files.append(str(file_path))
                return False
                
        except Exception as e:
            print(f"❌ Error uploading {file_path.name}: {e}")
            self.failed_files.append(str(file_path))
            return False
    
    def _get_content_type(self, file_path: Path) -> str:
        """Get content type for file"""
        ext = file_path.suffix.lower()
        if ext == '.pdf':
            return 'application/pdf'
        elif ext in ['.xlsx', '.xls']:
            return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        else:
            return 'application/octet-stream'
    
    def upload_batch(self, file_paths: List[Path], delay: float = 1.0) -> None:
        """Upload multiple files with optional delay between uploads"""
        total_files = len(file_paths)
        
        if total_files == 0:
            print("⚠️ No supported files found to upload")
            return
        
        print(f"\n📊 Found {total_files} files to upload")
        print(f"📄 Supported types: {', '.join(SUPPORTED_EXTENSIONS)}")
        print(f"⏱️ Delay between uploads: {delay}s")
        print("=" * 50)
        
        for i, file_path in enumerate(file_paths, 1):
            print(f"\n[{i}/{total_files}] ", end="")
            success = self.upload_file(file_path)
            
            if i < total_files and delay > 0:
                time.sleep(delay)
        
        self._print_summary()
    
    def _print_summary(self) -> None:
        """Print upload summary"""
        print("\n" + "=" * 50)
        print("📊 UPLOAD SUMMARY")
        print("=" * 50)
        
        print(f"✅ Successfully uploaded: {len(self.uploaded_files)}")
        for file_info in self.uploaded_files:
            print(f"   📄 {Path(file_info['path']).name} (ID: {file_info['file_id'][:8]}...)")
        
        if self.failed_files:
            print(f"\n❌ Failed uploads: {len(self.failed_files)}")
            for failed_path in self.failed_files:
                print(f"   📄 {Path(failed_path).name}")
        
        print(f"\n💡 Total processed: {len(self.uploaded_files) + len(self.failed_files)}")
        
        if self.uploaded_files:
            print(f"\n🎉 Your documents are now being processed!")
            print(f"📝 You can query them using the /query endpoint")
            print(f"🌐 API Documentation: {self.api_base}/docs")

def main():
    parser = argparse.ArgumentParser(
        description="Upload documents to GraphRAG system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s document.pdf
  %(prog)s /path/to/documents/
  %(prog)s doc1.pdf doc2.xlsx folder/
  %(prog)s --recursive /main/folder/
  %(prog)s --api-base http://localhost:8000 documents/
  %(prog)s --delay 2.0 large_folder/
        """
    )
    
    parser.add_argument(
        'paths',
        nargs='+',
        help='File paths or directories containing documents to upload'
    )
    
    parser.add_argument(
        '--recursive', '-r',
        action='store_true',
        help='Recursively scan subdirectories'
    )
    
    parser.add_argument(
        '--api-base',
        default=DEFAULT_API_BASE,
        help=f'GraphRAG API base URL (default: {DEFAULT_API_BASE})'
    )
    
    parser.add_argument(
        '--delay',
        type=float,
        default=1.0,
        help='Delay in seconds between uploads (default: 1.0)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show files that would be uploaded without actually uploading'
    )
    
    args = parser.parse_args()
    
    print("🚀 GraphRAG Document Upload Script")
    print("=" * 50)
    
    # Initialize uploader
    uploader = DocumentUploader(args.api_base)
    
    # Check system health (skip for dry run)
    if not args.dry_run:
        if not uploader.check_system_health():
            sys.exit(1)
        print()
    
    # Collect files
    files_to_upload = uploader.collect_files(args.paths, args.recursive)
    
    if args.dry_run:
        print(f"\n🔍 DRY RUN - Found {len(files_to_upload)} files:")
        for file_path in files_to_upload:
            print(f"   📄 {file_path}")
        print(f"\n💡 Use without --dry-run to actually upload these files")
        return
    
    # Upload files
    if files_to_upload:
        uploader.upload_batch(files_to_upload, args.delay)
    else:
        print("⚠️ No supported files found in the specified paths")
        print(f"📄 Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}")

if __name__ == "__main__":
    main()
