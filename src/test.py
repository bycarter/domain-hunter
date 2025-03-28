# test_db.py
import os
import sqlite3

# Use the exact same path calculation as domain_pricing.py
data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
db_path = os.path.join(data_dir, 'domains.db')
print(f"Looking for database at: {db_path}")
print(f"File exists: {os.path.exists(db_path)}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Test basic connection
cursor.execute("SELECT COUNT(*) FROM domain_results")
total = cursor.fetchone()[0]
print(f"Total domains: {total}")

# Test the exact query used in get_domains_to_process
query = """
    SELECT domain FROM domain_results 
    WHERE average_score IS NOT NULL
    AND (price_type IS NULL OR price_type = 'Error')
    ORDER BY average_score DESC
    LIMIT 20
"""
print(f"Executing query: {query}")
cursor.execute(query)
domains = cursor.fetchall()

print(f"Found {len(domains)} domains to process:")
for domain in domains:
    print(f"- {domain[0]}")

# Check for schema issues:
cursor.execute("SELECT COUNT(*) FROM domain_results WHERE price_type = ''")
empty_string = cursor.fetchone()[0]
print(f"Domains with empty string price_type: {empty_string}")

cursor.execute("SELECT COUNT(*) FROM domain_results WHERE price_type = 'NULL'")
string_null = cursor.fetchone()[0]
print(f"Domains with 'NULL' string as price_type: {string_null}")

conn.close()