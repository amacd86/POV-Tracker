import sqlite3

def check_database():
    # Connect to the database
    conn = sqlite3.connect('instance/pov_tracker.db')
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    print("Tables in database:")
    for table in tables:
        print(f"- {table[0]}")
        
        # Get columns for each table
        cursor.execute(f"PRAGMA table_info({table[0]})")
        columns = cursor.fetchall()
        print("  Columns:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
        
    # Close the connection
    conn.close()

if __name__ == "__main__":
    check_database()
