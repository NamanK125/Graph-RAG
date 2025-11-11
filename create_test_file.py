#!/usr/bin/env python3
"""
Simple Test Document for GraphRAG
"""

import os
from pathlib import Path

def create_simple_test_file():
    """Create a simple text file for testing"""
    
    test_dir = Path("test_data")
    test_dir.mkdir(exist_ok=True)
    
    # Create a simple text file
    test_file = test_dir / "simple_test.txt"
    
    content = """
SIMPLE TEST DOCUMENT

COMPANY: TestCorp Inc.
LOCATION: San Francisco, CA
CEO: Alice Johnson
CTO: Bob Smith

PRODUCTS:
- Software Solution A
- Hardware Device B
- Service Package C

RELATIONSHIPS:
Alice Johnson leads TestCorp Inc.
Bob Smith manages technology at TestCorp Inc.
TestCorp Inc. produces Software Solution A.
TestCorp Inc. manufactures Hardware Device B.
TestCorp Inc. offers Service Package C.

FINANCIAL INFO:
Revenue: $1,000,000
Employees: 50
Founded: 2020
"""
    
    with open(test_file, 'w') as f:
        f.write(content)
    
    print(f"✅ Created simple test file: {test_file}")
    return str(test_file)

if __name__ == "__main__":
    create_simple_test_file()
