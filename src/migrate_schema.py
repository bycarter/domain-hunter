import os
import sqlite3
import sys

def get_data_directory():
    """Get the absolute path to the data directory."""
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

def migrate_database():
    """Migrate the database schema to include pricing columns without losing data."""
    # Connect to the database
    db_path = os.path.join(get_data_directory(), 'domains.db')
    
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        return False
    
    # Backup the database first
    import shutil
    backup_path = f"{db_path}.backup"
    print(f"Creating backup of database at {backup_path}")
    shutil.copy2(db_path, backup_path)
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check current schema
    cursor.execute("PRAGMA table_info(domain_results)")
    columns = cursor.fetchall()
    column_names = [col[1] for col in columns]
    
    print(f"Current database columns: {column_names}")
    
    # Add new columns if they don't exist
    new_columns = {
        'price': 'REAL',
        'price_type': 'TEXT',
        'pricing_data': 'TEXT'
    }
    
    columns_added = False
    for col_name, col_type in new_columns.items():
        if col_name not in column_names:
            print(f"Adding column: {col_name} ({col_type})")
            try:
                cursor.execute(f"ALTER TABLE domain_results ADD COLUMN {col_name} {col_type}")
                columns_added = True
            except sqlite3.OperationalError as e:
                print(f"Error adding column {col_name}: {e}")
    
    conn.commit()
    
    # Verify the changes
    cursor.execute("PRAGMA table_info(domain_results)")
    new_columns = cursor.fetchall()
    new_column_names = [col[1] for col in new_columns]
    
    print(f"Updated database columns: {new_column_names}")
    
    conn.close()
    
    if columns_added:
        print("Database migration completed successfully!")
    else:
        print("No changes needed - schema is already up to date.")
    
    return True

if __name__ == "__main__":
    try:
        migrate_database()
    except Exception as e:
        print(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)