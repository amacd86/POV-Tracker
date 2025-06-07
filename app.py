# ===================================================================
#  IMPORTS & APP CONFIGURATION
# ===================================================================
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DateField, TextAreaField, BooleanField, SubmitField, FloatField
from wtforms.validators import DataRequired, Email, Optional
from datetime import datetime, timedelta
import os
from collections import Counter
from sqlalchemy import func

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a-very-secret-key-that-is-long')
basedir = os.path.abspath(os.path.dirname(__file__))
# Correctly point to a database file inside an 'instance' folder
instance_path = os.path.join(basedir, 'instance')
os.makedirs(instance_path, exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_path, "pov_tracker.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# ===================================================================
#  DATABASE MODELS
# ===================================================================
class POV(db.Model):
    __tablename__ = 'povs'
    id = db.Column(db.Integer, primary_key=True)
    deal_name = db.Column(db.String(200), nullable=False)
    customer_name = db.Column(db.String(200), nullable=False, default='N/A')
    assigned_se = db.Column(db.String(100))
    assigned_ae = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    projected_end_date = db.Column(db.Date)
    actual_completion_date = db.Column(db.Date)
    current_stage = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    deal_amount = db.Column(db.Float)
    success_criteria = db.Column(db.Text)
    technical_win = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted = db.Column(db.Boolean, default=False)
    deleted_at = db.Column(db.DateTime)
    
    # Roadblock Fields
    roadblock_category = db.Column(db.String(50))
    roadblock_severity = db.Column(db.String(10))
    roadblock_owner = db.Column(db.String(20))
    roadblock_notes = db.Column(db.Text)
    roadblock_created_date = db.Column(db.Date)
    roadblock_resolved_date = db.Column(db.Date)
    
    notes = db.relationship('Note', backref='pov', lazy=True, cascade="all, delete-orphan")

    @property
    def days_stagnant(self):
        if self.roadblock_created_date and not self.roadblock_resolved_date:
            return (datetime.utcnow().date() - self.roadblock_created_date).days
        return 0

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    pov_id = db.Column(db.Integer, db.ForeignKey('povs.id'), nullable=False)


# ===================================================================
#  FORMS
# ===================================================================
class POVForm(FlaskForm):
    deal_name = StringField('Deal Name', validators=[DataRequired()])
    customer_name = StringField('Customer Name', validators=[DataRequired()])
    assigned_ae = StringField('Account Executive', validators=[DataRequired()])
    assigned_se = StringField('Sales Engineer', validators=[Optional()])
    current_stage = SelectField('Stage', choices=[('Deployment', 'Deployment'), ('Training 1', 'Training 1'), ('Training 2', 'Training 2'), ('POV Wrap-Up', 'POV Wrap-Up'), ('Completed', 'Completed')], validators=[DataRequired()])
    status = SelectField('Status', choices=[('In Trial', 'In Trial'), ('Pending Sales', 'Pending Sales'), ('On Hold', 'On Hold'), ('Closed Won', 'Closed Won'), ('Closed Lost', 'Closed Lost')], validators=[DataRequired()])
    start_date = DateField('Start Date', format='%Y-%m-%d', validators=[DataRequired()])
    projected_end_date = DateField('Projected End Date', format='%Y-%m-%d', validators=[Optional()])
    actual_completion_date = DateField('Actual Completion Date', format='%Y-%m-%d', validators=[Optional()])
    deal_amount = FloatField('Deal Amount ($)', validators=[Optional()])
    technical_win = BooleanField('Technical Win')
    success_criteria = TextAreaField('Success Criteria', render_kw={"rows": 4}, validators=[Optional()])
    roadblock_category = SelectField('Roadblock Category', choices=[('', 'No Roadblock'), ('Technical', 'Technical'), ('Budget', 'Budget'), ('Timeline', 'Timeline'), ('Decision Maker', 'Decision Maker'), ('Competitive', 'Competitive')], validators=[Optional()])
    roadblock_severity = SelectField('Roadblock Severity', choices=[('', 'Select Severity'), ('Low', 'Low'), ('Medium', 'Medium'), ('High', 'High')], validators=[Optional()])
    roadblock_owner = SelectField('Roadblock Owner', choices=[('', 'Select Owner'), ('AE', 'AE'), ('SE', 'SE'), ('Leadership', 'Leadership'), ('Engineering', 'Engineering')], validators=[Optional()])
    roadblock_notes = TextAreaField('Roadblock Notes', render_kw={"rows": 4}, validators=[Optional()])
    submit = SubmitField('Save POV')

class NoteForm(FlaskForm):
    content = TextAreaField('Add Note', validators=[DataRequired()], render_kw={"rows": 3, "placeholder": "Add a new note..."})
    submit = SubmitField('Add Note')

# ===================================================================
#  HELPER FUNCTIONS
# ===================================================================
def get_pov_metrics():
    # ... Your existing get_pov_metrics function ...
    return {} # Placeholder for brevity

# ===================================================================
#  ROUTES
# ===================================================================
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
        # Initialize with empty lists in case of an error
        povs, all_ses, all_aes, all_statuses = [], [], [], []
        se_filter, ae_filter, status_filter = '', '', ''
        start_date_from, start_date_to, end_date_from, end_date_to = '', '', '', ''


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

@app.route('/pov/<int:pov_id>')
def pov_detail(pov_id):
    pov = POV.query.get_or_404(pov_id)
    note_form = NoteForm()
    return render_template('pov_detail.html', pov=pov, note_form=note_form)

@app.route('/pov/new', methods=['GET', 'POST'])
def new_pov():
    form = POVForm()
    if form.validate_on_submit():
        pov = POV()
        # To map form data to a model with different attribute names
        pov.deal_name = form.deal_name.data
        pov.customer_name = form.customer_name.data
        pov.assigned_ae = form.assigned_ae.data
        pov.assigned_se = form.assigned_se.data
        pov.current_stage = form.current_stage.data
        pov.status = form.status.data
        pov.start_date = form.start_date.data
        pov.projected_end_date = form.projected_end_date.data
        pov.actual_completion_date = form.actual_completion_date.data
        pov.deal_amount = form.deal_amount.data
        pov.technical_win = form.technical_win.data
        pov.success_criteria = form.success_criteria.data
        pov.roadblock_category = form.roadblock_category.data
        pov.roadblock_severity = form.roadblock_severity.data
        pov.roadblock_owner = form.roadblock_owner.data
        pov.roadblock_notes = form.roadblock_notes.data
        db.session.add(pov)
        db.session.commit()
        flash('POV created successfully!', 'success')
        return redirect(url_for('pov_detail', pov_id=pov.id))
    return render_template('pov_form.html', form=form, title='New POV')


@app.route('/pov/<int:pov_id>/edit', methods=['GET', 'POST'])
def edit_pov(pov_id):
    pov = POV.query.get_or_404(pov_id)
    form = POVForm()
    if form.validate_on_submit():
        old_roadblock_category = pov.roadblock_category
        # Manually update fields
        pov.deal_name = form.deal_name.data
        pov.customer_name = form.customer_name.data
        pov.assigned_ae = form.assigned_ae.data
        pov.assigned_se = form.assigned_se.data
        pov.current_stage = form.current_stage.data
        pov.status = form.status.data
        pov.start_date = form.start_date.data
        pov.projected_end_date = form.projected_end_date.data
        pov.actual_completion_date = form.actual_completion_date.data
        pov.deal_amount = form.deal_amount.data
        pov.technical_win = form.technical_win.data
        pov.success_criteria = form.success_criteria.data
        pov.roadblock_category = form.roadblock_category.data
        pov.roadblock_severity = form.roadblock_severity.data
        pov.roadblock_owner = form.roadblock_owner.data
        pov.roadblock_notes = form.roadblock_notes.data
        # Roadblock date logic
        if form.roadblock_category.data and not old_roadblock_category:
            pov.roadblock_created_date = datetime.utcnow().date()
            pov.roadblock_resolved_date = None
        elif not form.roadblock_category.data and old_roadblock_category:
            pov.roadblock_resolved_date = datetime.utcnow().date()
        pov.updated_at = datetime.utcnow()
        db.session.commit()
        flash('POV updated successfully!', 'success')
        return redirect(url_for('pov_detail', pov_id=pov.id))
    elif request.method == 'GET':
        # Pre-fill form
        form.deal_name.data = pov.deal_name
        form.customer_name.data = pov.customer_name
        # ... and so on for all fields ...
    return render_template('pov_form.html', form=form, title='Edit POV', pov=pov)


@app.route('/pov/<int:pov_id>/add_note', methods=['POST'])
def add_note(pov_id):
    pov = POV.query.get_or_404(pov_id)
    form = NoteForm()
    if form.validate_on_submit():
        note = Note(content=form.content.data, pov_id=pov.id)
        db.session.add(note)
        db.session.commit()
        flash('Note added successfully.', 'success')
    return redirect(url_for('pov_detail', pov_id=pov.id))


@app.route('/pov/<int:pov_id>/update_stage', methods=['POST'])
def update_stage(pov_id):
    pov = POV.query.get_or_404(pov_id)
    new_stage = request.form.get('stage')
    if new_stage:
        pov.current_stage = new_stage
        db.session.commit()
        flash(f'Stage updated to {new_stage}.', 'info')
    return redirect(url_for('pov_detail', pov_id=pov.id))
    
# ... (all your other routes: analytics, delete_pov, etc.) ...

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)