# Database Migration Script for Phase 1 Enhancements
# Run this script to add missing fields to your existing POV table

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
import os

def run_migration(app, db):
    """
    Add missing columns to the POV table for Phase 1 enhancements
    """
    
    with app.app_context():
        try:
            # Get current columns to see what's missing
            result = db.engine.execute(text("PRAGMA table_info(povs)"))
            existing_columns = [row[1] for row in result.fetchall()]
            
            print(f"Existing columns: {existing_columns}")
            
            # Define new columns to add
            new_columns = [
                ("customer_name", "VARCHAR(200) NOT NULL DEFAULT ''"),
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
            
            # Add missing columns
            for column_name, column_definition in new_columns:
                if column_name not in existing_columns:
                    try:
                        sql = f"ALTER TABLE povs ADD COLUMN {column_name} {column_definition}"
                        db.engine.execute(text(sql))
                        print(f"✅ Added column: {column_name}")
                    except Exception as e:
                        print(f"❌ Error adding {column_name}: {e}")
                else:
                    print(f"⏭️  Column {column_name} already exists")
            
            # Commit the changes
            db.session.commit()
            print("\n🎉 Migration completed successfully!")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            db.session.rollback()

# If running this script directly
if __name__ == "__main__":
    # Import your app and db
    from app import app, db
    
    print("Starting Phase 1 database migration...")
    run_migration(app, db)
    print("Migration complete!")

# Alternative: Manual SQL commands if you prefer to run them directly
"""
-- Run these SQL commands in your database if you prefer manual migration:

ALTER TABLE povs ADD COLUMN customer_name VARCHAR(200) NOT NULL DEFAULT '';
ALTER TABLE povs ADD COLUMN customer_email VARCHAR(200);
ALTER TABLE povs ADD COLUMN sales_engineer VARCHAR(100);
ALTER TABLE povs ADD COLUMN technical_win BOOLEAN DEFAULT 0;
ALTER TABLE povs ADD COLUMN roadblock_category VARCHAR(50);
ALTER TABLE povs ADD COLUMN roadblock_severity VARCHAR(10);
ALTER TABLE povs ADD COLUMN roadblock_owner VARCHAR(20);
ALTER TABLE povs ADD COLUMN roadblock_notes TEXT;
ALTER TABLE povs ADD COLUMN roadblock_created_date DATE;
ALTER TABLE povs ADD COLUMN roadblock_resolved_date DATE;
ALTER TABLE povs ADD COLUMN notes TEXT;

-- Update existing records to have customer_name populated
UPDATE povs SET customer_name = 'Contact Name Required' WHERE customer_name = '';
"""
