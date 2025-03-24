import asyncio
import aiohttp
import os
import sys
import sqlite3
import xml.etree.ElementTree as ET
import pandas as pd
import json
from datetime import datetime
import time
import re
from dotenv import load_dotenv
from tqdm import tqdm

# Load environment variables
load_dotenv()

# Global cache for TLD pricing
tld_price_cache = {}

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

def ensure_price_columns_exist(conn):
    """Ensure necessary columns exist in the database."""
    cursor = conn.cursor()
    
    # Check if price columns exist, add them if not
    try:
        cursor.execute("SELECT price, price_type FROM domain_results LIMIT 1")
    except sqlite3.OperationalError:
        try:
            cursor.execute("ALTER TABLE domain_results ADD COLUMN price REAL")
            cursor.execute("ALTER TABLE domain_results ADD COLUMN price_type TEXT")
            print("Added price columns to database")
        except sqlite3.OperationalError as e:
            # This might happen if another process already added the columns
            print(f"Note: {e}")
    
    # Check if pricing_data column exists
    try:
        cursor.execute("SELECT pricing_data FROM domain_results LIMIT 1")
    except sqlite3.OperationalError:
        try:
            cursor.execute("ALTER TABLE domain_results ADD COLUMN pricing_data TEXT")
            print("Added pricing_data column to database")
        except sqlite3.OperationalError as e:
            print(f"Note: {e}")
    
    conn.commit()

def save_raw_response(filename, content):
    """Save raw API response to a file for debugging."""
    debug_dir = os.path.join(get_data_directory(), 'debug')
    os.makedirs(debug_dir, exist_ok=True)
    
    with open(os.path.join(debug_dir, filename), 'w') as f:
        f.write(content)

async def get_domain_price(session, domain, api_key, username, client_ip):
    """Get pricing information for a domain using Namecheap API."""
    domain_tld = domain.split('.')[-1].lower()
    
    # Step 1: Check domain availability and premium status
    url = "https://api.namecheap.com/xml.response"
    check_params = {
        "ApiUser": username,
        "ApiKey": api_key,
        "UserName": username,
        "ClientIp": client_ip,
        "Command": "namecheap.domains.check",
        "DomainList": domain
    }
    
    try:
        # First request: Check domain availability
        async with session.get(url, params=check_params) as response:
            check_response_text = await response.text()
            
            # Save raw response for debugging (first few requests only)
            if random.random() < 0.1:  # Save ~10% of responses for analysis
                save_raw_response(f"domain_check_{domain}_{int(time.time())}.xml", check_response_text)
            
            # Create API response tracking object
            api_response = {
                'timestamp': datetime.now().isoformat(),
                'status_code': response.status,
                'domain_check_response': check_response_text
            }
            
            if response.status != 200:
                return {
                    'domain': domain,
                    'price': None,
                    'price_type': 'Error',
                    'error': f"API error: {response.status}",
                    'pricing_data': json.dumps(api_response)
                }
            
            # Parse XML response
            try:
                root = ET.fromstring(check_response_text)
                
                # Check if response indicates an error
                api_status = root.attrib.get('Status', 'ERROR')
                if api_status != 'OK':
                    error_elem = root.find('.//Error')
                    error_message = error_elem.text if error_elem is not None else "Unknown API error"
                    api_response['error'] = error_message
                    return {
                        'domain': domain,
                        'price': None,
                        'price_type': 'Error',
                        'error': error_message,
                        'pricing_data': json.dumps(api_response)
                    }
                
                # Parse domain check result
                domain_check = root.find('.//DomainCheckResult')
                if domain_check is None:
                    return {
                        'domain': domain,
                        'price': None,
                        'price_type': 'Error', 
                        'error': "No DomainCheckResult found in API response",
                        'pricing_data': json.dumps(api_response)
                    }
                
                # Extract domain check attributes
                domain_attributes = {k: v for k, v in domain_check.attrib.items()}
                api_response['domain_attributes'] = domain_attributes
                
                # Check availability
                available = domain_check.attrib.get('Available', 'false').lower() == 'true'
                if not available:
                    return {
                        'domain': domain,
                        'price': None,
                        'price_type': 'Taken',
                        'error': "Domain is not available",
                        'pricing_data': json.dumps(api_response)
                    }
                
                # Check for premium pricing
                is_premium = domain_check.attrib.get('IsPremiumName', 'false').lower() == 'true'
                if is_premium:
                    premium_price = float(domain_check.attrib.get('PremiumRegistrationPrice', '0'))
                    return {
                        'domain': domain,
                        'price': premium_price,
                        'price_type': 'Premium',
                        'error': None,
                        'pricing_data': json.dumps(api_response)
                    }
                
                # If domain is available but not premium, get standard price
                standard_price = await get_tld_price(session, domain_tld, api_key, username, client_ip)
                api_response['standard_price_info'] = {'tld': domain_tld, 'price': standard_price}
                
                return {
                    'domain': domain,
                    'price': standard_price,
                    'price_type': 'Standard',
                    'error': None,
                    'pricing_data': json.dumps(api_response)
                }
            
            except ET.ParseError as e:
                # XML parsing error
                api_response['error'] = f"XML parsing error: {str(e)}"
                api_response['raw_xml'] = check_response_text
                return {
                    'domain': domain,
                    'price': None,
                    'price_type': 'Error',
                    'error': f"XML parsing error: {str(e)}",
                    'pricing_data': json.dumps(api_response)
                }
                
    except Exception as e:
        api_response = {
            'timestamp': datetime.now().isoformat(),
            'error': str(e),
            'domain': domain
        }
        
        return {
            'domain': domain,
            'price': None,
            'price_type': 'Error',
            'error': str(e),
            'pricing_data': json.dumps(api_response)
        }

async def get_tld_price(session, tld, api_key, username, client_ip):
    """Get the standard price for a TLD using caching to minimize API calls."""
    global tld_price_cache
    
    # Check cache first
    if tld in tld_price_cache:
        return tld_price_cache[tld]
    
    # Use hardcoded price as fallback if API fails
    hardcoded_price = get_standard_price_for_tld(tld)
    
    # Try to get accurate price from Namecheap API
    try:
        # Get pricing for TLD
        url = "https://api.namecheap.com/xml.response"
        pricing_params = {
            "ApiUser": username,
            "ApiKey": api_key,
            "UserName": username,
            "ClientIp": client_ip,
            "Command": "namecheap.users.getPricing",
            "ProductType": "DOMAIN",
            "ProductCategory": "REGISTER",
            "ActionName": "REGISTER",
            "ProductName": tld
        }
        
        async with session.get(url, params=pricing_params) as response:
            if response.status != 200:
                # Use hardcoded price if API call fails
                tld_price_cache[tld] = hardcoded_price
                return hardcoded_price
            
            pricing_response = await response.text()
            
            # Save raw response for debugging
            save_raw_response(f"tld_pricing_{tld}_{int(time.time())}.xml", pricing_response)
            
            try:
                # Parse XML response for pricing
                root = ET.fromstring(pricing_response)
                
                # Check for API errors
                api_status = root.attrib.get('Status', 'ERROR')
                if api_status != 'OK':
                    tld_price_cache[tld] = hardcoded_price
                    return hardcoded_price
                
                # Navigate to price info - each API might have different XML structure
                # Try different paths to find the price
                # For TLD-specific pricing:
                price_elem = root.find(f".//Product[@Name='{tld}']/Price")
                
                if price_elem is None:
                    # Try general REGISTER category
                    price_elem = root.find(".//ProductCategory[@Name='REGISTER']/Product/Price")
                
                if price_elem is not None and 'Price' in price_elem.attrib:
                    price = float(price_elem.attrib['Price'])
                    tld_price_cache[tld] = price
                    return price
                
                # Fallback to hardcoded price if we can't find price in the XML
                tld_price_cache[tld] = hardcoded_price
                return hardcoded_price
                
            except ET.ParseError:
                # XML parsing error, use hardcoded price
                tld_price_cache[tld] = hardcoded_price
                return hardcoded_price
    
    except Exception:
        # Any exception, use hardcoded price
        tld_price_cache[tld] = hardcoded_price
        return hardcoded_price

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

def analyze_api_responses(conn, domain_limit=5):
    """Analyze the API responses stored in the database to see what data is available."""
    cursor = conn.cursor()
    cursor.execute("SELECT domain, pricing_data FROM domain_results WHERE pricing_data IS NOT NULL LIMIT ?", (domain_limit,))
    rows = cursor.fetchall()
    
    if not rows:
        print("No API response data found in the database yet.")
        return
    
    print("\nAnalyzing sample API responses to identify available fields:")
    
    for domain, pricing_data in rows:
        try:
            data = json.loads(pricing_data)
            print(f"\nDomain: {domain}")
            
            if 'domain_attributes' in data:
                print("  Domain attributes from Namecheap API:")
                for key, value in data['domain_attributes'].items():
                    print(f"    - {key}: {value}")
            
            if 'standard_price_info' in data:
                print(f"  Standard price info: {data['standard_price_info']}")
            
            if 'error' in data:
                print(f"  Error: {data['error']}")
            
            # Only show first few domains
            domain_limit -= 1
            if domain_limit <= 0:
                break
                
        except json.JSONDecodeError:
            print(f"  Error parsing JSON for {domain}")
            continue
    
    print("\nThis data is now stored in the 'pricing_data' column and can be used for future analysis.")

async def update_domain_prices(quantity=10, sort_field="average_score", batch_size=10):
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
    
    # Validate sort field
    valid_fields = ["average_score", "memorability", "pronunciation", "visual_appeal", "brandability"]
    if sort_field not in valid_fields:
        print(f"Invalid sort field: {sort_field}. Using 'average_score' instead.")
        sort_field = "average_score"
    
    # Connect to database
    conn = get_db_connection()
    ensure_price_columns_exist(conn)
    cursor = conn.cursor()
    
    # Get domains that need pricing, sorted by the specified field
    query = f"""
        SELECT domain FROM domain_results 
        WHERE price IS NULL AND {sort_field} IS NOT NULL
        ORDER BY {sort_field} DESC
        LIMIT ?
    """
    
    cursor.execute(query, (quantity,))
    domains = [row[0] for row in cursor.fetchall()]
    
    if not domains:
        print("No domains need pricing information.")
        conn.close()
        return
    
    print(f"Getting pricing for {len(domains)} domains (sorted by {sort_field})...")
    
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
                        "UPDATE domain_results SET price = ?, price_type = ?, error = ?, pricing_data = ? WHERE domain = ?",
                        (result.get('price'), result.get('price_type'), result.get('error'), 
                         result.get('pricing_data'), result.get('domain'))
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
    cursor.execute(f"""
        SELECT domain, {sort_field}, price, price_type
        FROM domain_results
        WHERE price IS NOT NULL
        ORDER BY {sort_field} DESC, price ASC
        LIMIT 10
    """)
    
    top_domains = cursor.fetchall()
    
    if top_domains:
        print(f"\nTop domains with pricing (sorted by {sort_field}):")
        print(f"{'Domain':<20} {'Score':>5} {'Price':>8} {'Type':<10}")
        print("-" * 45)
        for domain, score, price, price_type in top_domains:
            price_str = f"${price:.2f}" if price else "-"
            print(f"{domain:<20} {score:>5.1f} {price_str:>8} {price_type:<10}")
    
    # Analyze the API responses
    analyze_api_responses(conn)
    
    conn.close()

def print_usage():
    """Print usage instructions."""
    print("Domain Pricing Tool")
    print("==================\n")
    print("Usage: python domain_pricing.py [quantity] [sort_field]\n")
    print("Arguments:")
    print("  quantity   : Number of domains to price (default: 10)")
    print("  sort_field : Field to sort domains by (default: average_score)")
    print("               Options: average_score, memorability, pronunciation, visual_appeal, brandability\n")
    print("Examples:")
    print("  python domain_pricing.py")
    print("  python domain_pricing.py 20")
    print("  python domain_pricing.py 15 memorability")

if __name__ == "__main__":
    try:
        # For testing
        import random
        
        # Parse command line arguments
        quantity = 10  # Default
        sort_field = "average_score"  # Default
        
        if len(sys.argv) > 1:
            if sys.argv[1].lower() in ['-h', '--help', 'help']:
                print_usage()
                sys.exit(0)
            try:
                quantity = int(sys.argv[1])
            except ValueError:
                print(f"Invalid quantity: {sys.argv[1]}. Using default (10).")
        
        if len(sys.argv) > 2:
            sort_field = sys.argv[2].lower()
        
        asyncio.run(update_domain_prices(quantity, sort_field))
    except KeyboardInterrupt:
        print("\nProcess interrupted.")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()