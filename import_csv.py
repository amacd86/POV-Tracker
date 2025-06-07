import csv
import sys
from datetime import datetime, timedelta
from app import app, db, POV, Note

def clean_date(date_str):
    """Convert various date formats to datetime object"""
    if not date_str or date_str.strip() == '' or date_str.strip() == 'N/A':
        return None
    
    # Try different date formats
    formats = ['%m/%d/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m-%d-%Y']
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    print(f"Warning: Could not parse date '{date_str}', using None instead.")
    return None

def clean_amount(amount_str):
    """Clean and convert amount string to float"""
    if not amount_str or amount_str.strip() == '' or amount_str.strip() == 'N/A':
        return None
    cleaned = amount_str.replace('$', '').replace(',', '').replace(' ', '')
    try:
        return float(cleaned)
    except ValueError:
        print(f"Warning: Could not parse amount '{amount_str}', using None instead.")
        return None

def map_status(win_loss, technical_win, pov_stage):
    """Map CSV status fields to database status"""
    if not win_loss or win_loss.strip() == '':
        # If no win/loss, determine from stage and technical win
        if pov_stage and pov_stage.strip().lower() == 'completed':
            return 'Closed Won' if technical_win and technical_win.strip().lower() == 'yes' else 'In Trial'
        return 'In Trial'
    
    win_loss = win_loss.strip().lower()
    if win_loss in ['closed won', 'won', 'win']:
        return 'Closed Won'
    elif win_loss in ['closed lost', 'lost', 'loss']:
        return 'Closed Lost'
    elif win_loss in ['pending sales', 'pending']:
        return 'Pending Sales'
    elif win_loss in ['in trial', 'trial']:
        return 'In Trial'
    elif win_loss in ['on hold', 'hold']:
        return 'On Hold'
    else:
        return 'In Trial'

def map_stage(pov_stage):
    """Map CSV POV Stage to database stage"""
    if not pov_stage or pov_stage.strip() == '':
        return 'Deployment'
    
    stage = pov_stage.strip()
    stage_mapping = {
        'Deployment': 'Deployment',
        'Training 1': 'Training 1',
        'Training 2': 'Training 2',
        'POV Wrap-Up': 'POV Wrap-Up',
        'Completed': 'Completed',
        'Troubleshooting': 'Deployment'  # Map troubleshooting back to deployment
    }
    return stage_mapping.get(stage, 'Deployment')

def to_boolean(value):
    """Converts a string to a boolean value, handling non-boolean strings."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False  # Default for None
    val = str(value).strip().lower()
    if val in ('yes', 'true', 't', 'y', '1'):
        return True
    # Everything else, including 'no', 'pending', '', etc., will be False.
    return False

def map_technical_win(technical_win):
    """Map CSV Technical Win to database technical_win (boolean)"""
    return to_boolean(technical_win)

def import_csv_data(csv_file):
    """Import POVs and Notes from a CSV file"""
    with app.app_context():
        # Track statistics
        povs_added = 0
        notes_added = 0
        errors = 0
        
        print(f"Starting import from {csv_file}...")
        
        # Try different encodings
        encodings = ['utf-8-sig', 'utf-8', 'cp1252', 'iso-8859-1', 'latin1']
        csv_reader = None
        f = None
        
        for encoding in encodings:
            try:
                print(f"Trying encoding: {encoding}")
                f = open(csv_file, 'r', encoding=encoding)
                csv_reader = csv.DictReader(f)
                # Test if we can read the header
                if csv_reader.fieldnames:
                    print(f"✅ Successfully opened with encoding: {encoding}")
                    break
            except UnicodeDecodeError as e:
                print(f"❌ Failed with {encoding}: {e}")
                if f:
                    f.close()
                continue
            except Exception as e:
                print(f"❌ Error with {encoding}: {e}")
                if f:
                    f.close()
                continue
        
        if not csv_reader:
            print("Error: Could not read CSV file with any encoding")
            return False
        
        try:
            # Print detected columns for troubleshooting
            if csv_reader.fieldnames:
                print(f"Detected columns: {', '.join(csv_reader.fieldnames)}")
            
            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 since row 1 is headers
                try:
                    # Skip completely empty rows
                    if not any(row.values()):
                        continue
                    
                    # Extract and clean data from CSV columns
                    deal_name = row.get('Deal Name', '').strip() or row.get('', '').strip()  # First column
                    if not deal_name:
                        print(f"Row {row_num}: Skipping row without deal name")
                        continue
                    
                    # Get other fields
                    assigned_ae = row.get('Account Executive', '').strip()
                    assigned_se = row.get('Sales Engineer', '').strip()
                    
                    # Handle dates
                    start_date = clean_date(row.get('POV Start Date', ''))
                    complete_date = clean_date(row.get('POV Complete Date', ''))
                    close_date = clean_date(row.get('Close Date', ''))
                    
                    # If no start date, use today
                    if not start_date:
                        start_date = datetime.now().date()
                    
                    # Use complete date as projected end, or add 30 days to start
                    if complete_date:
                        projected_end_date = complete_date
                    else:
                        projected_end_date = start_date + timedelta(days=30)
                    
                    # Map other fields
                    current_stage = map_stage(row.get('POV Stage', ''))
                    status = map_status(row.get('Win/Loss', ''), row.get('Technical Win', ''), row.get('POV Stage', ''))
                    technical_win = map_technical_win(row.get('Technical Win', ''))
                    
                    # Handle amount
                    deal_amount = clean_amount(row.get('Amount', ''))
                    
                    # Handle text fields
                    success_criteria = row.get('Success Criteria', '').strip()
                    roadblocks = row.get('Roadblocks', '').strip()
                    win_loss_reason = row.get('Reason', '').strip()
                    
                    # Handle roadblock resolution
                    roadblock_removed = row.get('Roadblock Removed', '').strip()
                    overcome_roadblocks = roadblock_removed.lower() in ['yes', 'y', 'true', '1'] if roadblock_removed else False
                    roadblock_resolution = roadblock_removed if roadblock_removed and roadblock_removed.lower() not in ['yes', 'no', 'y', 'n'] else ''
                    
                    # Set default values for required fields
                    if not assigned_se:
                        assigned_se = 'Angus MacDonald'  # Default SE
                    if not assigned_ae:
                        assigned_ae = 'Rob Lynch'  # Default AE
                    
                    # Create POV record
                    pov = POV(
                        deal_name=deal_name,
                        assigned_se=assigned_se,
                        assigned_ae=assigned_ae,
                        start_date=start_date,
                        projected_end_date=projected_end_date,
                        actual_completion_date=complete_date,
                        current_stage=current_stage,
                        roadblocks=roadblocks,
                        overcome_roadblocks=overcome_roadblocks,
                        status=status,
                        deal_amount=deal_amount,
                        success_criteria=success_criteria,
                        technical_win=technical_win,
                        roadblock_resolution=roadblock_resolution,
                        win_loss_reason=win_loss_reason,
                        deleted=False
                    )
                    
                    db.session.add(pov)
                    db.session.flush()  # Get the POV ID
                    povs_added += 1
                    
                    # Create note from additional info if it exists
                    note_parts = []
                    if win_loss_reason:
                        note_parts.append(f"Reason: {win_loss_reason}")
                    if close_date:
                        note_parts.append(f"Close Date: {close_date}")
                    
                    if note_parts:
                        note_content = "\n\n".join(note_parts)
                        note = Note(
                            content=note_content,
                            pov_id=pov.id,
                            timestamp=datetime.now()
                        )
                        db.session.add(note)
                        notes_added += 1
                    
                    print(f"Row {row_num}: Successfully imported {deal_name}")
                    
                except Exception as e:
                    print(f"Row {row_num}: Error importing row: {str(e)}")
                    print(f"Row data: {row}")
                    errors += 1
                    continue
            
            # Commit all changes
            try:
                db.session.commit()
                print(f"\nImport complete!")
                print(f"✅ {povs_added} POVs added")
                print(f"✅ {notes_added} notes added") 
                print(f"❌ {errors} errors")
                return True
            except Exception as e:
                db.session.rollback()
                print(f"Error committing to database: {str(e)}")
                return False
        
        finally:
            if f:
                f.close()

if __name__ == "__main__":
    # Check if a CSV file was provided
    if len(sys.argv) < 2:
        print("Usage: python import_csv.py <path_to_csv_file>")
        print("Example: python import_csv.py data.csv")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    
    # Check if file exists
    import os
    if not os.path.exists(csv_file):
        print(f"Error: File '{csv_file}' not found!")
        sys.exit(1)
    
    success = import_csv_data(csv_file)
    if success:
        print("Import completed successfully!")
    else:
        print("Import failed!")
        sys.exit(1)
