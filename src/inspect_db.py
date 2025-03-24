import sqlite3
import os
import pandas as pd

def get_data_directory():
    """Get the absolute path to the data directory."""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    return data_dir

def inspect_database():
    # Connect to the database
    db_path = os.path.join(get_data_directory(), 'domains.db')
    conn = sqlite3.connect(db_path)
    
    # Query for error samples
    print("Sampling error messages from the database:")
    c = conn.cursor()
    c.execute("SELECT domain, error FROM domain_results WHERE error IS NOT NULL LIMIT 10")
    
    for domain, error in c.fetchall():
        print(f"{domain}: {error}")
    
    # Check for common error patterns
    c.execute("SELECT error, COUNT(*) FROM domain_results GROUP BY error ORDER BY COUNT(*) DESC LIMIT 5")
    print("\nMost common errors:")
    for error, count in c.fetchall():
        print(f"- {error}: {count} occurrences")
    
    # Check raw JSON responses
    c.execute("SELECT domain, raw_json FROM domain_results WHERE raw_json IS NOT NULL LIMIT 3")
    print("\nSample raw JSON responses:")
    for domain, raw_json in c.fetchall():
        print(f"{domain}: {raw_json}")
    
    # Get score statistics if any
    c.execute("SELECT COUNT(*) FROM domain_results WHERE average_score IS NOT NULL")
    scored_count = c.fetchone()[0]
    
    if scored_count > 0:
        c.execute("SELECT AVG(average_score) FROM domain_results WHERE average_score IS NOT NULL")
        avg = c.fetchone()[0]
        print(f"\nFound {scored_count} domains with scores. Average score: {avg:.2f}")
    else:
        print("\nNo domains with scores found.")
    
    conn.close()

if __name__ == "__main__":
    inspect_database()