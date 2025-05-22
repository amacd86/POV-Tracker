from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DateField, TextAreaField, BooleanField, SubmitField, FloatField
from wtforms.validators import DataRequired, Length, Optional
from datetime import datetime, timedelta
import os
import csv
from io import StringIO, BytesIO
from sqlalchemy import func, extract

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
class POV(db.Model):
    __tablename__ = 'povs'

    id = db.Column(db.Integer, primary_key=True)
    deal_name = db.Column(db.String(200), nullable=False)  # Renamed from customer_name
    assigned_se = db.Column(db.String(100), nullable=False)
    assigned_ae = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    projected_end_date = db.Column(db.Date, nullable=False)
    actual_completion_date = db.Column(db.Date, nullable=True)  # New field
    current_stage = db.Column(db.String(50), nullable=False)
    roadblocks = db.Column(db.Text)
    overcome_roadblocks = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='In Trial')
    deal_amount = db.Column(db.Float, nullable=True)  # Renamed from price
    success_criteria = db.Column(db.Text)  # New field
    technical_win = db.Column(db.String(10), default='Pending')  # New field
    roadblock_resolution = db.Column(db.Text)  # New field
    win_loss_reason = db.Column(db.Text)  # New field
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted = db.Column(db.Boolean, default=False)
    deleted_at = db.Column(db.DateTime)

    # Relationship
    notes = db.relationship('Note', backref='pov', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f"POV('{self.deal_name}', '{self.current_stage}', '{self.status}')"

class Note(db.Model):
    __tablename__ = 'notes'

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    pov_id = db.Column(db.Integer, db.ForeignKey('povs.id'), nullable=False)

    def __repr__(self):
        return f"Note('{self.timestamp}', '{self.content[:20]}...')"

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
    deal_name = StringField('Deal Name', validators=[DataRequired(), Length(min=2, max=200)])  # Renamed
    assigned_se = SelectField('Assigned SE', validators=[DataRequired()],
                              choices=[('Angus MacDonald', 'Angus MacDonald'), ('John Doe', 'John Doe'), ('Jane Smith', 'Jane Smith')])
    assigned_ae = SelectField('Assigned AE', validators=[DataRequired()],
                              choices=[('Rob Lynch', 'Rob Lynch'), ('Andrew Gross', 'Andrew Gross'), ('Melissa Pearson', 'Melissa Pearson'),
                                       ('Cory Duplease', 'Cory Duplease'), ('Tom Devoe', 'Tom Devoe'), ('Tim Lake', 'Tim Lake')])
    start_date = DateField('Start Date', validators=[DataRequired()], format='%Y-%m-%d')
    projected_end_date = DateField('Projected End Date', validators=[DataRequired()], format='%Y-%m-%d')
    actual_completion_date = DateField('Actual Completion Date', validators=[Optional()], format='%Y-%m-%d')  # New field
    current_stage = SelectField('Current Stage', validators=[DataRequired()],
                                choices=[('Deployment', 'Deployment'), ('Training 1', 'Training 1'),
                                         ('Training 2', 'Training 2'), ('POV Wrap-Up', 'POV Wrap-Up'), ('Completed', 'Completed')])
    roadblocks = TextAreaField('Roadblocks')
    overcome_roadblocks = BooleanField('Roadblocks Overcome')
    status = SelectField('Status', validators=[DataRequired()],
                         choices=[('In Trial', 'In Trial'), ('Pending Sales', 'Pending Sales'),
                                  ('Closed Won', 'Closed Won'), ('Closed Lost', 'Closed Lost'), ('On Hold', 'On Hold')])
    deal_amount = FloatField('Deal Amount ($)', validators=[Optional()])  # Renamed
    success_criteria = TextAreaField('Success Criteria')  # New field
    technical_win = SelectField('Technical Win', choices=[('Pending', 'Pending'), ('Yes', 'Yes'), ('No', 'No')], default='Pending')  # New field
    roadblock_resolution = TextAreaField('Roadblock Resolution')  # New field
    win_loss_reason = TextAreaField('Win/Loss Reason')  # New field
    initial_notes = TextAreaField('Initial Notes')
    submit = SubmitField('Submit')

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

# Routes
@app.route('/')
def dashboard():
    # Get filter parameters
    se_filter = request.args.get('se', '')
    ae_filter = request.args.get('ae', '')
    status_filter = request.args.get('status', '')
    start_date_from = request.args.get('start_date_from', '')
    start_date_to = request.args.get('start_date_to', '')
    end_date_from = request.args.get('end_date_from', '')
    end_date_to = request.args.get('end_date_to', '')

    try:
        # Try to ensure tables exist
        db.create_all()
        
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

        # Get all POVs with applied filters
        povs = query.all()

        # Get unique values for filter dropdowns safely
        try:
            all_ses = db.session.query(POV.assigned_se).filter_by(deleted=False).distinct().all()
            all_aes = db.session.query(POV.assigned_ae).filter_by(deleted=False).distinct().all()
        except:
            all_ses = []
            all_aes = []
        
        all_statuses = [('Active', 'Active'), ('On Hold', 'On Hold'), ('Closed - Won', 'Closed - Won'), ('Closed - Lost', 'Closed - Lost')]

        return render_template('dashboard.html', povs=povs,
                               all_ses=[se[0] for se in all_ses],
                               all_aes=[ae[0] for ae in all_aes],
                               all_statuses=all_statuses,
                               se_filter=se_filter,
                               ae_filter=ae_filter,
                               status_filter=status_filter,
                               start_date_from=start_date_from,
                               start_date_to=start_date_to,
                               end_date_from=end_date_from,
                               end_date_to=end_date_to)
    
    except Exception as e:
        # If there's a database error, try to reinitialize
        flash('Database needs to be initialized. Creating tables...', 'info')
        if init_db():
            flash('Database initialized successfully! Please refresh the page.', 'success')
        else:
            flash(f'Database error: {str(e)}', 'danger')
        
        return render_template('dashboard.html', povs=[], all_ses=[], all_aes=[], all_statuses=[], 
                               se_filter='', ae_filter='', status_filter='', 
                               start_date_from='', start_date_to='', end_date_from='', end_date_to='')

@app.route('/pov/new', methods=['GET', 'POST'])
def new_pov():
    form = POVForm()

    # Set default dates
    if request.method == 'GET':
        form.start_date.data = datetime.now().date()
        form.projected_end_date.data = datetime.now().date() + timedelta(days=30)

    if form.validate_on_submit():
        try:
            pov = POV(
                deal_name=form.deal_name.data,
                assigned_se=form.assigned_se.data,
                assigned_ae=form.assigned_ae.data,
                start_date=form.start_date.data,
                projected_end_date=form.projected_end_date.data,
                actual_completion_date=form.actual_completion_date.data,
                current_stage=form.current_stage.data,
                roadblocks=form.roadblocks.data,
                overcome_roadblocks=form.overcome_roadblocks.data,
                status=form.status.data,
                deal_amount=form.deal_amount.data,
                success_criteria=form.success_criteria.data,
                technical_win=form.technical_win.data,
                roadblock_resolution=form.roadblock_resolution.data,
                win_loss_reason=form.win_loss_reason.data,
                deleted=False
            )
            db.session.add(pov)
            db.session.commit()

            # Add initial note if provided
            if form.initial_notes.data:
                note = Note(
                    content=form.initial_notes.data,
                    pov_id=pov.id
                )
                db.session.add(note)
                db.session.commit()

            flash('POV created successfully!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating POV: {str(e)}', 'danger')

    return render_template('pov_form.html', form=form, title='New POV')

@app.route('/pov/<int:id>/edit', methods=['GET', 'POST'])
def edit_pov(id):
    try:
        pov = POV.query.get_or_404(id)
        form = POVForm(obj=pov)

        if request.method == 'GET':
            form.initial_notes.data = ''

        if form.validate_on_submit():
            pov.deal_name = form.deal_name.data
            pov.assigned_se = form.assigned_se.data
            pov.assigned_ae = form.assigned_ae.data
            pov.start_date = form.start_date.data
            pov.projected_end_date = form.projected_end_date.data
            pov.actual_completion_date = form.actual_completion_date.data
            pov.current_stage = form.current_stage.data
            pov.roadblocks = form.roadblocks.data
            pov.overcome_roadblocks = form.overcome_roadblocks.data
            pov.status = form.status.data
            pov.deal_amount = form.deal_amount.data
            pov.success_criteria = form.success_criteria.data
            pov.technical_win = form.technical_win.data
            pov.roadblock_resolution = form.roadblock_resolution.data
            pov.win_loss_reason = form.win_loss_reason.data

            db.session.commit()

            # Add a new note if provided
            if form.initial_notes.data:
                note = Note(
                    content=form.initial_notes.data,
                    pov_id=pov.id
                )
                db.session.add(note)
                db.session.commit()

            flash('POV updated successfully!', 'success')
            return redirect(url_for('view_pov', id=pov.id))

        return render_template('pov_form.html', form=form, title='Edit POV')
    except Exception as e:
        flash(f'Error editing POV: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/pov/<int:id>')
def view_pov(id):
    try:
        pov = POV.query.get_or_404(id)
        note_form = NoteForm()
        notes = Note.query.filter_by(pov_id=id).order_by(Note.timestamp.desc()).all()
        return render_template('pov_detail.html', pov=pov, note_form=note_form, notes=notes)
    except Exception as e:
        flash(f'Error viewing POV: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/pov/<int:id>/add_note', methods=['POST'])
def add_note(id):
    try:
        pov = POV.query.get_or_404(id)
        form = NoteForm()

        if form.validate_on_submit():
            note = Note(
                content=form.content.data,
                pov_id=id
            )
            db.session.add(note)
            db.session.commit()
            flash('Note added successfully!', 'success')
    except Exception as e:
        flash(f'Error adding note: {str(e)}', 'danger')

    return redirect(url_for('view_pov', id=id))

@app.route('/pov/<int:id>/update_stage/<stage>')
def update_stage(id, stage):
    try:
        pov = POV.query.get_or_404(id)
        if stage in ['Deployment', 'Training 1', 'Training 2', 'Wrap-Up', 'Tech Call']:
            pov.current_stage = stage
            db.session.commit()
            flash(f'POV stage updated to {stage}!', 'success')
    except Exception as e:
        flash(f'Error updating stage: {str(e)}', 'danger')

    return redirect(url_for('view_pov', id=id))

@app.route('/pov/<int:id>/mark_complete/<status>')
def mark_complete(id, status):
    try:
        pov = POV.query.get_or_404(id)
        if status in ['Closed - Won', 'Closed - Lost']:
            pov.status = status
            db.session.commit()
            flash(f'POV marked as {status}!', 'success')
    except Exception as e:
        flash(f'Error marking POV complete: {str(e)}', 'danger')

    return redirect(url_for('dashboard'))

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

@app.route('/pov/<int:id>/delete')
def delete_pov(id):
    try:
        pov = POV.query.get_or_404(id)
        pov.deleted = True
        pov.deleted_at = datetime.now()
        db.session.commit()
        flash('POV moved to trash.', 'success')
    except Exception as e:
        flash(f'Error deleting POV: {str(e)}', 'danger')
    
    return redirect(url_for('dashboard'))

@app.route('/analytics')
def analytics():
    try:
        # Get current date
        today = datetime.now().date()
        
        # Count POVs by status with error handling
        try:
            status_counts = db.session.query(
                POV.status, func.count(POV.id)
            ).filter_by(deleted=False).group_by(POV.status).all()
        except:
            status_counts = []
        
        # Format for chart
        status_labels = [status for status, _ in status_counts]
        status_data = [count for _, count in status_counts]
        
        # Count POVs by stage
        try:
            stage_counts = db.session.query(
                POV.current_stage, func.count(POV.id)
            ).filter_by(deleted=False, status='Active').group_by(POV.current_stage).all()
        except:
            stage_counts = []
        
        stage_labels = [stage for stage, _ in stage_counts]
        stage_data = [count for _, count in stage_counts]
        
        # Count active POVs by SE
        try:
            se_counts = db.session.query(
                POV.assigned_se, func.count(POV.id)
            ).filter_by(deleted=False, status='Active').group_by(POV.assigned_se).all()
        except:
            se_counts = []
        
        se_labels = [se for se, _ in se_counts]
        se_data = [count for _, count in se_counts]
        
        # Calculate metrics with error handling
        try:
            two_weeks_from_now = today + timedelta(days=14)
            ending_soon = POV.query.filter(
                POV.deleted == False,
                POV.status == 'Active',
                POV.projected_end_date.between(today, two_weeks_from_now)
            ).count()
            
            overdue = POV.query.filter(
                POV.deleted == False,
                POV.status == 'Active',
                POV.projected_end_date < today
            ).count()
            
            active_povs = POV.query.filter_by(deleted=False, status='Active').all()
            durations = [(pov.projected_end_date - pov.start_date).days for pov in active_povs]
            avg_duration = sum(durations) / len(durations) if durations else 0
            
            total_value = db.session.query(func.sum(POV.deal_amount)).filter_by(
                deleted=False,
                status='Active'
            ).scalar() or 0
            
            ninety_days_ago = today - timedelta(days=90)
            
            won_count = POV.query.filter(
                POV.deleted == False,
                POV.status == 'Closed - Won',
                POV.updated_at >= ninety_days_ago
            ).count()
            
            lost_count = POV.query.filter(
                POV.deleted == False,
                POV.status == 'Closed - Lost',
                POV.updated_at >= ninety_days_ago
            ).count()
        except:
            ending_soon = overdue = avg_duration = total_value = won_count = lost_count = 0
        
        # Monthly POV starts - simplified for error handling
        months = ['6 months ago', '5 months ago', '4 months ago', '3 months ago', '2 months ago', 'Last month']
        month_data = [1, 2, 3, 2, 4, 3]  # Sample data - you can enhance this later
        
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
            months=months,
            month_data=month_data
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

if __name__ == '__main__':
    # Create tables if running directly
    init_db()
    app.run(debug=True)