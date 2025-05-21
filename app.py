from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DateField, TextAreaField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-for-pov-tracker')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pov_tracker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Custom Jinja2 filters and globals
@app.template_filter('nl2br')
def nl2br_filter(s):
    if s:
        return s.replace('\n', '<br>')
    return s

@app.context_processor
def inject_now():
    return {'now': datetime.now}

# Import models after db initialization to avoid circular imports
from models import POV, Note

# Forms
class POVForm(FlaskForm):
    customer_name = StringField('Customer Name', validators=[DataRequired(), Length(min=2, max=100)])
    assigned_se = SelectField('Assigned SE', validators=[DataRequired()], 
                              choices=[('John Doe', 'John Doe'), ('Jane Smith', 'Jane Smith'), ('Bob Johnson', 'Bob Johnson')])
    assigned_ae = SelectField('Assigned AE', validators=[DataRequired()],
                              choices=[('Alex Brown', 'Alex Brown'), ('Sarah Lee', 'Sarah Lee'), ('Mike Wilson', 'Mike Wilson')])
    start_date = DateField('Start Date', validators=[DataRequired()], format='%Y-%m-%d')
    projected_end_date = DateField('Projected End Date', validators=[DataRequired()], format='%Y-%m-%d')
    current_stage = SelectField('Current Stage', validators=[DataRequired()],
                                choices=[('Deployment', 'Deployment'), ('Training 1', 'Training 1'), 
                                         ('Training 2', 'Training 2'), ('Wrap-Up', 'Wrap-Up'), ('Tech Call', 'Tech Call')])
    roadblocks = TextAreaField('Roadblocks')
    overcome_roadblocks = BooleanField('Roadblocks Overcome')
    status = SelectField('Status', validators=[DataRequired()],
                         choices=[('Active', 'Active'), ('On Hold', 'On Hold'), ('Closed - Won', 'Closed - Won'), ('Closed - Lost', 'Closed - Lost')])
    initial_notes = TextAreaField('Initial Notes')  # Add this line
    submit = SubmitField('Submit')

class NoteForm(FlaskForm):
    content = TextAreaField('Note', validators=[DataRequired()])
    submit = SubmitField('Add Note')
    

# Routes
@app.route('/')
def dashboard():
    # Get filter parameters
    se_filter = request.args.get('se', '')
    ae_filter = request.args.get('ae', '')
    status_filter = request.args.get('status', '')
    
    # Base query
    query = POV.query
    
    # Apply filters if provided
    if se_filter:
        query = query.filter(POV.assigned_se == se_filter)
    if ae_filter:
        query = query.filter(POV.assigned_ae == ae_filter)
    if status_filter:
        query = query.filter(POV.status == status_filter)
    
    # Get all POVs with applied filters
    povs = query.all()
    
    # Get unique values for filter dropdowns
    all_ses = db.session.query(POV.assigned_se).distinct().all()
    all_aes = db.session.query(POV.assigned_ae).distinct().all()
    all_statuses = [('Active', 'Active'), ('On Hold', 'On Hold'), ('Closed - Won', 'Closed - Won'), ('Closed - Lost', 'Closed - Lost')]
    
    return render_template('dashboard.html', povs=povs,
                           all_ses=[se[0] for se in all_ses],
                           all_aes=[ae[0] for ae in all_aes],
                           all_statuses=all_statuses,
                           se_filter=se_filter,
                           ae_filter=ae_filter,
                           status_filter=status_filter)

@app.route('/pov/new', methods=['GET', 'POST'])
def new_pov():
    form = POVForm()
    
    # Set default dates
    if request.method == 'GET':
        form.start_date.data = datetime.now()
        form.projected_end_date.data = datetime.now() + timedelta(days=30)
    
    if form.validate_on_submit():
        pov = POV(
            customer_name=form.customer_name.data,
            assigned_se=form.assigned_se.data,
            assigned_ae=form.assigned_ae.data,
            start_date=form.start_date.data,
            projected_end_date=form.projected_end_date.data,
            current_stage=form.current_stage.data,
            roadblocks=form.roadblocks.data,
            overcome_roadblocks=form.overcome_roadblocks.data,
            status=form.status.data
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
    
    return render_template('pov_form.html', form=form, title='New POV')

@app.route('/pov/<int:id>/edit', methods=['GET', 'POST'])
def edit_pov(id):
    pov = POV.query.get_or_404(id)
    form = POVForm(obj=pov)
    
    if request.method == 'GET':
        # For edit, don't set initial_notes as it would create duplicate notes
        form.initial_notes.data = ''
    
    if form.validate_on_submit():
        pov.customer_name = form.customer_name.data
        pov.assigned_se = form.assigned_se.data
        pov.assigned_ae = form.assigned_ae.data
        pov.start_date = form.start_date.data
        pov.projected_end_date = form.projected_end_date.data
        pov.current_stage = form.current_stage.data
        pov.roadblocks = form.roadblocks.data
        pov.overcome_roadblocks = form.overcome_roadblocks.data
        pov.status = form.status.data
        
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

@app.route('/pov/<int:id>')
def view_pov(id):
    pov = POV.query.get_or_404(id)
    note_form = NoteForm()
    notes = Note.query.filter_by(pov_id=id).order_by(Note.timestamp.desc()).all()
    
    return render_template('pov_detail.html', pov=pov, note_form=note_form, notes=notes)

@app.route('/pov/<int:id>/add_note', methods=['POST'])
def add_note(id):
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
    
    return redirect(url_for('view_pov', id=id))

@app.route('/pov/<int:id>/update_stage/<stage>')
def update_stage(id, stage):
    pov = POV.query.get_or_404(id)
    if stage in ['Deployment', 'Training 1', 'Training 2', 'Wrap-Up', 'Tech Call']:
        pov.current_stage = stage
        db.session.commit()
        flash(f'POV stage updated to {stage}!', 'success')
    
    return redirect(url_for('view_pov', id=id))

@app.route('/pov/<int:id>/mark_complete/<status>')
def mark_complete(id, status):
    pov = POV.query.get_or_404(id)
    if status in ['Closed - Won', 'Closed - Lost']:
        pov.status = status
        db.session.commit()
        flash(f'POV marked as {status}!', 'success')
    
    return redirect(url_for('dashboard'))

@app.route('/export_csv')
def export_csv():
    # This would be implemented in a future version
    flash('Export feature will be available in a future update', 'info')
    return redirect(url_for('dashboard'))

# Initialize the database
@app.cli.command('init-db')
def init_db():
    db.create_all()
    print('Database initialized!')

# Add sample data
@app.cli.command('seed-db')
def seed_db():
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

if __name__ == '__main__':
    app.run(debug=True)