# migrations.py
# Run this script to add the price column to the existing database
import os
import sqlite3
from datetime import datetime

# Get the absolute path to the database file
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'instance', 'pov_tracker.db')

# Ensure the instance directory exists
os.makedirs(os.path.join(basedir, 'instance'), exist_ok=True)

def add_price_column():
    print(f"Connecting to database at: {db_path}")
    
    # Only proceed if the database file exists
    if not os.path.exists(db_path):
        print(f"Database file not found at {db_path}")
        print("Please run the application first to create the initial database.")
        return

    conn = None
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
            print("Column added successfully!")
        else:
            print("'price' column already exists in povs table.")
        
        # Check if the analytics route is available
        # This is just a placeholder, as SQLite doesn't allow checking for route existence
        print("Migration complete! The price field is now available in the POV Tracker.")
        print("Please restart your Flask application to see the changes.")
        
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    add_price_column()