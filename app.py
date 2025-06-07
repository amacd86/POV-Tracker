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
#fun comment
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
    notes = db.Column(db.Text)

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
    # Basic POV Information
    company_name = StringField('Company Name', validators=[DataRequired()])
    deal_name = StringField('Deal Name', validators=[DataRequired()])
    customer_name = StringField('Customer Contact Name', validators=[DataRequired()])
    customer_email = StringField('Customer Email', validators=[Email(), Optional()])
    
    # POV Details
    stage = SelectField('Stage', choices=[
        ('', 'Select Stage'),
        ('Initial Contact', 'Initial Contact'),
        ('Discovery', 'Discovery'),
        ('Deployment', 'Deployment'),
        ('Training 1', 'Training 1'),
        ('Training 2', 'Training 2'),
        ('POV Wrap-Up', 'POV Wrap-Up'),
        ('Evaluation', 'Evaluation')
    ], validators=[DataRequired()])
    
    status = SelectField('Status', choices=[
        ('', 'Select Status'),
        ('Active', 'Active'),
        ('On Hold', 'On Hold'),
        ('Closed Won', 'Closed Won'),
        ('Closed Lost', 'Closed Lost')
    ], validators=[DataRequired()])
    
    # Dates
    start_date = DateField('Start Date', validators=[DataRequired()])
    expected_end_date = DateField('Expected End Date', validators=[Optional()])
    actual_end_date = DateField('Actual End Date', validators=[Optional()])
    
    # Sales Team
    account_executive = StringField('Account Executive', validators=[DataRequired()])
    sales_engineer = StringField('Sales Engineer', validators=[Optional()])
    
    # Technical Information
    technical_win = BooleanField('Technical Win')
    
    # Enhanced Roadblock Fields (from Phase 1)
    roadblock_category = SelectField('Roadblock Category', choices=[
        ('', 'No Roadblock'),
        ('Technical', '🔧 Technical'),
        ('Budget', '💰 Budget'),
        ('Timeline', '⏰ Timeline'),
        ('Decision Maker', '👥 Decision Maker'),
        ('Competitive', '⚔️ Competitive')
    ], validators=[Optional()])
    
    roadblock_severity = SelectField('Roadblock Severity', choices=[
        ('', 'Select Severity'),
        ('Low', '🟢 Low'),
        ('Medium', '🟡 Medium'),
        ('High', '🔴 High')
    ], validators=[Optional()])
    
    roadblock_owner = SelectField('Roadblock Owner', choices=[
        ('', 'Select Owner'),
        ('AE', '👔 AE (Account Executive)'),
        ('SE', '🛠️ SE (Sales Engineer)'),
        ('Leadership', '👑 Leadership'),
        ('Engineering', '⚙️ Engineering')
    ], validators=[Optional()])
    
    roadblock_notes = TextAreaField('Roadblock Notes', validators=[Optional()])
    
    # Additional Fields
    notes = TextAreaField('General Notes', validators=[Optional()])
    
    # Submit
    submit = SubmitField('Save POV')

class NoteForm(FlaskForm):
    content = TextAreaField('Note', validators=[DataRequired()])
    submit = SubmitField('Add Note')

# Initialize database function
def init_db():
    """Initialize the database with all tables"""
    with app.app_context():
        try:
            # Drop all tables and recreate to ensure correct structure
            db.drop_all()
            db.create_all()
            print("Database initialized successfully!")
            return True
        except Exception as e:
            print(f"Error initializing database: {e}")
            return False

def get_pov_metrics():
    """
    Calculate POV metrics with corrected logic:
    - Only count completed POVs (Closed Won + Closed Lost) for conversion rates
    - Exclude pending/in-progress POVs from rate calculations
    """
    # Get completed POVs only (excludes pending/in-progress)
    completed_povs = POV.query.filter(
        POV.deleted == False,
        POV.status.in_(['Closed Won', 'Closed Lost'])
    ).count()

    # Get won POVs
    closed_won_count = POV.query.filter(
        POV.deleted == False, 
        POV.status == 'Closed Won'
    ).count()

    # Get lost POVs
    closed_lost_count = POV.query.filter(
        POV.deleted == False,
        POV.status == 'Closed Lost'
    ).count()

    # Get technical wins (assuming you have a technical_win boolean field or 'Yes' string)
    technical_wins = POV.query.filter(
        POV.deleted == False,
        ((POV.technical_win == True) | (POV.technical_win == 'Yes')),
        POV.status.in_(['Closed Won', 'Closed Lost'])
    ).count()

    # FIXED CALCULATIONS - Only use completed POVs as denominator
    pov_conversion_rate = (closed_won_count / completed_povs) * 100 if completed_povs > 0 else 0
    tech_win_rate = (technical_wins / completed_povs) * 100 if completed_povs > 0 else 0

    # Stage counts for new metric cards (for active POVs only)
    deployment_count = POV.query.filter(
        POV.deleted == False,
        POV.current_stage == 'Deployment',
        POV.status.in_(['In Trial', 'Pending Sales'])
    ).count()

    training_1_count = POV.query.filter(
        POV.deleted == False,
        POV.current_stage == 'Training 1',
        POV.status.in_(['In Trial', 'Pending Sales'])
    ).count()

    training_2_count = POV.query.filter(
        POV.deleted == False,
        POV.current_stage == 'Training 2',
        POV.status.in_(['In Trial', 'Pending Sales'])
    ).count()

    pov_wrap_up_count = POV.query.filter(
        POV.deleted == False,
        POV.current_stage == 'POV Wrap-Up',
        POV.status.in_(['In Trial', 'Pending Sales'])
    ).count()

    return {
        'total_povs': POV.query.filter(POV.deleted == False).count(),
        'completed_povs': completed_povs,
        'closed_won_count': closed_won_count,
        'closed_lost_count': closed_lost_count,
        'technical_wins': technical_wins,
        'pov_conversion_rate': round(pov_conversion_rate, 1),
        'tech_win_rate': round(tech_win_rate, 1),
        'stage_counts': {
            'deployment': deployment_count,
            'training_1': training_1_count,
            'training_2': training_2_count,
            'pov_wrap_up': pov_wrap_up_count
        }
    }

# Routes
@app.route('/')
def dashboard():
    metrics = get_pov_metrics()
    # Define filter defaults at the start
    se_filter = request.args.get('se', '')
    ae_filter = request.args.get('ae', '')
    status_filter = request.args.get('status', '')
    start_date_from = request.args.get('start_date_from', '')
    start_date_to = request.args.get('start_date_to', '')
    end_date_from = request.args.get('end_date_from', '')
    end_date_to = request.args.get('end_date_to', '')

    try:
        # Only create tables if they do not exist (no drop_all, no destructive init)
        if not os.path.exists(database_path):
            db.create_all()
        
        query = POV.query.filter_by(deleted=False)

        if se_filter:
            query = query.filter(POV.assigned_se == se_filter)
        if ae_filter:
            query = query.filter(POV.assigned_ae == ae_filter)
        if status_filter:
            query = query.filter(POV.status == status_filter)

        if start_date_from:
            try:
                from_date = datetime.strptime(start_date_from, '%Y-%m-%d').date()
                query = query.filter(POV.start_date >= from_date)
            except ValueError:
                flash('Invalid start date format. Please use YYYY-MM-DD format.', 'warning')

        if start_date_to:
            try:
                to_date = datetime.strptime(start_date_to, '%Y-%m-%d').date()
                query = query.filter(POV.start_date <= to_date)
            except ValueError:
                flash('Invalid start date format. Please use YYYY-MM-DD format.', 'warning')

        if end_date_from:
            try:
                from_date = datetime.strptime(end_date_from, '%Y-%m-%d').date()
                query = query.filter(POV.projected_end_date >= from_date)
            except ValueError:
                flash('Invalid end date format. Please use YYYY-MM-DD format.', 'warning')

        if end_date_to:
            try:
                to_date = datetime.strptime(end_date_to, '%Y-%m-%d').date()
                query = query.filter(POV.projected_end_date <= to_date)
            except ValueError:
                flash('Invalid end date format. Please use YYYY-MM-DD format.', 'warning')

        povs = query.all()

        try:
            all_ses = db.session.query(POV.assigned_se).filter_by(deleted=False).distinct().all()
            all_aes = db.session.query(POV.assigned_ae).filter_by(deleted=False).distinct().all()
        except:
            all_ses = []
            all_aes = []

        all_statuses = [('Active', 'Active'), ('On Hold', 'On Hold'), ('Closed - Won', 'Closed - Won'), ('Closed - Lost', 'Closed - Lost')]

        # Status chart with percentages (for Chart.js)
        all_statuses_chart = [row[0] for row in db.session.query(POV.status).filter(POV.deleted == False).all()]
        status_counts = Counter(all_statuses_chart)
        total_povs = len(all_statuses_chart)
        chart_data = {
            'labels': [],
            'datasets': [{
                'data': [],
                'backgroundColor': [
                    '#28a745',  # Closed Won
                    '#dc3545',  # Closed Lost
                    '#ffc107',  # In Progress
                    '#6c757d',  # On Hold
                    '#17a2b8',  # Pending Sales
                    '#007bff',  # Other
                ]
            }]
        }
        color_map = {
            'Closed Won': '#28a745',
            'Closed Lost': '#dc3545',
            'In Trial': '#ffc107',
            'On Hold': '#6c757d',
            'Pending Sales': '#17a2b8'
        }
        for status, count in status_counts.items():
            percentage = (count / total_povs) * 100 if total_povs else 0
            chart_data['labels'].append(f"{status}: {count} ({percentage:.0f}%)")
            chart_data['datasets'][0]['data'].append(count)
            chart_data['datasets'][0]['backgroundColor'].append(color_map.get(status, '#007bff'))

        return render_template('dashboard.html', 
                               povs=povs,
                               all_ses=[se[0] for se in all_ses],
                               all_aes=[ae[0] for ae in all_aes],
                               all_statuses=all_statuses,
                               se_filter=se_filter,
                               ae_filter=ae_filter,
                               status_filter=status_filter,
                               start_date_from=start_date_from,
                               start_date_to=start_date_to,
                               end_date_from=end_date_from,
                               end_date_to=end_date_to,
                               metrics=metrics,
                               status_data=status_data,
                               chart_data=chart_data)
    except Exception as e:
        flash(f'Could not load all dashboard data: {e}', 'danger')
        povs = []
        all_ses = []
        all_aes = []
        all_statuses = []
        chart_data = {'labels': [], 'datasets': [{'data': [], 'backgroundColor': []}]}
        status_data = []
        # Ensure filters are defined
        se_filter = se_filter if 'se_filter' in locals() else ''
        ae_filter = ae_filter if 'ae_filter' in locals() else ''
        status_filter = status_filter if 'status_filter' in locals() else ''
        start_date_from = start_date_from if 'start_date_from' in locals() else ''
        start_date_to = start_date_to if 'start_date_to' in locals() else ''
        end_date_from = end_date_from if 'end_date_from' in locals() else ''
        end_date_to = end_date_to if 'end_date_to' in locals() else ''
        return render_template('dashboard.html', 
                               povs=povs, all_ses=all_ses, all_aes=all_aes, all_statuses=all_statuses,
                               se_filter=se_filter, ae_filter=ae_filter, status_filter=status_filter,
                               start_date_from=start_date_from, start_date_to=start_date_to,
                               end_date_from=end_date_from, end_date_to=end_date_to,
                               metrics=metrics,
                               status_data=status_data,
                               chart_data=chart_data)

@app.route('/pov/new', methods=['GET', 'POST'])
def new_pov():
    if request.method == 'POST':
        form = SimplePOVForm(request)
        if form.validate():
            pov = POV(
                deal_name=request.form['deal_name'],
                customer_name=request.form['customer_name'],
                customer_email=request.form.get('customer_email', ''),
                assigned_ae=request.form['assigned_ae'],
                assigned_se=request.form.get('assigned_se', ''),
                start_date=datetime.strptime(request.form['start_date'], '%Y-%m-%d').date(),
                projected_end_date=datetime.strptime(request.form['projected_end_date'], '%Y-%m-%d').date() if request.form.get('projected_end_date') else None,
                current_stage=request.form['current_stage'],
                status=request.form['status'],
                deal_amount=float(request.form['deal_amount']) if request.form.get('deal_amount') else None,
                technical_win=bool(request.form.get('technical_win')),
                notes=request.form.get('notes', ''),
                success_criteria=request.form.get('success_criteria', ''),
                roadblocks=request.form.get('roadblocks', '')
            )
            # Handle new roadblock fields
            if request.form.get('roadblock_category'):
                pov.roadblock_category = request.form['roadblock_category']
                pov.roadblock_severity = request.form.get('roadblock_severity')
                pov.roadblock_owner = request.form.get('roadblock_owner')
                pov.roadblock_notes = request.form.get('roadblock_notes', '')
                pov.roadblock_created_date = datetime.utcnow().date()
            db.session.add(pov)
            db.session.commit()
            flash('POV created successfully!', 'success')
            return redirect(url_for('pov_detail', id=pov.id))
        else:
            for field, error in form.errors.items():
                flash(f'{error}', 'error')
    return render_template('pov_form.html', title='New POV')

@app.route('/pov/<int:id>/edit', methods=['GET', 'POST'])
def edit_pov(id):
    pov = POV.query.get_or_404(id)
    form = POVForm(obj=pov)
    
    if form.validate_on_submit():
        # Check if roadblock status changed
        old_roadblock = pov.roadblock_category
        new_roadblock = form.roadblock_category.data
        
        # Update all fields
        form.populate_obj(pov)
        
        # Handle roadblock date logic
        if new_roadblock and not old_roadblock:
            # New roadblock added
            pov.roadblock_created_date = datetime.utcnow().date()
            pov.roadblock_resolved_date = None
        elif not new_roadblock and old_roadblock:
            # Roadblock removed (resolved)
            pov.roadblock_resolved_date = datetime.utcnow().date()
        
        pov.updated_at = datetime.utcnow()
        db.session.commit()
        
        flash('POV updated successfully!', 'success')
        return redirect(url_for('pov_detail', id=pov.id))
    
    return render_template('pov_form.html', form=form, title='Edit POV', pov=pov)

@app.route('/pov/<int:id>')
def pov_detail(id):
    pov = POV.query.get_or_404(id)
    return render_template('pov_detail.html', pov=pov)

@app.route('/export_csv')
def export_csv():
    try:
        # Get filter parameters
        se_filter = request.args.get('se', '')
        ae_filter = request.args.get('ae', '')
        status_filter = request.args.get('status', '')
        start_date_from = request.args.get('start_date_from', '')
        start_date_to = request.args.get('start_date_to', '')
        end_date_from = request.args.get('end_date_from', '')
        end_date_to = request.args.get('end_date_to', '')

        # Base query - exclude deleted POVs
        query = POV.query.filter_by(deleted=False)

        # Apply filters if provided
        if se_filter:
            query = query.filter(POV.assigned_se == se_filter)
        if ae_filter:
            query = query.filter(POV.assigned_ae == ae_filter)
        if status_filter:
            query = query.filter(POV.status == status_filter)

        # Apply date filters with proper error handling
        if start_date_from:
            try:
                from_date = datetime.strptime(start_date_from, '%Y-%m-%d').date()
                query = query.filter(POV.start_date >= from_date)
            except ValueError:
                pass

        if start_date_to:
            try:
                to_date = datetime.strptime(start_date_to, '%Y-%m-%d').date()
                query = query.filter(POV.start_date <= to_date)
            except ValueError:
                pass

        if end_date_from:
            try:
                from_date = datetime.strptime(end_date_from, '%Y-%m-%d').date()
                query = query.filter(POV.projected_end_date >= from_date)
            except ValueError:
                pass

        if end_date_to:
            try:
                to_date = datetime.strptime(end_date_to, '%Y-%m-%d').date()
                query = query.filter(POV.projected_end_date <= to_date)
            except ValueError:
                pass

        # Get filtered POVs
        povs = query.all()

        # Create a string buffer for CSV content
        output = StringIO()
        writer = csv.writer(output)

        # Write header row
        writer.writerow([
            'Deal Name', 'SE', 'AE', 'Stage', 'Start Date', 'Projected End Date', 'Actual Completion Date',
            'Status', 'Deal Amount ($)', 'Success Criteria', 'Technical Win', 'Roadblocks', 'Roadblock Resolution',
            'Roadblocks Overcome', 'Win/Loss Reason', 'Notes'
        ])

        # Write data rows
        for pov in povs:
            try:
                notes = Note.query.filter_by(pov_id=pov.id).order_by(Note.timestamp.desc()).all()
                notes_text = "; ".join([f"{note.timestamp.strftime('%m/%d/%Y')}: {note.content}" for note in notes])
            except:
                notes_text = ""

            writer.writerow([
                pov.deal_name,
                pov.assigned_se,
                pov.assigned_ae,
                pov.current_stage,
                pov.start_date.strftime('%m/%d/%Y') if pov.start_date else '',
                pov.projected_end_date.strftime('%m/%d/%Y') if pov.projected_end_date else '',
                pov.actual_completion_date.strftime('%m/%d/%Y') if pov.actual_completion_date else '',
                pov.status,
                f"${pov.deal_amount:.2f}" if pov.deal_amount else "-",
                pov.success_criteria or '',
                pov.technical_win or '',
                pov.roadblocks or '',
                pov.roadblock_resolution or '',
                'Yes' if pov.overcome_roadblocks else 'No',
                pov.win_loss_reason or '',
                notes_text
            ])

        # Convert to bytes for sending
        output.seek(0)
        output_bytes = BytesIO()
        output_bytes.write(output.getvalue().encode('utf-8-sig'))
        output_bytes.seek(0)

        return send_file(
            output_bytes,
            as_attachment=True,
            download_name=f'POV_Tracker_{datetime.now().strftime("%Y-%m-%d")}.csv',
            mimetype='text/csv'
        )
    except Exception as e:
        flash(f'Error exporting CSV: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/bulk_action', methods=['POST'])
def bulk_action():
    try:
        action = request.form.get('bulk_action')
        selected_povs = request.form.getlist('selected_povs')
        
        if not action or not selected_povs:
            flash('No action or POVs selected.', 'warning')
            return redirect(url_for('dashboard'))
        
        povs = POV.query.filter(POV.id.in_(selected_povs)).all()
        count = len(povs)
        
        if action == 'delete':
            for pov in povs:
                pov.deleted = True
                pov.deleted_at = datetime.now()
            db.session.commit()
            flash(f'{count} POVs moved to trash.', 'success')
        
        elif action == 'mark_active':
            for pov in povs:
                pov.status = 'Active'
            db.session.commit()
            flash(f'{count} POVs marked as Active.', 'success')
        
        elif action == 'mark_on_hold':
            for pov in povs:
                pov.status = 'On Hold'
            db.session.commit()
            flash(f'{count} POVs marked as On Hold.', 'success')
        
        elif action == 'mark_won':
            for pov in povs:
                pov.status = 'Closed - Won'
            db.session.commit()
            flash(f'{count} POVs marked as Won.', 'success')
        
        elif action == 'mark_lost':
            for pov in povs:
                pov.status = 'Closed - Lost'
            db.session.commit()
            flash(f'{count} POVs marked as Lost.', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash(f'Error performing bulk action: {str(e)}', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/analytics')
def analytics():
    try:
        # Get current date
        today = datetime.now().date()
        
        # Count POVs by status - use EXACT values from database
        try:
            status_counts = db.session.query(
                POV.status, func.count(POV.id)
            ).filter_by(deleted=False).group_by(POV.status).all()
            print(f"Debug - Status counts: {status_counts}")
        except Exception as e:
            print(f"Error in status counts: {e}")
            status_counts = []
        
        # Format for chart with percentages
        status_labels = []
        status_data = []
        total_povs = sum([count for _, count in status_counts])
        for status, count in status_counts:
            percentage = round((count / total_povs) * 100, 1) if total_povs > 0 else 0
            status_labels.append(f"{status}: {count} ({percentage}%)")
            status_data.append(count)
        
        # Count POVs by stage - for ACTIVE POVs
        try:
            stage_counts = db.session.query(
                POV.current_stage, func.count(POV.id)
            ).filter_by(deleted=False).filter(
                POV.status.in_(['In Trial', 'Pending Sales'])
            ).group_by(POV.current_stage).all()
            print(f"Debug - Stage counts: {stage_counts}")
        except Exception as e:
            print(f"Error in stage counts: {e}")
            stage_counts = []
        
        stage_labels = [stage for stage, _ in stage_counts]
        stage_data = [count for _, count in stage_counts]
        
        # Count POVs by SE - for ACTIVE POVs
        try:
            se_counts = db.session.query(
                POV.assigned_se, func.count(POV.id)
            ).filter_by(deleted=False).filter(
                POV.status.in_(['In Trial', 'Pending Sales'])
            ).group_by(POV.assigned_se).all()
            print(f"Debug - SE counts: {se_counts}")
        except Exception as e:
            print(f"Error in SE counts: {e}")
            se_counts = []
        
        se_labels = [se for se, _ in se_counts]
        se_data = [count for _, count in se_counts]
        
        # Calculate basic metrics and advanced/fixed metrics
        try:
            two_weeks_from_now = today + timedelta(days=14)
            ending_soon = POV.query.filter(
                POV.deleted == False,
                POV.status.in_(['In Trial', 'Pending Sales']),
                POV.projected_end_date.between(today, two_weeks_from_now)
            ).count()
            
            overdue = POV.query.filter(
                POV.deleted == False,
                POV.status.in_(['In Trial', 'Pending Sales']),
                POV.projected_end_date < today
            ).count()
            
            active_povs = POV.query.filter(
                POV.deleted == False,
                POV.status.in_(['In Trial', 'Pending Sales'])
            ).all()
            
            durations = [(pov.projected_end_date - pov.start_date).days for pov in active_povs if pov.projected_end_date and pov.start_date]
            avg_duration = sum(durations) / len(durations) if durations else 0
            
            # Total value for active POVs
            total_value = db.session.query(func.sum(POV.deal_amount)).filter(
                POV.deleted == False,
                POV.status.in_(['In Trial', 'Pending Sales'])
            ).scalar() or 0
            
            ninety_days_ago = today - timedelta(days=90)
            
            won_count = POV.query.filter(
                POV.deleted == False,
                POV.status == 'Closed Won',
                POV.updated_at >= ninety_days_ago
            ).count()
            
            lost_count = POV.query.filter(
                POV.deleted == False,
                POV.status == 'Closed Lost',
                POV.updated_at >= ninety_days_ago
            ).count()
            
            # FIXED ADVANCED METRICS - Only count completed POVs
            technical_wins = POV.query.filter(
                POV.deleted == False,
                POV.technical_win == 'Yes'
            ).count()
            
            povs_in_progress = POV.query.filter(
                POV.deleted == False,
                POV.status.in_(['In Trial', 'Pending Sales'])
            ).count()
            
            # Only completed POVs for conversion calculations
            completed_povs = POV.query.filter(
                POV.deleted == False,
                POV.status.in_(['Closed Won', 'Closed Lost'])
            ).count()
            
            total_closed_won = POV.query.filter(
                POV.deleted == False,
                POV.status == 'Closed Won'
            ).count()
            
            # POV to Closed Won Conversion Rate (only completed POVs)
            pov_conversion_rate = round((total_closed_won / completed_povs) * 100, 1) if completed_povs > 0 else 0
            
            # Technical Win Rate (only completed POVs)
            technical_win_rate = round((technical_wins / completed_povs) * 100, 1) if completed_povs > 0 else 0
            
            # STAGE COUNTS for new metric cards
            deployment_count = POV.query.filter(
                POV.deleted == False,
                POV.current_stage == 'Deployment',
                POV.status.in_(['In Trial', 'Pending Sales'])
            ).count()
            
            training1_count = POV.query.filter(
                POV.deleted == False,
                POV.current_stage == 'Training 1',
                POV.status.in_(['In Trial', 'Pending Sales'])
            ).count()
            
            training2_count = POV.query.filter(
                POV.deleted == False,
                POV.current_stage == 'Training 2',
                POV.status.in_(['In Trial', 'Pending Sales'])
            ).count()
            
            wrapup_count = POV.query.filter(
                POV.deleted == False,
                POV.current_stage == 'POV Wrap-Up',
                POV.status.in_(['In Trial', 'Pending Sales'])
            ).count()
            
            print(f"Debug - Fixed Metrics: pov_conversion={pov_conversion_rate}% (was including pending), tech_win_rate={technical_win_rate}%")
            print(f"Debug - Stage Counts: deployment={deployment_count}, training1={training1_count}, training2={training2_count}, wrapup={wrapup_count}")
            
        except Exception as e:
            print(f"Error calculating metrics: {e}")
            ending_soon = overdue = avg_duration = total_value = won_count = lost_count = 0
            technical_wins = pov_conversion_rate = technical_win_rate = povs_in_progress = 0
            deployment_count = training1_count = training2_count = wrapup_count = 0
        
        # Monthly POV starts
        try:
            monthly_data = []
            monthly_labels = []
            for i in range(6, 0, -1):
                month_start = today.replace(day=1) - timedelta(days=30*i)
                month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                
                count = POV.query.filter(
                    POV.deleted == False,
                    POV.start_date >= month_start,
                    POV.start_date <= month_end
                ).count()
                
                monthly_data.append(count)
                monthly_labels.append(month_start.strftime('%b %Y'))
            
        except Exception as e:
            print(f"Error in monthly data: {e}")
            monthly_labels = ['6 months ago', '5 months ago', '4 months ago', '3 months ago', '2 months ago', 'Last month']
            monthly_data = [1, 2, 3, 2, 4, 3]
        
        return render_template(
            'analytics.html',
            status_labels=status_labels,
            status_data=status_data,
            stage_labels=stage_labels,
            stage_data=stage_data,
            se_labels=se_labels,
            se_data=se_data,
            ending_soon=ending_soon,
            overdue=overdue,
            avg_duration=round(avg_duration, 1),
            total_value=total_value,
            won_count=won_count,
            lost_count=lost_count,
            months=monthly_labels,
            month_data=monthly_data,
            # FIXED ADVANCED METRICS
            technical_wins=technical_wins,
            pov_conversion_rate=pov_conversion_rate,
            technical_win_rate=technical_win_rate,
            povs_in_progress=povs_in_progress,
            # NEW STAGE COUNT METRICS
            deployment_count=deployment_count,
            training1_count=training1_count,
            training2_count=training2_count,
            wrapup_count=wrapup_count
        )
    except Exception as e:
        flash(f'Error loading analytics: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/init_db')
def init_database():
    """Route to manually initialize the database"""
    if init_db():
        flash('Database initialized successfully!', 'success')
    else:
        flash('Error initializing database.', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/pov/<int:pov_id>/roadblock', methods=['GET', 'POST'])
def manage_roadblock(pov_id):
    pov = POV.query.get_or_404(pov_id)
    if request.method == 'POST':
        pov.roadblock_category = request.form.get('roadblock_category')
        pov.roadblock_severity = request.form.get('roadblock_severity')
        pov.roadblock_owner = request.form.get('roadblock_owner')
        pov.roadblock_notes = request.form.get('roadblock_notes')
        if not pov.roadblock_created_date:
            pov.roadblock_created_date = datetime.utcnow().date()
        if request.form.get('action') == 'resolve':
            pov.roadblock_resolved_date = datetime.utcnow().date()
        elif request.form.get('action') == 'reopen':
            pov.roadblock_resolved_date = None
        db.session.commit()
        flash('Roadblock updated successfully!', 'success')
        return redirect(url_for('pov_detail', id=pov_id))
    return render_template('roadblock_form.html', pov=pov)

def get_roadblock_analytics():
    """Get comprehensive roadblock analytics"""
    active_roadblocks = POV.query.filter(
        POV.deleted == False,
        POV.roadblock_category.isnot(None),
        POV.roadblock_resolved_date.is_(None)
    ).all()
    category_counts = {}
    severity_counts = {'High': 0, 'Medium': 0, 'Low': 0}
    owner_counts = {'AE': 0, 'SE': 0, 'Leadership': 0, 'Engineering': 0}
    total_stagnant_days = 0
    high_priority_stagnant = []
    for pov in active_roadblocks:
        category = pov.roadblock_category or 'Unspecified'
        category_counts[category] = category_counts.get(category, 0) + 1
        if pov.roadblock_severity in severity_counts:
            severity_counts[pov.roadblock_severity] += 1
        if pov.roadblock_owner in owner_counts:
            owner_counts[pov.roadblock_owner] += 1
        days_stagnant = pov.days_stagnant
        total_stagnant_days += days_stagnant
        if (pov.roadblock_severity == 'High' and days_stagnant > 7) or days_stagnant > 14:
            high_priority_stagnant.append({
                'pov': pov,
                'days_stagnant': days_stagnant,
                'company': getattr(pov, 'company_name', pov.deal_name)
            })
    avg_stagnant_days = total_stagnant_days / len(active_roadblocks) if active_roadblocks else 0
    return {
        'total_active_roadblocks': len(active_roadblocks),
        'category_counts': category_counts,
        'severity_counts': severity_counts,
        'owner_counts': owner_counts,
        'avg_stagnant_days': round(avg_stagnant_days, 1),
        'high_priority_stagnant': sorted(high_priority_stagnant, key=lambda x: x['days_stagnant'], reverse=True)
    }

@app.route('/roadblocks/analytics')
def roadblock_analytics():
    analytics = get_roadblock_analytics()
    return render_template('roadblock_analytics.html', analytics=analytics)

if __name__ == '__main__':
    # Do NOT call init_db() automatically here!
    # init_db()
    app.run(debug=True)