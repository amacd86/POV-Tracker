# fix_database.py
# Run this script to add the missing price column to your existing database

import sqlite3
import os

# Path to your database file
db_path = '/home/frznlogr/POV-Tracker/pov_tracker.db'

# Alternative paths to check
possible_paths = [
    '/home/frznlogr/POV-Tracker/pov_tracker.db',
    '/home/frznlogr/pov_tracker.db',
    '/home/frznlogr/POV-Tracker/instance/pov_tracker.db'
]

def find_database():
    """Find the database file"""
    for path in possible_paths:
        if os.path.exists(path):
            print(f"Found database at: {path}")
            return path
    return None

def add_price_column():
    """Add the price column to the povs table"""
    db_path = find_database()
    
    if not db_path:
        print("No database file found. The app will create a new one automatically.")
        return
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if price column already exists
        cursor.execute("PRAGMA table_info(povs)")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]
        
        if 'price' not in column_names:
            print("Adding 'price' column to povs table...")
            cursor.execute('ALTER TABLE povs ADD COLUMN price FLOAT;')
            conn.commit()
            print("✓ Price column added successfully!")
        else:
            print("✓ Price column already exists.")
        
        # Verify the column was added
        cursor.execute("PRAGMA table_info(povs)")
        columns = cursor.fetchall()
        print("\nCurrent table structure:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
        
        conn.close()
        print("\n✓ Database update completed successfully!")
        print("You can now reload your web app on PythonAnywhere.")
        
    except Exception as e:
        print(f"Error: {e}")
        print("If this doesn't work, you may need to delete the old database and start fresh.")

if __name__ == "__main__":
    add_price_column()