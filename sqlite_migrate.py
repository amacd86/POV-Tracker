#!/usr/bin/env python3
import sqlite3
import os

def run_sqlite_migration():
    # Look for database file
    db_files = ['pov_tracker.db', 'instance/pov_tracker.db', 'app.db', 'instance/app.db']
    db_path = None
    
    for db_file in db_files:
        if os.path.exists(db_file):
            db_path = db_file
            break
    
    if not db_path:
        print("❌ Could not find database file!")
        print("Looking for: pov_tracker.db, instance/pov_tracker.db, app.db, instance/app.db")
        return False
    
    print(f"✅ Found database: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if povs table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='povs';")
        if not cursor.fetchone():
            print("❌ POVs table not found!")
            return False
        
        # Get current columns
        cursor.execute("PRAGMA table_info(povs);")
        existing_columns = [row[1] for row in cursor.fetchall()]
        print(f"Existing columns: {existing_columns}")
        
        # Define new columns to add
        new_columns = [
            ("customer_name", "VARCHAR(200) NOT NULL DEFAULT 'Contact Required'"),
            ("customer_email", "VARCHAR(200)"),
            ("sales_engineer", "VARCHAR(100)"),
            ("technical_win", "BOOLEAN DEFAULT 0"),
            ("roadblock_category", "VARCHAR(50)"),
            ("roadblock_severity", "VARCHAR(10)"),
            ("roadblock_owner", "VARCHAR(20)"),
            ("roadblock_notes", "TEXT"),
            ("roadblock_created_date", "DATE"),
            ("roadblock_resolved_date", "DATE"),
            ("notes", "TEXT")
        ]
        
        print(f"🚀 Adding new columns...")
        
        added_count = 0
        for column_name, column_definition in new_columns:
            if column_name not in existing_columns:
                try:
                    sql = f"ALTER TABLE povs ADD COLUMN {column_name} {column_definition}"
                    cursor.execute(sql)
                    print(f"✅ Added: {column_name}")
                    added_count += 1
                except sqlite3.Error as e:
                    print(f"❌ Error adding {column_name}: {e}")
            else:
                print(f"⏭️  {column_name} already exists")
        
        conn.commit()
        conn.close()
        
        print(f"🎉 Migration completed! Added {added_count} columns")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    print("POV TRACKER - DATABASE MIGRATION")
    print("=" * 40)
    run_sqlite_migration()
