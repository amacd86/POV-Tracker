from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DateField, TextAreaField, BooleanField, SubmitField, FloatField
from wtforms.validators import DataRequired, Email, Optional
from datetime import datetime, timedelta
import os
import csv
from io import StringIO, BytesIO
from sqlalchemy import func, extract
from collections import Counter

# Create Flask app first
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-for-pov-tracker-12345')

# For PythonAnywhere, use absolute path to database
basedir = os.path.abspath(os.path.dirname(__file__))
database_path = os.path.join(basedir, 'pov_tracker.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{database_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database extension
db = SQLAlchemy()
db.init_app(app)

# Define models
class SimplePOVForm:
    """Simple form handler without flask-wtf dependency"""
    def __init__(self, request=None):
        self.request = request
        self.errors = {}
    
    def validate(self):
        """Basic validation"""
        if not self.request:
            return False
        
        required_fields = ['deal_name', 'customer_name', 'assigned_ae', 'start_date', 'current_stage', 'status']
        
        for field in required_fields:
            if not self.request.form.get(field, '').strip():
                self.errors[field] = f'{field.replace("_", " ").title()} is required'
        
        return len(self.errors) == 0

class POV(db.Model):
    __tablename__ = 'povs'
    
    id = db.Column(db.Integer, primary_key=True)
    deal_name = db.Column(db.String(200), nullable=False)
    assigned_se = db.Column(db.String(100))
    assigned_ae = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    projected_end_date = db.Column(db.Date)
    actual_completion_date = db.Column(db.Date)
    current_stage = db.Column(db.String(50), nullable=False)
    roadblocks = db.Column(db.Text)
    overcome_roadblocks = db.Column(db.Text)
    status = db.Column(db.String(50), nullable=False)
    deal_amount = db.Column(db.Float)
    success_criteria = db.Column(db.Text)
    technical_win = db.Column(db.Boolean, default=False)
    roadblock_resolution = db.Column(db.Text)
    win_loss_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted = db.Column(db.Boolean, default=False)
    deleted_at = db.Column(db.DateTime)
    
    # NEW columns
    customer_name = db.Column(db.String(200), nullable=False, default='Contact Required')
    customer_email = db.Column(db.String(200))
    sales_engineer = db.Column(db.String(100))
    roadblock_category = db.Column(db.String(50))
    roadblock_severity = db.Column(db.String(10))
    roadblock_owner = db.Column(db.String(20))
    roadblock_notes = db.Column(db.Text)
    roadblock_created_date = db.Column(db.Date)
    roadblock_resolved_date = db.Column(db.Date)
    
    # <<< FIX #1 >>> This redundant 'notes' column has been removed. The relationship below handles it.
    
    # Relationship to Note model
    notes = db.relationship('Note', backref='pov', lazy=True, cascade="all, delete-orphan")

    @property
    def days_stagnant(self):
        """Calculate days since roadblock was created (if unresolved)"""
        if self.roadblock_created_date and not self.roadblock_resolved_date:
            return (datetime.utcnow().date() - self.roadblock_created_date).days
        return 0

    @property
    def company_name(self):
        return self.deal_name

    @property
    def stage(self):
        return self.current_stage

    @property
    def account_executive(self):
        return self.assigned_ae

    @property
    def expected_end_date(self):
        return self.projected_end_date

    @property
    def actual_end_date(self):
        return self.actual_completion_date

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    pov_id = db.Column(db.Integer, db.ForeignKey('povs.id'), nullable=False)

# Custom Jinja2 filters and globals
@app.template_filter('nl2br')
def nl2br_filter(s):
    if s:
        return s.replace('\n', '<br>')
    return s

@app.context_processor
def inject_now():
    return {'now': datetime.now}

# Forms
class POVForm(FlaskForm):
    # ... (No changes in this class) ...
    pass

class NoteForm(FlaskForm):
    content = TextAreaField('Note', validators=[DataRequired()])
    submit = SubmitField('Add Note')

# Initialize database function
def init_db():
    # ... (No changes in this function) ...
    pass

def get_pov_metrics():
    """A single, reliable function to calculate all key analytics metrics."""
    today = datetime.utcnow().date()
    
    # Define status variations
    won_statuses = ['Closed Won', 'Closed - Won']
    lost_statuses = ['Closed Lost', 'Closed - Lost']
    completed_statuses = won_statuses + lost_statuses
    active_statuses = ['In Trial', 'Pending Sales', 'Active', 'On Hold']

    # Get all non-deleted POVs once to work with them in memory
    all_povs = POV.query.filter_by(deleted=False).all()
    
    # Filter lists
    active_povs_list = [p for p in all_povs if p.status in active_statuses]
    completed_povs_list = [p for p in all_povs if p.status in completed_statuses]

    # --- TOP ROW METRICS ---
    ending_soon = len([p for p in active_povs_list if p.projected_end_date and today <= p.projected_end_date <= (today + timedelta(days=14))])
    overdue = len([p for p in active_povs_list if p.projected_end_date and p.projected_end_date < today])
    
    durations = [(p.projected_end_date - p.start_date).days for p in active_povs_list if p.projected_end_date and p.start_date]
    avg_duration = sum(durations) / len(durations) if durations else 0
    
    total_value = sum(p.deal_amount for p in active_povs_list if p.deal_amount)

    # --- SECOND ROW METRICS ---
    closed_won_count = len([p for p in completed_povs_list if p.status in won_statuses])
    completed_count = len(completed_povs_list)
    pov_conversion_rate = (closed_won_count / completed_count) * 100 if completed_count > 0 else 0
    
    technical_wins_count = len([p for p in completed_povs_list if p.technical_win])
    tech_win_rate = (technical_wins_count / completed_count) * 100 if completed_count > 0 else 0

    # --- STAGE CARDS METRICS ---
    stage_counts = {
        'deployment': len([p for p in active_povs_list if p.current_stage == 'Deployment']),
        'training_1': len([p for p in active_povs_list if p.current_stage == 'Training 1']),
        'training_2': len([p for p in active_povs_list if p.current_stage == 'Training 2']),
        'pov_wrap_up': len([p for p in active_povs_list if p.current_stage == 'POV Wrap-Up']),
    }

    return {
        'total_povs': len(all_povs),
        'povs_in_progress': len(active_povs_list),
        'completed_povs': completed_count,
        'ending_soon': ending_soon,
        'overdue': overdue,
        'avg_duration': round(avg_duration, 1),
        'total_value': total_value or 0,
        'technical_wins': technical_wins_count,
        'closed_won_count': closed_won_count,
        'pov_conversion_rate': round(pov_conversion_rate, 1),
        'tech_win_rate': round(tech_win_rate, 1),
        'stage_counts': stage_counts,
    }
# Routes
@app.route('/')
def dashboard():
    try:
        se_filter = request.args.get('se', '')
        ae_filter = request.args.get('ae', '')
        status_filter = request.args.get('status', '')
        start_date_from = request.args.get('start_date_from', '')
        start_date_to = request.args.get('start_date_to', '')
        end_date_from = request.args.get('end_date_from', '')
        end_date_to = request.args.get('end_date_to', '')

        query = POV.query.filter_by(deleted=False)

        if se_filter:
            query = query.filter(POV.assigned_se == se_filter)
        if ae_filter:
            query = query.filter(POV.assigned_ae == ae_filter)
        if status_filter:
            query = query.filter(POV.status == status_filter)
        # Add date filters if you wish

        povs = query.order_by(POV.start_date.desc()).all()

        all_ses = sorted([se[0] for se in db.session.query(POV.assigned_se).filter(POV.assigned_se.isnot(None)).distinct().all()])
        all_aes = sorted([ae[0] for ae in db.session.query(POV.assigned_ae).filter(POV.assigned_ae.isnot(None)).distinct().all()])
        all_statuses = [('Active', 'Active'), ('On Hold', 'On Hold'), ('Closed Won', 'Closed Won'), ('Closed Lost', 'Closed Lost'), ('Pending Sales', 'Pending Sales')]

    except Exception as e:
        flash(f'An error occurred while loading the dashboard: {e}', 'danger')
        povs, all_ses, all_aes, all_statuses = [], [], [], []

    return render_template('dashboard.html',
                           povs=povs,
                           all_ses=all_ses,
                           all_aes=all_aes,
                           all_statuses=all_statuses,
                           se_filter=se_filter,
                           ae_filter=ae_filter,
                           status_filter=status_filter,
                           start_date_from=start_date_from,
                           start_date_to=start_date_to,
                           end_date_from=end_date_from,
                           end_date_to=end_date_to)

@app.route('/pov/new', methods=['GET', 'POST'])
def new_pov():
    if request.method == 'POST':
        form = SimplePOVForm(request)
        if form.validate():
            # ... (code to create pov object) ...
            db.session.add(pov)
            db.session.commit()
            flash('POV created successfully!', 'success')
            # <<< FIX #2 >>> Standardize redirect to use pov_id
            return redirect(url_for('pov_detail', pov_id=pov.id))
        else:
            for field, error in form.errors.items():
                flash(f'{error}', 'error')
    return render_template('pov_form.html', title='New POV')

# <<< FIX #3 >>> Standardize route to use pov_id
@app.route('/pov/<int:pov_id>/edit', methods=['GET', 'POST'])
def edit_pov(pov_id):
    pov = POV.query.get_or_404(pov_id)
    form = POVForm(obj=pov)
    
    if form.validate_on_submit():
        # ... (code to update pov object) ...
        db.session.commit()
        
        flash('POV updated successfully!', 'success')
        # <<< FIX #4 >>> Standardize redirect to use pov_id
        return redirect(url_for('pov_detail', pov_id=pov.id))
    
    return render_template('pov_form.html', form=form, title='Edit POV', pov=pov)

# <<< FIX #5 >>> Standardize route to use pov_id
@app.route('/pov/<int:pov_id>')
def pov_detail(pov_id):
    pov = POV.query.get_or_404(pov_id)
    return render_template('pov_detail.html', pov=pov)

@app.route('/export_csv')
def export_csv():
    # ... (No changes in this route) ...
    pass

@app.route('/bulk_action', methods=['POST'])
def bulk_action():
    # ... (No changes in this route) ...
    pass

@app.route('/analytics')
def analytics():
    # This route now has only two jobs: get the metrics and get chart data.
    metrics = get_pov_metrics()
    
    # Data for charts
    status_counts = db.session.query(POV.status, func.count(POV.id)).filter_by(deleted=False).group_by(POV.status).all()
    stage_counts_active = db.session.query(POV.current_stage, func.count(POV.id)).filter_by(deleted=False).filter(POV.status.in_(['In Trial', 'Pending Sales'])).group_by(POV.current_stage).all()

    return render_template(
        'analytics.html',
        metrics=metrics, # We just pass the whole dictionary
        status_chart_data = [{'label': status, 'value': count} for status, count in status_counts],
        stage_chart_data = [{'label': stage, 'value': count} for stage, count in stage_counts_active]
    )

@app.route('/init_db')
def init_database():
    # ... (No changes in this route) ...
    pass

# <<< FIX #6 >>> Standardize redirect to use pov_id (it was already correct but now matches the fixed pov_detail route)
@app.route('/pov/<int:pov_id>/roadblock', methods=['GET', 'POST'])
def manage_roadblock(pov_id):
    pov = POV.query.get_or_404(pov_id)
    if request.method == 'POST':
        # ... (code to update roadblock) ...
        db.session.commit()
        flash('Roadblock updated successfully!', 'success')
        return redirect(url_for('pov_detail', pov_id=pov.id))
    return render_template('roadblock_form.html', pov=pov)

def get_roadblock_analytics():
    # ... (No changes in this function) ...
    pass

@app.route('/roadblocks/analytics')
def roadblock_analytics():
    # ... (No changes in this route) ...
    pass

@app.route('/pov/<int:pov_id>/delete', methods=['POST'])
def delete_pov(pov_id):
    pov = POV.query.get_or_404(pov_id)
    pov.deleted = True
    pov.deleted_at = datetime.utcnow()
    db.session.commit()
    flash(f'POV "{pov.deal_name}" has been moved to the trash.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/pov/<int:pov_id>/mark_complete', methods=['POST'])
def mark_complete(pov_id):
    pov = POV.query.get_or_404(pov_id)
    new_status = request.form.get('status')
    if new_status in ['Closed Won', 'Closed Lost']:
        pov.status = new_status
        pov.actual_completion_date = datetime.utcnow().date()
        db.session.commit()
        flash(f'POV "{pov.deal_name}" has been marked as {new_status}.', 'success')
    else:
        flash('Invalid status provided.', 'danger')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)