import sqlite3

def update_schema():
    try:
        # Connect to the database
        conn = sqlite3.connect('instance/pov_tracker.db')
        cursor = conn.cursor()
        
        # Get table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = cursor.fetchall()
        
        # Look for POV table (might be named 'pov' or 'povs')
        pov_table = None
        for table in tables:
            if table[0].lower() in ['pov', 'povs']:
                pov_table = table[0]
                break
        
        if not pov_table:
            print("POV table not found. Available tables:")
            for table in tables:
                print(f"- {table[0]}")
            return
        
        print(f"Found POV table: {pov_table}")
        
        # Get columns for the POV table
        cursor.execute(f"PRAGMA table_info({pov_table})")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Add columns if they don't exist
        if 'deleted' not in columns:
            print(f"Adding 'deleted' column to {pov_table} table...")
            cursor.execute(f'ALTER TABLE {pov_table} ADD COLUMN deleted BOOLEAN DEFAULT 0')
            print("Column added successfully!")
        else:
            print("'deleted' column already exists")
            
        if 'deleted_at' not in columns:
            print(f"Adding 'deleted_at' column to {pov_table} table...")
            cursor.execute(f'ALTER TABLE {pov_table} ADD COLUMN deleted_at DATETIME')
            print("Column added successfully!")
        else:
            print("'deleted_at' column already exists")
        
        # Commit changes and close connection
        conn.commit()
        conn.close()
        
        print("Schema update complete!")
        
    except Exception as e:
        print(f"Error updating schema: {str(e)}")

if __name__ == "__main__":
    update_schema()
