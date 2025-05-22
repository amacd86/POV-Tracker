import csv
import sys
from datetime import datetime
from app import app, db
from models import POV, Note

def clean_date(date_str):
    """Convert various date formats to datetime object"""
    if not date_str or date_str.strip() == '':
        return datetime.now().date()
    
    # Try different date formats
    formats = ['%m/%d/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m-%d-%Y']
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    
    # If all formats fail, return today's date
    print(f"Warning: Could not parse date '{date_str}', using today's date instead.")
    return datetime.now().date()

def import_csv(csv_file):
    """Import POVs and Notes from a CSV file"""
    with app.app_context():
        # Track statistics
        povs_added = 0
        notes_added = 0
        errors = 0
        
        print(f"Starting import from {csv_file}...")
        
        with open(csv_file, 'r', encoding='cp1252') as f:  # Using cp1252 encoding as per your file
            csv_reader = csv.DictReader(f)
            
            # Print detected columns for troubleshooting
            if csv_reader.fieldnames:
                print(f"Detected columns: {', '.join(csv_reader.fieldnames)}")
            
            for row in csv_reader:
                try:
                    # Map CSV columns to model fields based on your specific columns
                    customer_name = row.get('Deal Name', '').strip()
                    assigned_se = row.get('Sales Engineer', '').strip()
                    assigned_ae = row.get('Account Executive', '').strip()
                    
                    # Handle dates
                    start_date_str = row.get('POV Start Date', '')
                    end_date_str = row.get('POV Complete Date', '')
                    
                    start_date = clean_date(start_date_str)
                    end_date = clean_date(end_date_str)
                    
                    # Handle stage
                    stage = row.get('POV Stage', '').strip()
                    valid_stages = ['Deployment', 'Training 1', 'Training 2', 'Wrap-Up', 'Tech Call']
                    # Map your stages to our valid stages
                    stage_mapping = {
                        'Deployment': 'Deployment',
                        'Training': 'Training 1',
                        'Training 1': 'Training 1',
                        'Training 2': 'Training 2',
                        'Wrap-Up': 'Wrap-Up',
                        'Tech Call': 'Tech Call'
                    }
                    current_stage = stage_mapping.get(stage, 'Deployment')
                    
                    # Handle roadblocks
                    roadblocks = row.get('Roadblocks', '').strip()
                    success_criteria = row.get('Success Criteria', '').strip()
                    if success_criteria and not roadblocks:
                        roadblocks = f"Success Criteria: {success_criteria}"
                    elif success_criteria:
                        roadblocks = f"{roadblocks}\n\nSuccess Criteria: {success_criteria}"
                        
                    overcome_str = row.get('Roadblock Removed', '')
                    overcome_roadblocks = overcome_str.lower() in ['yes', 'true', '1', 'y', 't'] if isinstance(overcome_str, str) else False
                    
                    # Handle status
                    win_loss = row.get('Win/Loss', '').strip().lower()
                    technical_win = row.get('Technical Win', '').strip().lower()
                    
                    # Map Win/Loss to status
                    if win_loss in ['won', 'win', 'yes']:
                        status = 'Closed - Won'
                    elif win_loss in ['lost', 'loss', 'no']:
                        status = 'Closed - Lost'
                    elif technical_win in ['in progress', 'ongoing']:
                        status = 'Active'
                    elif technical_win in ['on hold', 'paused']:
                        status = 'On Hold'
                    else:
                        status = 'Active'
                    
                    # Create notes from "Reason" field
                    reason = row.get('Reason', '').strip()
                    amount = row.get('Amount', '').strip()
                    close_date = row.get('Close Date', '').strip()
                    
                    # Combine additional info into notes
                    notes = ""
                    if reason:
                        notes += f"Reason: {reason}\n\n"
                    if amount:
                        notes += f"Amount: {amount}\n\n"
                    if close_date:
                        notes += f"Close Date: {close_date}\n\n"
                    
                    # Skip rows without a customer name
                    if not customer_name:
                        print(f"Warning: Skipping row without customer name")
                        continue
                    
                    # Create POV
                    pov = POV(
                        customer_name=customer_name,
                        assigned_se=assigned_se if assigned_se else 'Unassigned',
                        assigned_ae=assigned_ae if assigned_ae else 'Unassigned',
                        start_date=start_date,
                        projected_end_date=end_date,
                        current_stage=current_stage,
                        roadblocks=roadblocks,
                        overcome_roadblocks=overcome_roadblocks,
                        status=status
                    )
                    
                    db.session.add(pov)
                    db.session.flush()  # Get the POV ID
                    povs_added += 1
                    
                    # Add note if it exists
                    if notes.strip():
                        note = Note(
                            content=notes.strip(),
                            pov_id=pov.id,
                            timestamp=datetime.now()
                        )
                        db.session.add(note)
                        notes_added += 1
                    
                except Exception as e:
                    print(f"Error importing row: {str(e)}")
                    errors += 1
                    continue
            
            # Commit all changes
            db.session.commit()
            
            print(f"Import complete: {povs_added} POVs added, {notes_added} notes added, {errors} errors")

if __name__ == "__main__":
    # Check if a CSV file was provided
    if len(sys.argv) < 2:
        print("Usage: python import_csv.py <path_to_csv_file>")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    import_csv(csv_file)
