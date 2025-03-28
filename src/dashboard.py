import os
import sqlite3
import pandas as pd
from flask import Flask, render_template, request, jsonify
import traceback  # For better error reporting

app = Flask(__name__, 
            static_folder='static',  # Specify the static folder
            template_folder='templates')  # Specify the template folder

# Increase Flask's logging level
import logging
logging.basicConfig(level=logging.DEBUG)

# Data directory handling
def get_data_dir():
    """Return the data directory path, creating it if needed"""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    os.makedirs(data_dir, exist_ok=True)
    print(f"Data directory: {data_dir}")
    return data_dir

# Database connection
def get_db_connection():
    db_path = os.path.join(get_data_dir(), 'domains.db')
    print(f"Trying to connect to database at: {db_path}")
    
    if not os.path.exists(db_path):
        print(f"WARNING: Database file not found at {db_path}")
        raise FileNotFoundError(f"Database file not found at {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        # Test the connection
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM domain_results")
        count = cursor.fetchone()[0]
        print(f"Successfully connected to database. Found {count} records.")
        return conn
    except Exception as e:
        print(f"ERROR connecting to database: {e}")
        traceback.print_exc()
        raise

def validate_static_files():
    """Check static files for potential issues"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    js_path = os.path.join(script_dir, 'static', 'js', 'dashboard.js')
    
    try:
        with open(js_path, 'r') as file:
            js_content = file.read()
            
        # Check for problematic characters or patterns
        if "].join('\n');" not in js_content:
            print("WARNING: JS file might be missing proper newline in CSV export function")
            
        # Check if the file has proper line endings
        if "\r\n" in js_content:
            print("NOTE: JS file uses Windows-style line endings (CRLF)")
        else:
            print("NOTE: JS file uses Unix-style line endings (LF)")
            
        # Check file encoding
        try:
            js_content.encode('ascii')
            print("JS file appears to be ASCII-compatible")
        except UnicodeEncodeError:
            print("WARNING: JS file contains non-ASCII characters")
            
    except Exception as e:
        print(f"Error validating static files: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/domains')
def get_domains():
    print("API request received for /api/domains")
    # Get query parameters for filtering and sorting
    sort_by = request.args.get('sort_by', 'average_score')
    sort_dir = request.args.get('sort_dir', 'desc')
    min_score = request.args.get('min_score', 0, type=float)
    tld_filter = request.args.get('tld', '')
    search = request.args.get('search', '')
    price_type = request.args.get('price_type', '')
    max_price = request.args.get('max_price', 0, type=float)
    
    print(f"Query params: sort_by={sort_by}, sort_dir={sort_dir}, min_score={min_score}, tld={tld_filter}, search={search}, price_type={price_type}, max_price={max_price}")
    
    try:
        # Connect to database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check for columns that exist in the table
        cursor.execute("PRAGMA table_info(domain_results)")
        columns = [col[1] for col in cursor.fetchall()]
        print(f"Database columns: {columns}")
        
        # Ensure we're only selecting columns that exist
        select_columns = ["domain", "memorability", "pronunciation", "visual_appeal", "brandability", "average_score"]
        
        # Add price columns if they exist
        if "price" in columns:
            select_columns.append("price")
        if "price_type" in columns:
            select_columns.append("price_type")
        if "error" in columns:
            select_columns.append("error")
        
        # Build the query dynamically
        query = f"""
            SELECT {', '.join(select_columns)}
            FROM domain_results
            WHERE average_score IS NOT NULL
        """
        
        params = []
        
        # Add filters
        if min_score > 0:
            query += " AND average_score >= ?"
            params.append(min_score)
        
        if tld_filter:
            query += " AND domain LIKE '%." + tld_filter + "'"
        
        if search:
            query += " AND domain LIKE ?"
            params.append(f"%{search}%")
        
        # Add price type filter
        if price_type:
            query += " AND price_type = ?"
            params.append(price_type)
        
        # Add max price filter
        if max_price > 0:
            query += " AND price <= ?"
            params.append(max_price)
        
        # Add sorting (with validation to prevent SQL injection)
        if sort_by in columns:
            query += f" ORDER BY {sort_by} {'DESC' if sort_dir.lower() == 'desc' else 'ASC'}"
        elif sort_by == 'price' and 'price' not in columns:
            # Fall back to average_score if price column doesn't exist
            query += f" ORDER BY average_score {'DESC' if sort_dir.lower() == 'desc' else 'ASC'}"
        else:
            # Default sort by average_score
            query += f" ORDER BY average_score {'DESC' if sort_dir.lower() == 'desc' else 'ASC'}"
        
        print(f"Executing query: {query} with params {params}")
        
        # Execute query
        cursor.execute(query, params)
        rows = cursor.fetchall()
        print(f"Query returned {len(rows)} rows")
        
        # Convert rows to dictionaries
        data = []
        for row in rows:
            row_dict = {key: row[key] for key in row.keys()}
            # Ensure price fields exist even if not in database
            if "price" not in row_dict:
                row_dict["price"] = None
            if "price_type" not in row_dict:
                row_dict["price_type"] = None
            data.append(row_dict)
        
        # Close the connection before returning response
        conn.close()
        return jsonify(data)
    except Exception as e:
        print(f"ERROR in /api/domains: {e}")
        traceback.print_exc()
        if 'conn' in locals():
            conn.close()
        return jsonify({"error": str(e), "message": "Error fetching data from database"}), 500

@app.route('/api/stats')
def get_stats():
    print("API request received for /api/stats")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check for columns that exist in the table
        cursor.execute("PRAGMA table_info(domain_results)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Get total domains
        total = conn.execute("SELECT COUNT(*) FROM domain_results").fetchone()[0]
        print(f"Total domains: {total}")
        
        # Get domains by TLD
        tlds_query = """
            SELECT 
                SUBSTR(domain, INSTR(domain, '.') + 1) as tld,
                COUNT(*) as count 
            FROM domain_results 
            GROUP BY SUBSTR(domain, INSTR(domain, '.') + 1)
        """
        tlds = [dict(row) for row in conn.execute(tlds_query).fetchall()]
        print(f"Found {len(tlds)} unique TLDs")
        
        # Build average scores query based on available columns
        avg_columns = ["memorability", "pronunciation", "visual_appeal", "brandability", "average_score"]
        avg_price_included = False
        
        if "price" in columns:
            avg_columns.append("price")
            avg_price_included = True
        
        avg_query = f"""
            SELECT 
                {', '.join([f'AVG({col}) as avg_{col}' for col in avg_columns])}
            FROM domain_results
            WHERE average_score IS NOT NULL
        """
        
        avg_scores = conn.execute(avg_query).fetchone()
        avg_dict = {f"avg_{key}": avg_scores[f"avg_{key}"] for key in avg_columns}
        
        # Get price statistics if the price column exists
        price_stats = []
        if "price" in columns and "price_type" in columns:
            try:
                price_stats_query = """
                    SELECT 
                        price_type, 
                        COUNT(*) as count,
                        AVG(price) as avg_price,
                        MIN(price) as min_price,
                        MAX(price) as max_price
                    FROM domain_results
                    WHERE price IS NOT NULL
                    GROUP BY price_type
                """
                price_stats = [dict(row) for row in conn.execute(price_stats_query).fetchall()]
            except Exception as e:
                print(f"Error fetching price stats: {e}")
                price_stats = []
        
        conn.close()
        
        result = {
            'total': total,
            'tlds': tlds,
            'averages': avg_dict,
            'price_stats': price_stats
        }
        return jsonify(result)
    except Exception as e:
        print(f"ERROR in /api/stats: {e}")
        traceback.print_exc()
        if 'conn' in locals():
            conn.close()
        return jsonify({"error": str(e), "message": "Error fetching stats"}), 500

@app.route('/api/debug')
def api_debug():
    """Debug endpoint to verify API functionality."""
    print("API request received for /api/debug")
    try:
        import sys
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM domain_results WHERE average_score IS NOT NULL")
        count = cursor.fetchone()['count']
        db_path = os.path.join(get_data_dir(), 'domains.db')
        
        # Get sample record
        sample = None
        try:
            cursor.execute("SELECT * FROM domain_results WHERE average_score IS NOT NULL LIMIT 1")
            row = cursor.fetchone()
            if row:
                sample = {key: row[key] for key in row.keys()}
        except Exception as e:
            print(f"Error fetching sample: {e}")
        
        result = {
            'database_path': db_path,
            'database_exists': os.path.exists(db_path),
            'database_size': os.path.getsize(db_path) if os.path.exists(db_path) else 0,
            'record_count': count,
            'python_version': sys.version,
            'sample_record': sample,
            'api_status': 'ok'
        }
        conn.close()
        return jsonify(result)
    except Exception as e:
        print(f"ERROR in /api/debug: {e}")
        traceback.print_exc()
        if 'conn' in locals():
            conn.close()
        result = {
            'error': str(e),
            'api_status': 'error',
            'database_path': os.path.join(get_data_dir(), 'domains.db')
        }
        return jsonify(result), 500

# Create templates directory and ensure static files exist
def ensure_template_and_static_files():
    """
    Create the necessary directories and files for the Flask app.
    """
    # Get the directory where the dashboard.py script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define directory paths
    templates_dir = os.path.join(script_dir, 'templates')
    static_dir = os.path.join(script_dir, 'static')
    css_dir = os.path.join(static_dir, 'css')
    js_dir = os.path.join(static_dir, 'js')
    
    # Create directories
    os.makedirs(templates_dir, exist_ok=True)
    os.makedirs(css_dir, exist_ok=True)
    os.makedirs(js_dir, exist_ok=True)
    
    print(f"Template directory: {templates_dir}")
    print(f"Static directory: {static_dir}")
    
    # Check if files exist
    index_path = os.path.join(templates_dir, 'index.html')
    css_path = os.path.join(css_dir, 'dashboard.css')
    js_path = os.path.join(js_dir, 'dashboard.js')
    
    print(f"Template exists: {os.path.exists(index_path)}")
    print(f"CSS exists: {os.path.exists(css_path)}")
    print(f"JS exists: {os.path.exists(js_path)}")

if __name__ == "__main__":
    # Ensure all required files exist
    ensure_template_and_static_files()
    
    # Validate static files
    validate_static_files()
    
    # Start the Flask app
    print("Dashboard ready! Starting server...")
    app.run(debug=True)