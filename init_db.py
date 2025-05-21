from app import app, db
from models import POV, Note
from datetime import datetime, timedelta

# Create application context
with app.app_context():
    # Initialize database
    db.create_all()
    print('Database initialized!')

    # Check if you want to add sample data
    add_sample = input('Do you want to add sample data? (y/n): ')
    
    if add_sample.lower() == 'y':
        # Clear existing data
        db.session.query(Note).delete()
        db.session.query(POV).delete()
        
        # Sample POVs
        povs = [
            POV(
                customer_name='Acme Corp',
                assigned_se='John Doe',
                assigned_ae='Alex Brown',
                start_date=datetime.now() - timedelta(days=15),
                projected_end_date=datetime.now() + timedelta(days=15),
                current_stage='Training 1',
                roadblocks='Waiting on customer environment setup',
                overcome_roadblocks=False,
                status='Active'
            ),
            POV(
                customer_name='Globex Inc',
                assigned_se='Jane Smith',
                assigned_ae='Sarah Lee',
                start_date=datetime.now() - timedelta(days=30),
                projected_end_date=datetime.now(),
                current_stage='Wrap-Up',
                roadblocks='',
                overcome_roadblocks=True,
                status='Active'
            ),
            POV(
                customer_name='Initech',
                assigned_se='Bob Johnson',
                assigned_ae='Mike Wilson',
                start_date=datetime.now() - timedelta(days=45),
                projected_end_date=datetime.now() - timedelta(days=15),
                current_stage='Tech Call',
                roadblocks='Customer requested additional training',
                overcome_roadblocks=True,
                status='On Hold'
            ),
            POV(
                customer_name='Umbrella Corp',
                assigned_se='John Doe',
                assigned_ae='Alex Brown',
                start_date=datetime.now() - timedelta(days=60),
                projected_end_date=datetime.now() - timedelta(days=30),
                current_stage='Tech Call',
                roadblocks='',
                overcome_roadblocks=True,
                status='Closed - Won'
            )
        ]
        
        for pov in povs:
            db.session.add(pov)
        
        db.session.commit()
        
        # Add some notes to the POVs
        notes = [
            Note(
                content='Initial meeting went well. Customer is excited to start.',
                pov_id=1,
                timestamp=datetime.now() - timedelta(days=15)
            ),
            Note(
                content='Deployment completed successfully.',
                pov_id=1,
                timestamp=datetime.now() - timedelta(days=10)
            ),
            Note(
                content='Customer experiencing issues with configuration.',
                pov_id=1,
                timestamp=datetime.now() - timedelta(days=5)
            ),
            Note(
                content='Wrap-up meeting scheduled for next week.',
                pov_id=2,
                timestamp=datetime.now() - timedelta(days=5)
            ),
            Note(
                content='Customer requested pricing information.',
                pov_id=3,
                timestamp=datetime.now() - timedelta(days=20)
            ),
            Note(
                content='POV successful, moving to contract stage.',
                pov_id=4,
                timestamp=datetime.now() - timedelta(days=35)
            )
        ]
        
        for note in notes:
            db.session.add(note)
        
        db.session.commit()
        print('Sample data added!')