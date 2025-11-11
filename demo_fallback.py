#!/usr/bin/env python3
"""
Demo script showing OpenAI to Ollama fallback in action
"""

import os
from dotenv import load_dotenv
load_dotenv()

from main import OpenAIInference, Config

def demo_fallback():
    """Demonstrate the fallback functionality"""
    print("🚀 GraphRAG System - OpenAI to Ollama Fallback Demo")
    print("=" * 55)
    
    config = Config()
    
    # Initialize with fallback
    print(f"🔧 Initializing LLM:")
    print(f"   Primary: OpenAI {config.OPENAI_MODEL}")
    print(f"   Fallback: Ollama {config.OLLAMA_LLM_FALLBACK_MODEL}")
    
    openai_inference = OpenAIInference(
        api_key=config.OPENAI_API_KEY,
        model=config.OPENAI_MODEL,
        fallback_model=config.OLLAMA_LLM_FALLBACK_MODEL
    )
    
    # Test questions
    questions = [
        "What is a knowledge graph?",
        "How does RAG work?",
        "Explain entity extraction in one sentence."
    ]
    
    print(f"\n📝 Testing with {len(questions)} questions...")
    print(f"   Note: Due to OpenAI quota limits, these will use Ollama fallback")
    
    for i, question in enumerate(questions, 1):
        print(f"\n❓ Question {i}: {question}")
        try:
            response = openai_inference.generate(question)
            print(f"💬 Answer: {response}")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print(f"\n✅ Demo completed!")
    print(f"💡 Current status: Using {'Ollama ' + config.OLLAMA_LLM_FALLBACK_MODEL if openai_inference.use_fallback else 'OpenAI ' + config.OPENAI_MODEL}")

if __name__ == "__main__":
    demo_fallback()
