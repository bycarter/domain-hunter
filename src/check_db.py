import os
import sqlite3

def check_database():
    """Check database structure and content to help diagnose issues."""
    # Connect to the database
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    db_path = os.path.join(data_dir, 'domains.db')
    
    if not os.path.exists(db_path):
        print(f"ERROR: Database file not found at {db_path}")
        return
    
    print(f"Database found at {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check schema
    print("\nTABLE SCHEMA:")
    cursor.execute("PRAGMA table_info(domain_results)")
    columns = cursor.fetchall()
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")
    
    # Check row count
    cursor.execute("SELECT COUNT(*) FROM domain_results")
    total = cursor.fetchone()[0]
    print(f"\nTotal rows: {total}")
    
    # Check scored domains
    cursor.execute("SELECT COUNT(*) FROM domain_results WHERE average_score IS NOT NULL")
    scored = cursor.fetchone()[0]
    print(f"Domains with scores: {scored}")
    
    # Check a sample row
    if total > 0:
        print("\nSAMPLE ROW:")
        cursor.execute("SELECT * FROM domain_results LIMIT 1")
        row = cursor.fetchone()
        column_names = [description[0] for description in cursor.description]
        for i, col_name in enumerate(column_names):
            print(f"  - {col_name}: {row[i]}")
    
    # Check if any rows would be returned by the dashboard query
    cursor.execute("SELECT COUNT(*) FROM domain_results WHERE average_score IS NOT NULL")
    dashboard_rows = cursor.fetchone()[0]
    print(f"\nRows that should appear in dashboard: {dashboard_rows}")
    
    conn.close()
    
    print("\nDATABASE DIAGNOSIS COMPLETE")
    if dashboard_rows == 0:
        print("ISSUE FOUND: No rows have average_score values - this is why the dashboard is empty.")
    elif dashboard_rows > 0:
        print("The database appears to have data that should display in the dashboard.")
        print("Try clearing your browser cache or accessing dashboard in a private/incognito window.")

if __name__ == "__main__":
    check_database()