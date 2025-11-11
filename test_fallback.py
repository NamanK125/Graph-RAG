#!/usr/bin/env python3
"""
Test the OpenAI to Ollama fallback functionality
"""

import os
import sys
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import OpenAIInference, Config

def test_fallback_functionality():
    """Test the fallback from OpenAI to Ollama"""
    print("🧪 Testing OpenAI to Ollama Fallback Functionality")
    print("=" * 50)
    
    config = Config()
    
    # Initialize OpenAI with Llava fallback
    try:
        openai_inference = OpenAIInference(
            api_key=config.OPENAI_API_KEY,
            model=config.OPENAI_MODEL,
            fallback_model=config.OLLAMA_LLM_FALLBACK_MODEL
        )
        print(f"✅ OpenAI inference initialized with fallback model: {config.OLLAMA_LLM_FALLBACK_MODEL}")
    except Exception as e:
        print(f"❌ Failed to initialize OpenAI inference: {e}")
        return
    
    # Test 1: Simple text generation
    print("\n🔬 Test 1: Simple Text Generation")
    test_prompt = "Explain what a knowledge graph is in one sentence."
    
    try:
        response = openai_inference.generate(test_prompt)
        print(f"Response: {response[:100]}...")
        
        if response.startswith("Error:"):
            print("❌ Generation failed")
        else:
            print("✅ Generation successful")
    except Exception as e:
        print(f"❌ Generation error: {e}")
    
    # Test 2: Entity extraction
    print("\n🔬 Test 2: Entity Extraction")
    test_text = """
    Apple Inc. is a technology company founded by Steve Jobs and Steve Wozniak in 1976.
    The company is headquartered in Cupertino, California and develops consumer electronics.
    """
    
    try:
        extracted = openai_inference.extract_entities_relationships(test_text)
        print(f"Entities found: {len(extracted.get('entities', []))}")
        print(f"Relationships found: {len(extracted.get('relationships', []))}")
        
        if extracted.get('entities'):
            print("✅ Entity extraction successful")
            print("Sample entities:", [e.get('properties', {}).get('name', 'N/A') for e in extracted['entities'][:3]])
        else:
            print("⚠️ No entities extracted")
    except Exception as e:
        print(f"❌ Entity extraction error: {e}")
    
    # Test 3: Force fallback by simulating quota error
    print("\n🔬 Test 3: Force Fallback Mode")
    openai_inference.use_fallback = True
    
    try:
        response = openai_inference.generate("What is machine learning?")
        print(f"Fallback response: {response[:100]}...")
        
        if "Ollama" in response or not response.startswith("Error:"):
            print("✅ Fallback mode working")
        else:
            print("❌ Fallback mode failed")
    except Exception as e:
        print(f"❌ Fallback error: {e}")
    
    print("\n" + "=" * 50)
    print("🏁 Fallback functionality test completed!")

if __name__ == "__main__":
    test_fallback_functionality()
