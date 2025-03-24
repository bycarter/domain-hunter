import asyncio
import json
import signal
import sys
import sqlite3
import os
import pandas as pd
import time
import random
from tqdm import tqdm
from openai import AsyncOpenAI

# Global variable to track shutdown request
shutdown_requested = False

# Track error counts by type
error_counts = {}

##############################
# Utility Functions          #
##############################

def get_openai_key():
    """Get the OpenAI API key from environment variables or .env file."""
    # Try to load from .env file first
    try:
        from dotenv import load_dotenv
        # Look for .env file in project root directory
        dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
        if os.path.exists(dotenv_path):
            load_dotenv(dotenv_path)
    except ImportError:
        print("Warning: python-dotenv not installed. Trying to read API key from environment variables.")
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set. Please set your API key in a .env file or environment variables.")
    return api_key

def get_data_directory():
    """Get the absolute path to the data directory."""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

##############################
# SQLite Database Functions  #
##############################

def init_db(db_path=None):
    """Initialize (or connect to) the SQLite database and create the table if it doesn't exist."""
    if db_path is None:
        db_path = os.path.join(get_data_directory(), 'domains.db')
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS domain_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT UNIQUE,
            memorability REAL,
            pronunciation REAL,
            visual_appeal REAL,
            brandability REAL,
            average_score REAL,
            raw_json TEXT,
            error TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    return conn

def insert_result(conn, result):
    """Insert or update a domain result into the database."""
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO domain_results 
        (domain, memorability, pronunciation, visual_appeal, brandability, average_score, raw_json, error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', result)
    conn.commit()

def domain_already_processed(conn, domain):
    """Check if the domain has already been processed completely (has an average score)."""
    c = conn.cursor()
    c.execute("SELECT average_score FROM domain_results WHERE domain = ?", (domain,))
    result = c.fetchone()
    
    # Only consider it processed if it has an average score (successful processing)
    return result is not None and result[0] is not None

def get_all_processed_domains(conn):
    """Get a set of all successfully processed domains."""
    c = conn.cursor()
    c.execute("SELECT domain FROM domain_results WHERE average_score IS NOT NULL")
    results = c.fetchall()
    return {row[0] for row in results}

def get_top_domains(conn, limit=10):
    """Get the top scoring domains from the database."""
    c = conn.cursor()
    c.execute("""
        SELECT domain, memorability, pronunciation, visual_appeal, brandability, average_score
        FROM domain_results
        WHERE average_score IS NOT NULL
        ORDER BY average_score DESC
        LIMIT ?
    """, (limit,))
    return c.fetchall()

def count_domains_in_db(conn):
    """Count total domains in the database and how many are successfully processed."""
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM domain_results")
    total = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM domain_results WHERE average_score IS NOT NULL")
    success = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM domain_results WHERE error IS NOT NULL")
    errors = c.fetchone()[0]
    
    return {
        'total': total,
        'success': success,
        'errors': errors,
        'incomplete': total - success - errors
    }

##############################
# Domain Scoring Functions   #
##############################

async def ai_score(domain, client, conn, semaphore, batch_counter, pbar):
    """Score a domain using the OpenAI API with basic retry."""
    global error_counts
    
    # Skip if already processed with a score
    if domain_already_processed(conn, domain):
        return None
    
    # Refined prompt - explicitly tell it NOT to use markdown
    prompt = f"""
You are a branding expert. Evaluate the domain "{domain}" based on the following four criteria:

Memorability: How easy is it to remember the domain?

Pronunciation: How easily can it be pronounced?

Visual Appeal: How attractive is the domain when seen as text?

Brandability: How well can the domain serve as a strong, unique brand identity?

Provide your response as a raw JSON object with exactly these keys: "memorability", "pronunciation", "visual_appeal", and "brandability". Each key should map to a number from 1 (poor) to 10 (excellent).

IMPORTANT: Return ONLY the JSON object without any markdown formatting, code blocks, explanations, or additional text.
    """
    
    max_retries = 3
    retry_delay = 1
    
    async with semaphore:
        for attempt in range(max_retries):
            try:
                # Call the API
                response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=100
                )
                
                # Process successful response
                response_text = response.choices[0].message.content.strip()
                
                # Clean up the response to handle markdown code blocks
                if response_text.startswith("```") and "```" in response_text:
                    # Extract just the JSON part from the markdown code block
                    response_text = response_text.split("```", 2)[1]  # Get the middle part
                    # If there's a language indicator (like "json"), remove it
                    if "\n" in response_text:
                        response_text = response_text.split("\n", 1)[1]
                    response_text = response_text.strip()
                    # Remove trailing code block markers if present
                    if response_text.endswith("```"):
                        response_text = response_text[:-3].strip()
                
                # Parse the cleaned JSON
                data = json.loads(response_text)
                
                # Compute average score
                avg_score = sum(data.values()) / len(data)
                
                # Prepare result for database
                result = (
                    domain,
                    data.get("memorability"),
                    data.get("pronunciation"),
                    data.get("visual_appeal"),
                    data.get("brandability"),
                    avg_score,
                    response_text,
                    None  # No error
                )
                
                # Update counter and track high scores
                batch_counter['success'] += 1
                if avg_score >= 8.0:
                    batch_counter['high_scores'].append((domain, avg_score))
                
                # Insert into database
                insert_result(conn, result)
                return result
            
            except json.JSONDecodeError as e:
                # Handle JSON parsing errors separately
                err_msg = f"JSON Error: {str(e)}"
                error_type = "JSON Error"
                
                # Print the raw response to help debug
                tqdm.write(f"\n❌ Error with {domain}: {err_msg}")
                if 'response_text' in locals():
                    tqdm.write(f"Response text: {repr(response_text)}")
                
                # Update error counts
                error_counts[error_type] = error_counts.get(error_type, 0) + 1
                
                # Update progress bar with error info
                pbar.set_postfix_str(f"Errors: {sum(error_counts.values())} ({', '.join([f'{k}: {v}' for k, v in error_counts.items()])})")
                
                # Try a fallback approach for handling common JSON issues
                if 'response_text' in locals():
                    try:
                        # Try to clean the response more aggressively
                        cleaned_text = response_text.replace("```json", "").replace("```", "").strip()
                        # Try adding missing braces if needed
                        if not cleaned_text.startswith("{"):
                            cleaned_text = "{" + cleaned_text
                        if not cleaned_text.endswith("}"):
                            cleaned_text = cleaned_text + "}"
                        
                        data = json.loads(cleaned_text)
                        
                        # If we're here, the aggressive cleaning worked!
                        tqdm.write(f"✅ Recovered using aggressive JSON cleaning!")
                        
                        # Compute average score
                        avg_score = sum(data.values()) / len(data)
                        
                        # Prepare result for database
                        result = (
                            domain,
                            data.get("memorability"),
                            data.get("pronunciation"),
                            data.get("visual_appeal"),
                            data.get("brandability"),
                            avg_score,
                            cleaned_text,
                            None  # No error - we recovered
                        )
                        
                        # Update counter and track high scores
                        batch_counter['success'] += 1
                        if avg_score >= 8.0:
                            batch_counter['high_scores'].append((domain, avg_score))
                        
                        # Insert into database
                        insert_result(conn, result)
                        return result
                    except:
                        # Recovery failed, proceed with error handling
                        pass
                
                result = (domain, None, None, None, None, None, response_text if 'response_text' in locals() else None, err_msg)
                insert_result(conn, result)
                batch_counter['errors'] += 1
                return result
                
            except Exception as e:
                error_str = str(e).lower()
                
                # Categorize the error
                if "rate limit" in error_str or "too many requests" in error_str:
                    error_type = "Rate Limit"
                    batch_counter['rate_limits'] += 1
                    
                    if attempt < max_retries - 1:
                        delay = retry_delay * (2 ** attempt) + random.uniform(0, 1)
                        await asyncio.sleep(delay)
                        continue
                    else:
                        err_msg = "Rate limited"
                elif "auth" in error_str or "key" in error_str:
                    error_type = "Auth Error"
                    err_msg = f"Authentication Error: {str(e)}"
                elif "model" in error_str:
                    error_type = "Model Error"
                    err_msg = f"Model Error: {str(e)}"
                else:
                    error_type = "Other Error"
                    err_msg = f"Error: {str(e)}"
                
                # Update error counts
                error_counts[error_type] = error_counts.get(error_type, 0) + 1
                
                # Update progress bar with error info
                pbar.set_postfix_str(f"Errors: {sum(error_counts.values())} ({', '.join([f'{k}: {v}' for k, v in error_counts.items()])})")
                
                # Log the error
                tqdm.write(f"\n❌ Error with {domain}: {err_msg}")
                
                result = (domain, None, None, None, None, None, None, err_msg)
                insert_result(conn, result)
                batch_counter['errors'] += 1
                return result

##############################
# Main Function              #
##############################

async def main():
    global error_counts
    error_counts = {}
    
    # Initialize the database
    conn = init_db()
    
    # Get database statistics
    db_stats = count_domains_in_db(conn)
    print(f"Database contains {db_stats['total']} domains:")
    print(f"  - {db_stats['success']} successfully scored")
    print(f"  - {db_stats['errors']} failed with errors")
    print(f"  - {db_stats['incomplete']} incomplete entries")
    
    # Get available domains from CSV
    try:
        input_path = os.path.join(get_data_directory(), 'domain_availability.csv')
        df = pd.read_csv(input_path)
        available_df = df[df['status'] == 'Available']
        
        total_available = len(available_df)
        if total_available == 0:
            print("No available domains found to score.")
            return
        
        print(f"Found {total_available} available domains in CSV file")
            
    except FileNotFoundError:
        print(f"Error: Could not find {input_path}")
        print("Please run check_domains.py first to generate the domain availability data.")
        sys.exit(1)
    
    # Initialize OpenAI client
    try:
        client = AsyncOpenAI(api_key=get_openai_key())
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    # Get set of already processed domains
    processed_domains = get_all_processed_domains(conn)
    print(f"Found {len(processed_domains)} successfully processed domains in database")
    
    # Filter out domains that are already processed
    domains_to_score = []
    for _, row in available_df.iterrows():
        domain = row['domain']
        if domain not in processed_domains:
            domains_to_score.append(domain)
    
    total_domains = len(domains_to_score)
    
    if total_domains == 0:
        print("All available domains have already been scored!")
        show_top_domains(conn)
        return
    
    print(f"Found {total_domains} domains that need scoring")
    
    # Test the API with a single call to make sure everything works
    print("\nTesting API connection with model gpt-4o-mini...")
    try:
        test_response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Say hello!"}],
            max_tokens=10
        )
        print(f"✅ API test successful! Response: {test_response.choices[0].message.content}")
    except Exception as e:
        print(f"❌ API test failed: {e}")
        confirm = input("Continue anyway? (y/n): ")
        if confirm.lower() != 'y':
            print("Exiting.")
            return
    
    # Use concurrency but avoid rate limits
    # Start with a conservative limit of 20 concurrent requests for the new model
    concurrency = 20
    semaphore = asyncio.Semaphore(concurrency)
    
    # Process in batches to handle network disruptions better
    batch_size = 100
    total_batches = (total_domains + batch_size - 1) // batch_size
    
    # Use a single progress bar for all batches
    pbar = tqdm(total=total_domains, desc="Scoring Domains")
    
    # Track global stats
    total_success = 0
    total_errors = 0
    total_rate_limits = 0
    high_scores = []
    
    # Process domain batches
    for i in range(0, total_domains, batch_size):
        batch = domains_to_score[i:i+batch_size]
        batch_num = i // batch_size + 1
        
        # Update progress bar description with batch info
        pbar.set_description(f"Batch {batch_num}/{total_batches}")
        
        # Counter for this batch
        batch_counter = {
            'success': 0,
            'errors': 0,
            'rate_limits': 0,
            'high_scores': []
        }
        
        # Process the batch
        tasks = [ai_score(domain, client, conn, semaphore, batch_counter, pbar) for domain in batch]
        await asyncio.gather(*tasks)
        
        # Update progress bar
        pbar.update(len(batch))
        processed = batch_counter['success'] + batch_counter['errors']
        
        # Update global stats
        total_success += batch_counter['success']
        total_errors += batch_counter['errors']
        total_rate_limits += batch_counter['rate_limits']
        high_scores.extend(batch_counter['high_scores'])
        
        # Show batch summary
        tqdm.write(f"\nBatch {batch_num} summary:")
        tqdm.write(f"  Success: {batch_counter['success']}")
        tqdm.write(f"  Errors: {batch_counter['errors']}")
        tqdm.write(f"  Rate limits: {batch_counter['rate_limits']}")
        
        # Dynamically adjust concurrency based on rate limits
        if batch_counter['rate_limits'] > 5:
            # Too many rate limits, reduce concurrency
            concurrency = max(5, concurrency - 5)
            semaphore = asyncio.Semaphore(concurrency)
            tqdm.write(f"Rate limits detected. Reducing concurrency to {concurrency}")
        elif batch_counter['rate_limits'] == 0 and processed > 0 and concurrency < 40:
            # No rate limits, can try increasing concurrency slightly (but more conservatively with gpt-4o-mini)
            concurrency = min(40, concurrency + 2)
            semaphore = asyncio.Semaphore(concurrency)
            # Only log concurrency changes occasionally
            if batch_num % 5 == 0 or concurrency == 40:
                tqdm.write(f"Concurrency set to {concurrency}")
        
        # Show high scores using tqdm.write to not interfere with progress bar
        if batch_counter['high_scores']:
            tqdm.write("\nHigh scores in this batch:")
            for domain, score in sorted(batch_counter['high_scores'], key=lambda x: x[1], reverse=True):
                tqdm.write(f"  {domain}: {score:.1f}/10")
        
        # Show current error summary
        if error_counts:
            tqdm.write("\nCurrent error summary:")
            for error_type, count in error_counts.items():
                tqdm.write(f"  {error_type}: {count}")
        
        # Check if shutdown was requested
        if shutdown_requested:
            tqdm.write("\nShutdown requested. Stopping after current batch.")
            break
        
        # Brief pause between batches to avoid rate limits
        if i + batch_size < total_domains:
            await asyncio.sleep(1)
    
    # Close progress bar
    pbar.close()
    
    # Show overall summary
    print("\nScoring complete!")
    print(f"Processed {total_success + total_errors} domains")
    print(f"Successful: {total_success}")
    print(f"Errors: {total_errors} (including {total_rate_limits} rate limits)")
    
    # Show error summary
    if error_counts:
        print("\nError summary:")
        for error_type, count in error_counts.items():
            print(f"  {error_type}: {count}")
    
    # Show top high scores from this run
    if high_scores:
        print("\nTop scores from this run:")
        for domain, score in sorted(high_scores, key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {domain}: {score:.1f}/10")
    
    # Show top domains from database
    show_top_domains(conn)

def show_top_domains(conn, limit=10):
    """Display the top scoring domains in a nice table."""
    top_domains = get_top_domains(conn, limit)
    
    if not top_domains:
        print("No scored domains found in the database.")
        return
    
    print(f"\n===== Top {len(top_domains)} Domains =====")
    print(f"{'Domain':<20} {'Mem':>5} {'Pron':>5} {'Vis':>5} {'Brand':>5} {'Avg':>5}")
    print("-" * 50)
    
    for domain, mem, pron, vis, brand, avg in top_domains:
        print(f"{domain:<20} {mem:>5.1f} {pron:>5.1f} {vis:>5.1f} {brand:>5.1f} {avg:>5.1f}")

# Set up signal handler for clean exit
def signal_handler(sig, frame):
    global shutdown_requested
    print("\nGraceful shutdown initiated. Completing current batch...")
    shutdown_requested = True

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProcess interrupted. Partial progress has been saved.")
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)