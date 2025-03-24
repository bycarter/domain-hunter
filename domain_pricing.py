import asyncio
import aiohttp
import os
import sys
import sqlite3
import xml.etree.ElementTree as ET
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

# Load environment variables
load_dotenv()

def get_data_directory():
    """Get the absolute path to the data directory."""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

def get_db_connection():
    """Connect to the SQLite database."""
    db_path = os.path.join(get_data_directory(), 'domains.db')
    conn = sqlite3.connect(db_path)
    return conn

async def get_domain_price(session, domain, api_key, username, client_ip):
    """Get pricing information for a domain using Namecheap API."""
    url = "https://api.namecheap.com/xml.response"
    params = {
        "ApiUser": username,
        "ApiKey": api_key,
        "UserName": username,
        "ClientIp": client_ip,
        "Command": "namecheap.domains.check",
        "DomainList": domain
    }
    
    try:
        async with session.get(url, params=params) as response:
            if response.status == 200:
                xml_text = await response.text()
                root = ET.fromstring(xml_text)
                
                # Check for errors in the response
                error_count = int(root.attrib.get('Errors', '0'))
                if error_count > 0:
                    error_text = root.find('.//Error').text
                    return {
                        'domain': domain,
                        'price': None,
                        'price_type': 'Error',
                        'error': error_text
                    }
                
                # Parse domain information
                domain_check = root.find('.//DomainCheckResult')
                if domain_check is not None:
                    available = domain_check.attrib.get('Available', 'false').lower() == 'true'
                    
                    if available:
                        # Check for premium pricing
                        is_premium = 'IsPremiumName' in domain_check.attrib and domain_check.attrib['IsPremiumName'].lower() == 'true'
                        
                        if is_premium:
                            premium_price = float(domain_check.attrib.get('PremiumRegistrationPrice', '0'))
                            return {
                                'domain': domain,
                                'price': premium_price,
                                'price_type': 'Premium',
                                'error': None
                            }
                        else:
                            # Get standard price based on TLD
                            tld = domain.split('.')[-1].lower()
                            standard_price = get_standard_price_for_tld(tld)
                            return {
                                'domain': domain,
                                'price': standard_price,
                                'price_type': 'Standard',
                                'error': None
                            }
                    else:
                        return {
                            'domain': domain,
                            'price': None,
                            'price_type': 'Taken',
                            'error': "Domain is not available"
                        }
            
            return {
                'domain': domain,
                'price': None,
                'price_type': 'Error',
                'error': f"API error: {response.status}"
            }
                
    except Exception as e:
        return {
            'domain': domain,
            'price': None,
            'price_type': 'Error',
            'error': str(e)
        }

def get_standard_price_for_tld(tld):
    """Return standard pricing for common TLDs."""
    # Approximate prices - you might want to update these
    standard_prices = {
        "com": 10.98,
        "net": 11.98,
        "org": 11.98,
        "io": 32.98,
        "ai": 79.98,
        "co": 25.98,
        "me": 19.98,
        "us": 9.98,
        "to": 39.98
    }
    return standard_prices.get(tld.lower(), 14.98)  # Default price if TLD not in list

async def update_domain_prices(batch_size=50, min_score=7.0, limit=None):
    """Update pricing for high-scoring domains."""
    # Get API credentials
    api_key = os.getenv('NAMECHEAP_API_KEY')
    username = os.getenv('NAMECHEAP_USERNAME') 
    client_ip = os.getenv('CLIENT_IP')  # Your whitelisted IP
    
    if not api_key:
        api_key = input("Enter your Namecheap API key: ")
    
    if not username:
        username = input("Enter your Namecheap username: ")
    
    if not client_ip:
        client_ip = input("Enter your whitelisted IP address: ")
    
    # Connect to database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get domains that need pricing
    query = f"""
        SELECT domain FROM domain_results 
        WHERE average_score >= {min_score} AND price IS NULL
        ORDER BY average_score DESC
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    cursor.execute(query)
    domains = [row[0] for row in cursor.fetchall()]
    
    if not domains:
        print("No domains need pricing information.")
        conn.close()
        return
    
    print(f"Getting pricing for {len(domains)} high-scoring domains...")
    
    # Process domains in batches
    async with aiohttp.ClientSession() as session:
        # Create progress bar
        pbar = tqdm(total=len(domains), desc="Fetching Prices")
        
        for i in range(0, len(domains), batch_size):
            batch = domains[i:i+batch_size]
            
            # Create tasks for each domain
            tasks = [get_domain_price(session, domain, api_key, username, client_ip) for domain in batch]
            results = await asyncio.gather(*tasks)
            
            # Update database with results
            for result in results:
                if result:
                    cursor.execute(
                        "UPDATE domain_results SET price = ?, price_type = ?, error = ? WHERE domain = ?",
                        (result.get('price'), result.get('price_type'), result.get('error'), result.get('domain'))
                    )
            
            conn.commit()
            pbar.update(len(batch))
            
            # Small delay between batches to avoid rate limits
            await asyncio.sleep(1)
        
        pbar.close()
    
    # Show summary
    cursor.execute("SELECT price_type, COUNT(*) FROM domain_results WHERE price IS NOT NULL GROUP BY price_type")
    price_counts = cursor.fetchall()
    
    print("\nPricing summary:")
    for price_type, count in price_counts:
        print(f"  - {price_type}: {count} domains")
    
    # Get some price statistics
    cursor.execute("""
        SELECT AVG(price), MIN(price), MAX(price) 
        FROM domain_results 
        WHERE price IS NOT NULL AND price_type = 'Standard'
    """)
    avg_price, min_price, max_price = cursor.fetchone()
    
    if avg_price:
        print(f"\nStandard domain price statistics:")
        print(f"  - Average: ${avg_price:.2f}")
        print(f"  - Minimum: ${min_price:.2f}")
        print(f"  - Maximum: ${max_price:.2f}")
    
    # Get premium domain statistics
    cursor.execute("""
        SELECT AVG(price), MIN(price), MAX(price) 
        FROM domain_results 
        WHERE price IS NOT NULL AND price_type = 'Premium'
    """)
    premium_stats = cursor.fetchone()
    
    if premium_stats[0]:
        print(f"\nPremium domain price statistics:")
        print(f"  - Average: ${premium_stats[0]:.2f}")
        print(f"  - Minimum: ${premium_stats[1]:.2f}")
        print(f"  - Maximum: ${premium_stats[2]:.2f}")
    
    # Show top domains with their prices
    cursor.execute("""
        SELECT domain, average_score, price, price_type
        FROM domain_results
        WHERE price IS NOT NULL
        ORDER BY average_score DESC, price ASC
        LIMIT 10
    """)
    
    top_domains = cursor.fetchall()
    
    if top_domains:
        print("\nTop domains with pricing:")
        print(f"{'Domain':<20} {'Score':>5} {'Price':>8} {'Type':<10}")
        print("-" * 45)
        for domain, score, price, price_type in top_domains:
            price_str = f"${price:.2f}" if price else "-"
            print(f"{domain:<20} {score:>5.1f} {price_str:>8} {price_type:<10}")
    
    conn.close()

if __name__ == "__main__":
    try:
        # Save API key to environment if provided as argument
        if len(sys.argv) > 1:
            os.environ["NAMECHEAP_API_KEY"] = sys.argv[1]
            
        # Set a limit for testing if provided
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
        
        asyncio.run(update_domain_prices(limit=limit))
    except KeyboardInterrupt:
        print("\nProcess interrupted.")
    except Exception as e:
        print(f"Error: {e}")