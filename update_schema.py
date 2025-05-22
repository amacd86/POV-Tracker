from app import app, db
import sqlite3

def update_schema():
    with app.app_context():
        try:
            # Check if columns exist
            conn = sqlite3.connect('pov_tracker.db')
            cursor = conn.cursor()
            
            # Get column info for povs table
            cursor.execute("PRAGMA table_info(povs)")
            columns = [col[1] for col in cursor.fetchall()]
            
            # Add columns if they don't exist
            if 'deleted' not in columns:
                print("Adding 'deleted' column to povs table...")
                cursor.execute('ALTER TABLE povs ADD COLUMN deleted BOOLEAN DEFAULT 0')
                print("Column added successfully!")
            else:
                print("'deleted' column already exists")
                
            if 'deleted_at' not in columns:
                print("Adding 'deleted_at' column to povs table...")
                cursor.execute('ALTER TABLE povs ADD COLUMN deleted_at DATETIME')
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