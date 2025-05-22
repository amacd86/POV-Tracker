from app import app, db, POV, Note

def clear_sample_data():
    with app.app_context():
        # List of known sample customer names
        sample_names = ['Acme Corp', 'Globex Inc', 'Initech', 'Umbrella Corp', 'poop corp', 'Smol beeb']
        
        # Find POVs with sample names
        sample_povs = POV.query.filter(POV.customer_name.in_(sample_names)).all()
        
        if not sample_povs:
            print("No sample data found.")
            return
        
        print(f"Found {len(sample_povs)} sample POVs to delete.")
        
        # Delete notes for sample POVs
        for pov in sample_povs:
            Note.query.filter_by(pov_id=pov.id).delete()
            print(f"Deleted notes for {pov.customer_name}")
            
            # Delete the POV
            db.session.delete(pov)
            print(f"Deleted POV for {pov.customer_name}")
        
        # Commit the changes
        db.session.commit()
        print("Sample data cleared successfully!")

if __name__ == "__main__":
    clear_sample_data()
