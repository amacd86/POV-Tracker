from app import app, db, POV
with app.app_context():
    povs = POV.query.filter_by(deleted=False).all()
    print(f'Total POVs: {len(povs)}')
    for pov in povs[:5]:
        print(f'- {pov.deal_name}: status="{pov.status}", stage="{pov.current_stage}"')
    
    statuses = db.session.query(POV.status).filter_by(deleted=False).distinct().all()
    print(f'Unique statuses: {[s[0] for s in statuses]}')
