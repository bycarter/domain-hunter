import asyncio
import aiohttp
import pandas as pd
import os
import sys
import signal
import random
from tqdm import tqdm

# Create data directory if it doesn't exist
data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
os.makedirs(data_dir, exist_ok=True)

# Use absolute path to read the CSV file
input_path = os.path.join(data_dir, 'three_char_words.csv')

try:
    df = pd.read_csv(input_path)
except FileNotFoundError:
    print(f"Error: Could not find {input_path}")
    print("Please run generate_words.py first to create the input file.")
    exit(1)

tlds = ['io', 'me', 'ai', 'us', 'co', 'to']

# Increase concurrency
concurrency_limit = 200
semaphore = asyncio.Semaphore(concurrency_limit)

# Timeout for faster failure
timeout = aiohttp.ClientTimeout(total=10)

# Track available domains
available_domains = []

# Signal handler for graceful shutdown
def signal_handler(sig, frame):
    print("\nShutting down gracefully...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

async def check(session, short, tld):
    domain = f"{short}.{tld}"
    url = f"https://rdap.org/domain/{domain}"

    async with semaphore:
        try:
            async with session.get(url, timeout=timeout) as resp:
                status = 'Available' if resp.status == 404 else 'Taken' if resp.status == 200 else 'Unknown'
        except asyncio.TimeoutError:
            status = 'Timeout'
        except aiohttp.ClientError:
            status = 'Error'
        except Exception as e:
            status = 'Error'
    
    if status == 'Available':
        available_domains.append(domain)
    
    return {'short_word': short, 'tld': tld, 'domain': domain, 'status': status}

async def main():
    total_domains = len(df['three_char_word']) * len(tlds)
    print(f"Checking availability for {total_domains} domains across {len(tlds)} TLDs...")
    print(f"Using concurrency limit of {concurrency_limit} simultaneous connections")
    
    # Create domain pairs
    domain_pairs = [(short, tld) for short in df['three_char_word'] for tld in tlds]
    
    # Create progress bar with available domains counter in description
    progress_bar = tqdm(total=len(domain_pairs), desc="Checking domains", unit="domain", 
                        miniters=1, ncols=100, bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]')
    
    # Process tasks
    conn = aiohttp.TCPConnector(limit=concurrency_limit, ttl_dns_cache=300)
    results = []
    
    async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
        # Process in chunks to update progress more frequently
        tasks = [check(session, short, tld) for short, tld in domain_pairs]
        chunk_size = 100
        
        for i in range(0, len(tasks), chunk_size):
            chunk = tasks[i:i+chunk_size]
            chunk_results = await asyncio.gather(*chunk, return_exceptions=True)
            
            # Process results
            valid_results = []
            for result in chunk_results:
                if not isinstance(result, Exception):
                    valid_results.append(result)
                else:
                    # Handle exception but don't add to results to avoid errors
                    pass
            
            results.extend(valid_results)
            
            # Update progress and description to show available domains count
            progress_bar.update(len(chunk))
            progress_bar.set_description(f"Found {len(available_domains)} available domains")
            
            # Show a sample of recent available domains (only occasionally)
            if len(available_domains) > 0 and random.random() < 0.05:  # Only show updates occasionally
                recent = available_domains[-1]
                tqdm.write(f"Found available: {recent}")
    
    # Close progress bar
    progress_bar.close()

    # Save results
    output_path = os.path.join(data_dir, 'domain_availability.csv')
    results_df = pd.DataFrame(results)
    results_df.to_csv(output_path, index=False)
    
    # Show summary
    print(f"\nDomain check complete!")
    print(f"Found {len(available_domains)} available domains out of {total_domains} checked")
    
    # Show a sample of available domains
    if available_domains:
        sample_size = min(10, len(available_domains))
        print(f"\nSample of available domains:")
        for domain in random.sample(available_domains, sample_size):
            print(f"  {domain}")
        
        if len(available_domains) > sample_size:
            print(f"  ...and {len(available_domains) - sample_size} more")
    
    print(f"\nResults saved to {output_path}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProcess was interrupted by user.")
        sys.exit(1)