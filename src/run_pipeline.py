import asyncio
import os
import sys

# Add the src directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.generate_words import generate_three_char_words
from src.check_domains import check_domains
from src.ai_score_domains import ai_score_domains

async def run_pipeline():
    print("=== Step 1: Generating three-character words ===")
    generate_three_char_words()
    
    print("\n=== Step 2: Checking domain availability ===")
    await check_domains()
    
    print("\n=== Step 3: Scoring available domains ===")
    await ai_score_domains()
    
    print("\n=== Pipeline complete! ===")

if __name__ == "__main__":
    asyncio.run(run_pipeline())