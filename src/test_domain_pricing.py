import os
import requests
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
import traceback  # For detailed error tracing

# Load environment variables
load_dotenv()

# API credentials
api_key = os.getenv('NAMECHEAP_API_KEY')
username = os.getenv('NAMECHEAP_USERNAME')
client_ip = os.getenv('CLIENT_IP')

# Validate credentials before proceeding
if not all([api_key, username, client_ip]):
    missing = []
    if not api_key: missing.append("NAMECHEAP_API_KEY")
    if not username: missing.append("NAMECHEAP_USERNAME")
    if not client_ip: missing.append("CLIENT_IP")
    print(f"Error: Missing environment variables: {', '.join(missing)}")
    exit(1)

print(f"Using credentials:")
print(f"  Username: {username}")
print(f"  API Key: {api_key[:5]}...{api_key[-5:]} (hidden middle)")
print(f"  Client IP: {client_ip}")

def check_domain_standard_api(domain):
    """Check domain using the standard availability API."""
    print(f"\n===== Checking domain with standard API: {domain} =====")
    
    check_url = "https://api.namecheap.com/xml.response"
    check_params = {
        "ApiUser": username,
        "ApiKey": api_key,
        "UserName": username,
        "ClientIp": client_ip,
        "Command": "namecheap.domains.check",
        "DomainList": domain
    }
    
    print(f"Sending availability check request to: {check_url}")
    
    try:
        response = requests.get(check_url, params=check_params)
        print(f"Response status code: {response.status_code}")
        
        # Save the raw response for debugging
        file_name = "standard_check_response.xml"
        with open(file_name, "w") as f:
            f.write(response.text)
        print(f"Raw response saved to {file_name}")
        
        # Parse XML response
        root = ET.fromstring(response.text)
        namespace = {'nc': 'http://api.namecheap.com/xml.response'}
        
        # Check API status
        api_status = root.attrib.get('Status', 'ERROR')
        print(f"API status: {api_status}")
        
        # Parse domain check result
        domain_check = root.find('.//nc:DomainCheckResult', namespaces=namespace)
        if domain_check is None:
            domain_check = root.find('.//DomainCheckResult')
            
        if domain_check is not None:
            print("Standard API DomainCheckResult attributes:")
            for key, value in domain_check.attrib.items():
                print(f"  {key}: {value}")
            
            available = domain_check.attrib.get('Available', 'false').lower() == 'true'
            is_premium = domain_check.attrib.get('IsPremiumName', 'false').lower() == 'true'
            
            result = {
                'available': available,
                'is_premium': is_premium,
                'raw_attributes': domain_check.attrib
            }
            return result
        else:
            print("No DomainCheckResult found in standard API response")
            return None
            
    except Exception as e:
        print(f"Exception in standard API check: {str(e)}")
        traceback.print_exc()
        return None

def check_domain_marketplace_api(domain):
    """Check domain using the marketplace API."""
    print(f"\n===== Checking domain with marketplace API: {domain} =====")
    
    check_url = "https://api.namecheap.com/xml.response"
    check_params = {
        "ApiUser": username,
        "ApiKey": api_key,
        "UserName": username,
        "ClientIp": client_ip,
        "Command": "namecheap.domains.marketplace.check",
        "DomainList": domain
    }
    
    print(f"Sending marketplace check request to: {check_url}")
    
    try:
        response = requests.get(check_url, params=check_params)
        print(f"Response status code: {response.status_code}")
        
        # Save the raw response for debugging
        file_name = "marketplace_check_response.xml"
        with open(file_name, "w") as f:
            f.write(response.text)
        print(f"Raw response saved to {file_name}")
        
        # Parse XML response
        root = ET.fromstring(response.text)
        namespace = {'nc': 'http://api.namecheap.com/xml.response'}
        
        # Check API status
        api_status = root.attrib.get('Status', 'ERROR')
        print(f"API status: {api_status}")
        
        # Look for relevant elements in the response
        command_response = root.find('.//nc:CommandResponse', namespaces=namespace)
        if command_response is None:
            command_response = root.find('.//CommandResponse')
            
        if command_response is not None:
            print("Marketplace API CommandResponse attributes:")
            for key, value in command_response.attrib.items():
                print(f"  {key}: {value}")
            
            # Parse all child elements and attributes
            print("Marketplace API response details:")
            for child in command_response:
                print(f"  Element: {child.tag}")
                for key, value in child.attrib.items():
                    print(f"    {key}: {value}")
            
            return {
                'command_response': command_response.attrib,
                'full_response': response.text
            }
        else:
            print("No CommandResponse found in marketplace API response")
            return None
            
    except Exception as e:
        print(f"Exception in marketplace API check: {str(e)}")
        traceback.print_exc()
        return None

def check_premium_domain_price(domain):
    """Check domain using the premium domain price API."""
    print(f"\n===== Checking domain with premium price API: {domain} =====")
    
    check_url = "https://api.namecheap.com/xml.response"
    check_params = {
        "ApiUser": username,
        "ApiKey": api_key,
        "UserName": username,
        "ClientIp": client_ip,
        "Command": "namecheap.domains.getPremiumDomainPrice",
        "DomainName": domain
    }
    
    print(f"Sending premium price check request to: {check_url}")
    
    try:
        response = requests.get(check_url, params=check_params)
        print(f"Response status code: {response.status_code}")
        
        # Save the raw response for debugging
        file_name = "premium_price_response.xml"
        with open(file_name, "w") as f:
            f.write(response.text)
        print(f"Raw response saved to {file_name}")
        
        # Parse XML response
        root = ET.fromstring(response.text)
        namespace = {'nc': 'http://api.namecheap.com/xml.response'}
        
        # Check API status
        api_status = root.attrib.get('Status', 'ERROR')
        print(f"API status: {api_status}")
        
        # Look for relevant elements in the response
        command_response = root.find('.//nc:CommandResponse', namespaces=namespace)
        if command_response is None:
            command_response = root.find('.//CommandResponse')
            
        if command_response is not None:
            print("Premium Price API CommandResponse attributes:")
            for key, value in command_response.attrib.items():
                print(f"  {key}: {value}")
            
            # Parse all child elements and attributes
            print("Premium Price API response details:")
            for child in command_response:
                print(f"  Element: {child.tag}")
                for key, value in child.attrib.items():
                    print(f"    {key}: {value}")
            
            return {
                'command_response': command_response.attrib,
                'full_response': response.text
            }
        else:
            print("No CommandResponse found in premium price API response")
            return None
            
    except Exception as e:
        print(f"Exception in premium price API check: {str(e)}")
        traceback.print_exc()
        return None

def get_tld_price(tld):
    """Get the standard price for a TLD."""
    print(f"\n----- Getting standard price for TLD: .{tld} -----")
    
    # Step 2: Get pricing for the TLD
    pricing_url = "https://api.namecheap.com/xml.response"
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
    
    print(f"Sending pricing request to: {pricing_url}")
    
    try:
        response = requests.get(pricing_url, params=pricing_params)
        print(f"Response status code: {response.status_code}")
        
        # Save the raw response for debugging
        file_name = f"tld_pricing_{tld}_response.xml"
        with open(file_name, "w") as f:
            f.write(response.text)
        print(f"Raw response saved to {file_name}")
        
        # Parse XML
        root = ET.fromstring(response.text)
        namespace = {'nc': 'http://api.namecheap.com/xml.response'}
        
        # Check API status
        api_status = root.attrib.get('Status', 'ERROR')
        print(f"API status: {api_status}")
        
        # Try different paths to find the price element
        price_paths = [
            f".//nc:Product[@Name='{tld}']/nc:Price[@Duration='1']",
            f".//Product[@Name='{tld}']/Price[@Duration='1']",
            ".//nc:Price[@Duration='1']",
            ".//Price[@Duration='1']"
        ]
        
        price_elem = None
        for path in price_paths:
            try:
                if "nc:" in path:
                    price_elem = root.find(path, namespaces=namespace)
                else:
                    price_elem = root.find(path)
                if price_elem is not None:
                    break
            except:
                continue
                
        if price_elem is not None:
            print("TLD Pricing attributes:")
            for key, value in price_elem.attrib.items():
                print(f"  {key}: {value}")
                
            price = price_elem.attrib.get('Price', '0')
            return float(price)
        else:
            print("Could not find price element in response")
            return get_standard_price_for_tld(tld)
            
    except Exception as e:
        print(f"Exception in get_tld_price: {str(e)}")
        traceback.print_exc()
        return get_standard_price_for_tld(tld)

def get_standard_price_for_tld(tld):
    """Return standard pricing for common TLDs as fallback."""
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
    price = standard_prices.get(tld.lower(), 14.98)
    print(f"Using fallback price for .{tld}: ${price}")
    return price

if __name__ == "__main__":
    print("==================================================")
    print("NAMECHEAP DOMAIN PRICING TEST (MULTIPLE APIs)")
    print("==================================================")
    
    test_domain = input("Enter a domain to check (e.g., example.com): ")
    
    # Run all three API checks
    standard_result = check_domain_standard_api(test_domain)
    marketplace_result = check_domain_marketplace_api(test_domain)
    premium_result = check_premium_domain_price(test_domain)
    
    # Get TLD price as fallback
    tld = test_domain.split('.')[-1]
    standard_tld_price = get_tld_price(tld)
    
    print("\n==================================================")
    print("SUMMARY OF RESULTS:")
    print("==================================================")
    
    print(f"\nDomain: {test_domain}")
    
    if standard_result:
        print("\nStandard API:")
        available = standard_result.get('available', False)
        is_premium = standard_result.get('is_premium', False)
        print(f"  Available: {available}")
        print(f"  Is Premium: {is_premium}")
        
        if is_premium and 'raw_attributes' in standard_result:
            attrs = standard_result['raw_attributes']
            if 'PremiumRegistrationPrice' in attrs:
                print(f"  Premium Registration Price: ${attrs['PremiumRegistrationPrice']}")
                
    if marketplace_result:
        print("\nMarketplace API:")
        print("  Response received - see marketplace_check_response.xml for details")
        
    if premium_result:
        print("\nPremium Price API:")
        print("  Response received - see premium_price_response.xml for details")
        
    print(f"\nStandard TLD Price for .{tld}: ${standard_tld_price}")
    
    print("\n==================================================")
    print("CONCLUSION:")
    
    # Try to make a determination based on all API results
    if standard_result and standard_result.get('available', False):
        print(f"Domain {test_domain} is AVAILABLE as a standard domain")
        price = standard_tld_price
        
        if standard_result.get('is_premium', False):
            attrs = standard_result.get('raw_attributes', {})
            if 'PremiumRegistrationPrice' in attrs and attrs['PremiumRegistrationPrice'] != '0':
                price = float(attrs['PremiumRegistrationPrice'])
                print(f"Domain {test_domain} is a PREMIUM domain with price: ${price}")
    else:
        print(f"Domain {test_domain} is reported as NOT AVAILABLE in standard API")
        
        # Check if we found it in the marketplace or premium API
        marketplace_available = False
        premium_available = False
        
        # Add custom logic here based on API responses
        
        if marketplace_available:
            print("Domain was found in MARKETPLACE")
        elif premium_available:
            print("Domain was found in PREMIUM catalog")
        else:
            print("Domain is likely already registered or reserved")
    
    print("==================================================")
    print("Check the saved XML files for detailed API responses")