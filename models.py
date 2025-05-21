from datetime import datetime
from app import db

class POV(db.Model):
    __tablename__ = 'povs'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    assigned_se = db.Column(db.String(100), nullable=False)
    assigned_ae = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    projected_end_date = db.Column(db.Date, nullable=False)
    current_stage = db.Column(db.String(50), nullable=False)
    roadblocks = db.Column(db.Text)
    overcome_roadblocks = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='Active')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    notes = db.relationship('Note', backref='pov', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"POV('{self.customer_name}', '{self.current_stage}', '{self.status}')"

class Note(db.Model):
    __tablename__ = 'notes'
    
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    pov_id = db.Column(db.Integer, db.ForeignKey('povs.id'), nullable=False)
    
    def __repr__(self):
        return f"Note('{self.timestamp}', '{self.content[:20]}...')"