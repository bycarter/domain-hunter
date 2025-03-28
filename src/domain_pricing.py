import asyncio
import aiohttp
import os
import sys
import sqlite3
import xml.etree.ElementTree as ET
import json
from datetime import datetime
import time
import random
import traceback
import argparse
from dotenv import load_dotenv
from tqdm import tqdm

# Global settings
MAX_RETRIES = 3
RETRY_DELAY = 2

# Load environment variables
load_dotenv()

# Global cache for TLD pricing
tld_price_cache = {}

def get_data_directory():
    """Get the absolute path to the data directory."""
    # Use absolute path instead of relative path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(project_root, 'data')
    os.makedirs(data_dir, exist_ok=True)
    print(f"Using data directory: {data_dir}")  # Add this line for debugging
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

def get_domains_to_process(conn, quantity=None, sort_field="average_score", include_taken=False, skip_priced=True):
    """Get domains that need to be processed for pricing."""
    cursor = conn.cursor()
    
    # Build the base query
    query_conditions = [f"{sort_field} IS NOT NULL"]
    
    if not include_taken:
        # Skip domains already marked as Taken
        query_conditions.append("(price_type IS NULL OR price_type != 'Taken')")
    
    if skip_priced:
        # Skip domains that have successful pricing info
        query_conditions.append("(price_type IS NULL OR price_type = 'Error')")
    
    # Construct the query
    query = f"""
        SELECT domain FROM domain_results 
        WHERE {' AND '.join(query_conditions)}
        ORDER BY {sort_field} DESC
    """
    
    # Add limit if quantity is specified
    if quantity:
        query += f" LIMIT {quantity}"
    
    # Execute query
    cursor.execute(query)
    domains = [row[0] for row in cursor.fetchall()]
    
    return domains

def save_debug_response(domain, response_text, api_type="check"):
    """Save API response to a file for debugging."""
    debug_dir = os.path.join(get_data_directory(), 'debug')
    os.makedirs(debug_dir, exist_ok=True)
    
    filename = f"{api_type}_{domain}_{int(time.time())}.xml"
    with open(os.path.join(debug_dir, filename), 'w', encoding='utf-8') as f:
        f.write(response_text)
    
    return filename

async def check_domain_availability(session, domain, api_credentials, debug=False):
    """
    Check domain availability using the Namecheap API.
    
    Returns a dictionary with availability information.
    """
    username = api_credentials['username']
    api_key = api_credentials['api_key']
    client_ip = api_credentials['client_ip']
    
    check_url = "https://api.namecheap.com/xml.response"
    check_params = {
        "ApiUser": username,
        "ApiKey": api_key,
        "UserName": username,
        "ClientIp": client_ip,
        "Command": "namecheap.domains.check",
        "DomainList": domain
    }
    
    for attempt in range(MAX_RETRIES):
        try:
            # Call API
            async with session.get(check_url, params=check_params) as response:
                response_text = await response.text()
                
                # Save debug info if requested
                if debug:
                    debug_file = save_debug_response(domain, response_text, "check")
                    print(f"Saved debug response to {debug_file}")
                
                if response.status != 200:
                    error_msg = f"API error: {response.status}"
                    if response.status == 429:
                        error_msg = "Rate limit exceeded (429)"
                    elif response.status >= 500:
                        error_msg = f"Server error ({response.status})"
                    
                    if attempt < MAX_RETRIES - 1:
                        delay = RETRY_DELAY * (2 ** attempt) + random.uniform(0, 1)
                        print(f"{error_msg} for {domain}, retrying in {delay:.1f}s...")
                        await asyncio.sleep(delay)
                        continue
                    
                    return {
                        'domain': domain,
                        'available': False,
                        'error': error_msg,
                        'price_type': 'Error',
                        'price': None,
                        'response_text': response_text
                    }
                
                # Parse XML response with proper namespace handling
                try:
                    root = ET.fromstring(response_text)
                    namespaces = {'nc': 'http://api.namecheap.com/xml.response'}
                    
                    # Check API status
                    api_status = root.attrib.get('Status', 'ERROR')
                    if api_status != 'OK':
                        error_elem = root.find('.//nc:Error', namespaces=namespaces)
                        if error_elem is None:
                            error_elem = root.find('.//Error')
                        
                        error_message = error_elem.text if error_elem is not None else "Unknown API error"
                        
                        # Look for specific rate limit messages
                        if "too many requests" in error_message.lower() or "rate limit" in error_message.lower():
                            error_message = "Rate limit: " + error_message
                        
                        return {
                            'domain': domain,
                            'available': False,
                            'error': error_message,
                            'price_type': 'Error',
                            'price': None,
                            'response_text': response_text
                        }
                    
                    # Find domain check result
                    domain_check = root.find('.//nc:DomainCheckResult', namespaces=namespaces)
                    if domain_check is None:
                        domain_check = root.find('.//DomainCheckResult')
                    
                    if domain_check is None:
                        return {
                            'domain': domain,
                            'available': False,
                            'error': "No DomainCheckResult found in API response",
                            'price_type': 'Error',
                            'price': None,
                            'response_text': response_text
                        }
                    
                    # Extract domain check attributes
                    available = domain_check.attrib.get('Available', 'false').lower() == 'true'
                    
                    # Only proceed if domain is available
                    if not available:
                        return {
                            'domain': domain,
                            'available': False,
                            'error': None,
                            'price_type': 'Taken',
                            'price': None,
                            'response_text': response_text
                        }
                    
                    # Check for premium pricing
                    is_premium = domain_check.attrib.get('IsPremiumName', 'false').lower() == 'true'
                    
                    if is_premium:
                        premium_price = domain_check.attrib.get('PremiumRegistrationPrice', '0')
                        # Convert to float, handling various formats
                        try:
                            premium_price = float(premium_price.replace(',', ''))
                        except (ValueError, TypeError):
                            premium_price = 0
                        
                        return {
                            'domain': domain,
                            'available': True,
                            'error': None,
                            'price_type': 'Premium',
                            'price': premium_price,
                            'is_premium': True,
                            'response_text': response_text
                        }
                    
                    # For standard domains, get TLD price
                    tld = domain.split('.')[-1]
                    standard_price = await get_tld_price(session, tld, api_credentials, debug)
                    
                    return {
                        'domain': domain,
                        'available': True,
                        'error': None,
                        'price_type': 'Standard',
                        'price': standard_price,
                        'is_premium': False,
                        'response_text': response_text
                    }
                
                except ET.ParseError as e:
                    if attempt < MAX_RETRIES - 1:
                        delay = RETRY_DELAY * (2 ** attempt) + random.uniform(0, 1)
                        print(f"XML parsing error for {domain}, retrying in {delay:.1f}s...")
                        await asyncio.sleep(delay)
                        continue
                    
                    return {
                        'domain': domain,
                        'available': False,
                        'error': f"XML parsing error: {str(e)}",
                        'price_type': 'Error',
                        'price': None,
                        'response_text': response_text
                    }
        
        except aiohttp.ClientError as e:
            error_msg = f"Network error: {str(e)}"
            # Look for specific error types
            if "TimeoutError" in str(e):
                error_msg = f"Timeout error: {str(e)}"
            elif "ConnectError" in str(e):
                error_msg = f"Connection error: {str(e)}"
                
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY * (2 ** attempt) + random.uniform(0, 1)
                print(f"{error_msg} for {domain}, retrying in {delay:.1f}s...")
                await asyncio.sleep(delay)
                continue
            
            return {
                'domain': domain,
                'available': False,
                'error': error_msg,
                'price_type': 'Error',
                'price': None,
                'response_text': None
            }
        
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY * (2 ** attempt) + random.uniform(0, 1)
                print(f"Unexpected error for {domain}: {str(e)}, retrying in {delay:.1f}s...")
                await asyncio.sleep(delay)
                continue
            
            return {
                'domain': domain,
                'available': False,
                'error': f"Unexpected error: {str(e)}",
                'price_type': 'Error',
                'price': None,
                'response_text': None
            }
    
    # If we get here, all retries failed
    return {
        'domain': domain,
        'available': False,
        'error': "Maximum retries exceeded",
        'price_type': 'Error',
        'price': None,
        'response_text': None
    }

async def get_tld_price(session, tld, api_credentials, debug=False):
    """Get the standard price for a TLD using caching to minimize API calls."""
    global tld_price_cache
    
    # Check cache first
    if tld in tld_price_cache:
        return tld_price_cache[tld]
    
    username = api_credentials['username']
    api_key = api_credentials['api_key']
    client_ip = api_credentials['client_ip']
    
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
            
            # Save debug info if requested
            if debug:
                debug_file = save_debug_response(tld, pricing_response, "pricing")
                print(f"Saved TLD pricing debug response to {debug_file}")
            
            try:
                # Parse XML response for pricing
                root = ET.fromstring(pricing_response)
                namespaces = {'nc': 'http://api.namecheap.com/xml.response'}
                
                # Check for API errors
                api_status = root.attrib.get('Status', 'ERROR')
                if api_status != 'OK':
                    tld_price_cache[tld] = hardcoded_price
                    return hardcoded_price
                
                # Try different paths to find the price element
                price_paths = [
                    f".//nc:Product[@Name='{tld}']/nc:Price[@Duration='1']",
                    f".//Product[@Name='{tld}']/Price[@Duration='1']",
                    f".//nc:ProductCategory[@Name='REGISTER']/nc:Product[@Name='{tld}']/nc:Price",
                    f".//ProductCategory[@Name='REGISTER']/Product[@Name='{tld}']/Price",
                    ".//nc:Price[@Duration='1']",
                    ".//Price[@Duration='1']"
                ]
                
                price_elem = None
                for path in price_paths:
                    try:
                        if 'nc:' in path:
                            price_elem = root.find(path, namespaces=namespaces)
                        else:
                            price_elem = root.find(path)
                        
                        if price_elem is not None:
                            break
                    except:
                        continue
                
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
    
    except Exception as e:
        # Any exception, use hardcoded price
        tld_price_cache[tld] = hardcoded_price
        return hardcoded_price

def get_standard_price_for_tld(tld):
    """Return standard pricing for common TLDs."""
    standard_prices = {
        "com": 10.98,
        "net": 11.98,
        "org": 11.98,
        "io": 32.98,
        "ai": 79.98,
        "co": 25.98,
        "me": 19.98,
        "us": 9.98,
        "to": 39.98,
        "xyz": 12.98
    }
    return standard_prices.get(tld.lower(), 14.98)  # Default price if TLD not in list

def update_domain_price_in_db(conn, domain, price_info):
    """Update a domain's price information in the database."""
    cursor = conn.cursor()
    
    # Prepare pricing data JSON
    pricing_data = {
        'timestamp': datetime.now().isoformat(),
        'domain': domain,
        'available': price_info.get('available', False),
        'price_type': price_info.get('price_type'),
        'price': price_info.get('price'),
        'error': price_info.get('error')
    }
    
    # Only update price fields if there was no error
    # This keeps domains with errors marked as not priced so they'll be retried
    if not price_info.get('error'):
        try:
            cursor.execute(
                """
                UPDATE domain_results 
                SET 
                    price = ?,
                    price_type = ?,
                    error = ?,
                    pricing_data = ?
                WHERE domain = ?
                """,
                (
                    price_info.get('price'),
                    price_info.get('price_type'),
                    price_info.get('error'),
                    json.dumps(pricing_data),
                    domain
                )
            )
            return True
        except sqlite3.Error as e:
            print(f"Database error updating {domain}: {e}")
            return False
    else:
        # For errors, just store the error info in pricing_data without marking the domain as processed
        try:
            cursor.execute(
                """
                UPDATE domain_results 
                SET pricing_data = ? 
                WHERE domain = ?
                """,
                (json.dumps(pricing_data), domain)
            )
            return True
        except sqlite3.Error as e:
            print(f"Database error updating error info for {domain}: {e}")
            return False

def save_progress_file(domains_processed, file_path=None):
    """Save a list of successfully processed domains to a file."""
    if file_path is None:
        file_path = os.path.join(get_data_directory(), 'last_pricing_run.json')
    
    try:
        data = {
            'timestamp': datetime.now().isoformat(),
            'domains_processed': domains_processed
        }
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving progress file: {e}")
        return False

async def process_domain_batch(domains, session, api_credentials, conn, pbar, debug=False, max_price=None):
    """Process a batch of domains to get pricing information."""
    results = {
        'success': 0,
        'errors': 0,
        'error_types': {},
        'taken': 0,
        'premium': 0,
        'standard': 0,
        'filtered_premium': 0,
        'high_scores': [],
        'error_domains': [],  # Track domains with errors
        'success_domains': []  # Track successful domains
    }
    
    # Create tasks for the batch
    tasks = [check_domain_availability(session, domain, api_credentials, debug) for domain in domains]
    batch_results = await asyncio.gather(*tasks)
    
    # Process results and update database
    for result in batch_results:
        domain = result['domain']
        
        # Handle domains with errors
        if result.get('error'):
            results['errors'] += 1
            results['error_domains'].append(domain)
            
            # Track error types
            error_msg = result.get('error', '')
            error_type = "Unknown"
            
            if "API error" in error_msg or "error" in error_msg.lower():
                if "429" in error_msg or "rate limit" in error_msg.lower() or "too many requests" in error_msg.lower():
                    error_type = "Rate Limit"
                else:
                    error_type = "API Error"
            elif "XML parsing" in error_msg:
                error_type = "XML Error"
            elif "Network error" in error_msg:
                error_type = "Network Error"
            elif "Timeout" in error_msg:
                error_type = "Timeout"
            elif "Connection" in error_msg:
                error_type = "Connection Error"
            elif "Maximum retries" in error_msg:
                error_type = "Retry Error"
            
            results['error_types'][error_type] = results['error_types'].get(error_type, 0) + 1
            
            # Update database with error info but don't mark as processed
            update_domain_price_in_db(conn, domain, result)
            continue
        
        # Count domains by availability and type
        if not result.get('available', False):
            results['taken'] += 1
        elif result.get('price_type') == 'Premium':
            results['premium'] += 1
            # Filter out expensive premium domains if max_price is set
            if max_price and result.get('price', 0) > max_price:
                result['price_type'] = 'Filtered'
                results['filtered_premium'] += 1
        elif result.get('price_type') == 'Standard':
            results['standard'] += 1
        
        # Update database
        update_success = update_domain_price_in_db(conn, domain, result)
        if update_success:
            results['success'] += 1
            results['success_domains'].append(domain)
        
        # Get domain score for reporting
        cursor = conn.cursor()
        cursor.execute("SELECT average_score FROM domain_results WHERE domain = ?", (domain,))
        score_row = cursor.fetchone()
        if score_row and score_row[0]:
            score = score_row[0]
            if score >= 7.0 and result.get('available', False) and result.get('price_type') != 'Filtered':
                results['high_scores'].append((domain, score, result.get('price_type'), result.get('price')))
    
    # Commit database changes
    conn.commit()
    
    # Update progress bar if provided
    if pbar is not None:
        pbar.update(len(domains))
    
    return results

async def update_domain_prices(quantity=None, sort_field="average_score", batch_size=10, 
                               max_price=None, debug=False, include_taken=False, skip_priced=True, 
                               batch_cooldown=1, max_errors=None, max_consecutive_failures=3,
                               batch_retries=2, save_progress=True):
    """
    Update pricing for high-scoring domains.
    
    Args:
        quantity: Number of domains to process (None for all)
        sort_field: Field to sort domains by
        batch_size: Number of domains to process in each batch
        max_price: Maximum price for premium domains
        debug: Whether to save debug information
        include_taken: Whether to include domains marked as taken
        skip_priced: Whether to skip domains that already have pricing info
        batch_cooldown: Base delay between batches in seconds
        max_errors: Maximum total errors before aborting (None for no limit)
        max_consecutive_failures: Maximum consecutive failing batches before pausing
        batch_retries: Number of times to retry a failing batch
        save_progress: Whether to save a list of successfully processed domains
    """
    start_time = time.time()
    
    # Get API credentials
    api_key = os.getenv('NAMECHEAP_API_KEY')
    username = os.getenv('NAMECHEAP_USERNAME') 
    client_ip = os.getenv('CLIENT_IP')
    
    # Validate credentials
    if not all([api_key, username, client_ip]):
        missing = []
        if not api_key: missing.append("NAMECHEAP_API_KEY")
        if not username: missing.append("NAMECHEAP_USERNAME")
        if not client_ip: missing.append("CLIENT_IP")
        print(f"Error: Missing environment variables: {', '.join(missing)}")
        print("Please add these to your .env file")
        return
    
    api_credentials = {
        'api_key': api_key,
        'username': username,
        'client_ip': client_ip
    }
    
    print(f"Using Namecheap credentials for user: {username}")
    
    # Validate sort field
    valid_fields = ["average_score", "memorability", "pronunciation", "visual_appeal", "brandability"]
    if sort_field not in valid_fields:
        print(f"Invalid sort field: {sort_field}. Using 'average_score' instead.")
        sort_field = "average_score"
    
    # Connect to database
    conn = get_db_connection()
    ensure_price_columns_exist(conn)
    
    # Get domains to process using our helper function
    domains = get_domains_to_process(
        conn, 
        quantity=quantity, 
        sort_field=sort_field, 
        include_taken=include_taken, 
        skip_priced=skip_priced
    )
    
    total_domains = len(domains)
    if total_domains == 0:
        print("No domains to process.")
        conn.close()
        return
    
    print(f"Found {total_domains} domains to check")
    
    # Calculate number of batches
    total_batches = (total_domains + batch_size - 1) // batch_size
    print(f"Processing in {total_batches} batches of {batch_size} domains each")
    
    if max_price:
        print(f"Premium domains with price > ${max_price} will be marked as 'Filtered'")
    
    # Track results
    all_results = {
        'total': total_domains,
        'success': 0,
        'errors': 0,
        'error_types': {},
        'taken': 0,
        'premium': 0,
        'standard': 0,
        'filtered_premium': 0,
        'high_scores': [],
        'error_domains': [],  # Track domains with errors
        'success_domains': []  # Track successfully processed domains
    }
    
    # Create a progress bar
    pbar = tqdm(total=total_domains, desc="Checking Domain Prices")
    
    # Adaptive rate limiting
    consecutive_errors = 0
    current_delay = batch_cooldown
    
    # Process domains in batches
    async with aiohttp.ClientSession() as session:
        for i in range(0, total_domains, batch_size):
            batch = domains[i:i+batch_size]
            batch_num = i // batch_size + 1
            
            # Apply exponential backoff if we've had consecutive failures
            if consecutive_errors > 0:
                cooldown = current_delay * (2 ** min(consecutive_errors - 1, 5))  # Cap the exponential growth
                tqdm.write(f"\nCooldown: {cooldown:.1f}s due to {consecutive_errors} consecutive error batches...")
                await asyncio.sleep(cooldown)
            
            # Try the batch with multiple retries
            batch_success = False
            batch_results = None
            
            for attempt in range(batch_retries + 1):  # +1 for initial attempt
                if attempt > 0:
                    retry_delay = max(5, current_delay * (2 ** (attempt - 1)))
                    tqdm.write(f"Retrying batch {batch_num} (attempt {attempt}/{batch_retries}) after {retry_delay}s delay...")
                    await asyncio.sleep(retry_delay)
                
                # Use the progress bar only for the first attempt to avoid double-counting
                current_pbar = pbar if attempt == 0 else None
                
                batch_results = await process_domain_batch(
                    batch, session, api_credentials, conn, current_pbar, debug, max_price
                )
                
                # If we've processed at least half the batch successfully, consider it a success
                if batch_results['success'] >= len(batch) / 2:
                    batch_success = True
                    consecutive_errors = 0
                    break
                elif attempt < batch_retries:
                    tqdm.write(f"Batch {batch_num} had low success rate ({batch_results['success']}/{len(batch)}). Retrying...")
            
            # Even if all retries failed, we still process whatever results we got
            if not batch_success:
                consecutive_errors += 1
            
            # Update overall results
            all_results['success'] += batch_results['success']
            all_results['errors'] += batch_results['errors']
            all_results['taken'] += batch_results['taken']
            all_results['premium'] += batch_results['premium']
            all_results['standard'] += batch_results['standard']
            all_results['filtered_premium'] += batch_results['filtered_premium']
            all_results['high_scores'].extend(batch_results['high_scores'])
            all_results['error_domains'].extend(batch_results['error_domains'])
            all_results['success_domains'].extend(batch_results['success_domains'])
            
            # Track error types
            for error_type, count in batch_results.get('error_types', {}).items():
                all_results['error_types'][error_type] = all_results['error_types'].get(error_type, 0) + count
            
            # Show batch summary with error details
            tqdm.write(f"\nBatch {batch_num}/{total_batches} completed:")
            tqdm.write(f"  Success: {batch_results['success']}/{len(batch)}")
            tqdm.write(f"  Taken: {batch_results['taken']}")
            tqdm.write(f"  Premium: {batch_results['premium']}")
            tqdm.write(f"  Standard: {batch_results['standard']}")
            
            if batch_results['errors'] > 0:
                tqdm.write(f"  Errors: {batch_results['errors']}")
                for error_type, count in batch_results.get('error_types', {}).items():
                    tqdm.write(f"    - {error_type}: {count}")
            
            if max_price and batch_results['filtered_premium'] > 0:
                tqdm.write(f"  Filtered premium (>${max_price}): {batch_results['filtered_premium']}")
            
            # Save progress incrementally
            if save_progress and batch_results['success'] > 0:
                save_progress_file(all_results['success_domains'])
                
            # Adaptive delay based on error rate
            if consecutive_errors >= max_consecutive_failures:
                # Long cooldown after multiple consecutive failing batches
                long_cooldown = 60  # 1 minute
                tqdm.write(f"\nToo many consecutive errors ({consecutive_errors}). Pausing for {long_cooldown}s...")
                await asyncio.sleep(long_cooldown)
                consecutive_errors = 0  # Reset after long cooldown
                current_delay = batch_cooldown  # Reset delay
            elif consecutive_errors > 0:
                # Increase delay for each consecutive error batch
                current_delay = min(30, batch_cooldown * (2 ** (consecutive_errors - 1)))
            else:
                # Reset to base delay after success
                current_delay = batch_cooldown
            
            # Check if we've hit the maximum error threshold
            if max_errors and all_results['errors'] >= max_errors:
                tqdm.write(f"\nReached maximum error threshold ({max_errors}). Stopping.")
                break
            
            # Standard pause between batches to avoid rate limits
            if i + batch_size < total_domains:
                tqdm.write(f"Pausing for {current_delay}s before next batch...")
                await asyncio.sleep(current_delay)
    
    # Close progress bar
    pbar.close()
    
    # Get statistics on domains by price type
    cursor = conn.cursor()  # Add this line to define the cursor
    cursor.execute("""
        SELECT 
            price_type, 
            COUNT(*) as count,
            AVG(price) as avg_price,
            MIN(price) as min_price,
            MAX(price) as max_price
        FROM domain_results
        WHERE price_type IS NOT NULL
        GROUP BY price_type
    """)
    price_stats = cursor.fetchall()
    
    # Show summary
    duration = time.time() - start_time
    print("\n" + "="*60)
    print(f"DOMAIN PRICE CHECK COMPLETE in {duration:.1f} seconds")
    print("="*60)
    print(f"Total domains processed: {all_results['total']}")
    print(f"Successful updates: {all_results['success']}")
    print(f"Errors: {all_results['errors']}")
    
    # Show error breakdown
    if all_results['errors'] > 0:
        print("\nError breakdown:")
        for error_type, count in all_results['error_types'].items():
            print(f"  - {error_type}: {count}")
    
    print(f"\nDomains by status:")
    print(f"  - Not available: {all_results['taken']}")
    print(f"  - Premium domains: {all_results['premium']}")
    print(f"  - Standard domains: {all_results['standard']}")
    if max_price:
        print(f"  - Filtered premium (>${max_price}): {all_results['filtered_premium']}")
    
    print("\nPrice statistics by type:")
    for price_type, count, avg_price, min_price, max_price in price_stats:
        if price_type and price_type not in ('Taken', 'Error'):
            print(f"  {price_type}: {count} domains")
            if avg_price:
                print(f"    Avg: ${avg_price:.2f}")
                print(f"    Min: ${min_price:.2f}")
                print(f"    Max: ${max_price:.2f}")
    
    # Show top high-scoring domains
    if all_results['high_scores']:
        print("\nTop scoring available domains:")
        print(f"{'Domain':<30} {'Score':<6} {'Type':<10} {'Price':<10}")
        print("-" * 60)
        
        # Sort by score (secondary sort by price for equal scores)
        sorted_domains = sorted(all_results['high_scores'], 
                               key=lambda x: (x[1], -1 * (x[3] or 0)), 
                               reverse=True)
        
        for domain, score, price_type, price in sorted_domains[:10]:
            price_str = f"${price:.2f}" if price else "-"
            print(f"{domain:<30} {score:<6.1f} {price_type:<10} {price_str:<10}")
        
        if len(sorted_domains) > 10:
            print(f"...and {len(sorted_domains) - 10} more")
    
    # Show remaining domains with errors
    if all_results['error_domains']:
        print(f"\n{len(all_results['error_domains'])} domains had errors and will be retried next time.")
        if len(all_results['error_domains']) <= 10:
            print("Domains with errors:")
            for domain in all_results['error_domains']:
                print(f"  - {domain}")
        else:
            print(f"Sample of domains with errors (showing 10 of {len(all_results['error_domains'])}):")
            for domain in all_results['error_domains'][:10]:
                print(f"  - {domain}")
    
    # Save final progress
    if save_progress and all_results['success_domains']:
        save_progress_file(all_results['success_domains'])
        print(f"\nSaved progress with {len(all_results['success_domains'])} successfully processed domains")
    
    # Close connection
    conn.close()

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Update domain pricing information")
    
    parser.add_argument("-n", "--num-domains", type=int, default=50,
                       help="Number of domains to check (default: 50, 0 for all)")
    
    parser.add_argument("-b", "--batch-size", type=int, default=10,
                       help="Number of domains to process in each batch (default: 10)")
    
    parser.add_argument("-s", "--sort-field", type=str, default="average_score",
                       choices=["average_score", "memorability", "pronunciation", 
                               "visual_appeal", "brandability"],
                       help="Field to sort domains by (default: average_score)")
    
    parser.add_argument("-m", "--max-price", type=float, default=None,
                       help="Maximum price for premium domains (default: no limit)")
    
    parser.add_argument("-d", "--debug", action="store_true",
                       help="Save API responses for debugging")
    
    parser.add_argument("-a", "--all", action="store_true",
                       help="Include domains already marked as taken")
    
    parser.add_argument("-p", "--process-all", action="store_true",
                       help="Process all domains including those already priced")
    
    parser.add_argument("-c", "--cooldown", type=float, default=1.0,
                       help="Base cooldown between batches (default: 1.0 second)")
    
    parser.add_argument("-e", "--max-errors", type=int, default=None,
                       help="Maximum number of errors before stopping (default: no limit)")
    
    parser.add_argument("-f", "--max-failures", type=int, default=3,
                       help="Maximum consecutive failing batches before long pause (default: 3)")
    
    parser.add_argument("-r", "--retries", type=int, default=2,
                       help="Number of times to retry a failing batch (default: 2)")
    
    parser.add_argument("-no-save", action="store_false", dest="save_progress",
                       help="Disable saving progress to a file")
    
    return parser.parse_args()

if __name__ == "__main__":
    try:
        # Parse command line arguments
        args = parse_arguments()
        
        # Convert num_domains=0 to None (all domains)
        quantity = None if args.num_domains == 0 else args.num_domains
        
        # Run the price update process
        asyncio.run(update_domain_prices(
            quantity=quantity,
            sort_field=args.sort_field,
            batch_size=args.batch_size,
            max_price=args.max_price,
            debug=args.debug,
            include_taken=args.all,
            skip_priced=not args.process_all,
            batch_cooldown=args.cooldown,
            max_errors=args.max_errors,
            max_consecutive_failures=args.max_failures,
            batch_retries=args.retries,
            save_progress=args.save_progress
        ))
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
    except Exception as e:
        print(f"Unexpected error: {e}")
        traceback.print_exc()