import os
import csv
from datetime import datetime, timedelta
from io import StringIO, BytesIO
from collections import Counter
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, DateField, TextAreaField, BooleanField, SubmitField, FloatField
from wtforms.validators import DataRequired, Email, Optional
from sqlalchemy import func

# ===================================================================
#  APP & DB CONFIGURATION
# ===================================================================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a-very-secret-key-that-is-long-and-secure')
basedir = os.path.abspath(os.path.dirname(__file__))
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
#  CONTEXT PROCESSORS & HELPERS
# ===================================================================
@app.context_processor
def inject_now():
    return {'now': datetime.utcnow}

@app.template_filter('nl2br')
def nl2br_filter(s):
    """Converts newlines in a string to HTML <br> tags."""
    if s:
        # Use the safe way to prevent HTML injection
        from markupsafe import Markup
        return Markup(s.replace('\n', '<br>\n'))
    return s

def get_pov_metrics():
    today = datetime.utcnow().date()
    won_statuses = ['Closed Won', 'Closed - Won']
    lost_statuses = ['Closed Lost', 'Closed - Lost']
    completed_statuses = won_statuses + lost_statuses
    active_statuses = ['In Trial', 'Pending Sales', 'Active', 'On Hold']
    all_povs = POV.query.filter_by(deleted=False).all()
    active_povs_list = [p for p in all_povs if p.status in active_statuses]
    completed_povs_list = [p for p in all_povs if p.status in completed_statuses]
    ending_soon = len([p for p in active_povs_list if p.projected_end_date and today <= p.projected_end_date <= (today + timedelta(days=14))])
    overdue = len([p for p in active_povs_list if p.projected_end_date and p.projected_end_date < today])
    durations = [(p.projected_end_date - p.start_date).days for p in active_povs_list if p.projected_end_date and p.start_date]
    avg_duration = sum(durations) / len(durations) if durations else 0
    total_value = sum(p.deal_amount for p in active_povs_list if p.deal_amount)
    closed_won_count = len([p for p in completed_povs_list if p.status in won_statuses])
    completed_count = len(completed_povs_list)
    pov_conversion_rate = (closed_won_count / completed_count) * 100 if completed_count > 0 else 0
    technical_wins_count = len([p for p in completed_povs_list if p.technical_win])
    tech_win_rate = (technical_wins_count / completed_count) * 100 if completed_count > 0 else 0
    stage_counts = {
        'deployment': len([p for p in active_povs_list if p.current_stage == 'Deployment']),
        'training_1': len([p for p in active_povs_list if p.current_stage == 'Training 1']),
        'training_2': len([p for p in active_povs_list if p.current_stage == 'Training 2']),
        'pov_wrap_up': len([p for p in active_povs_list if p.current_stage == 'POV Wrap-Up']),
    }
    return {
        'total_povs': len(all_povs), 'povs_in_progress': len(active_povs_list), 'completed_povs': completed_count,
        'ending_soon': ending_soon, 'overdue': overdue, 'avg_duration': round(avg_duration, 1),
        'total_value': total_value or 0, 'technical_wins': technical_wins_count, 'closed_won_count': closed_won_count,
        'pov_conversion_rate': round(pov_conversion_rate, 1), 'tech_win_rate': round(tech_win_rate, 1), 'stage_counts': stage_counts,
    }

# ===================================================================
#  ROUTES
# ===================================================================
@app.route('/')
def dashboard():
    povs, all_ses, all_aes, all_statuses = [], [], [], []
    se_filter, ae_filter, status_filter = '', '', ''
    start_date_from, start_date_to, end_date_from, end_date_to = '', '', '', ''
    try:
        se_filter = request.args.get('se', '')
        ae_filter = request.args.get('ae', '')
        status_filter = request.args.get('status', '')
        query = POV.query.filter_by(deleted=False)
        if se_filter: query = query.filter(POV.assigned_se == se_filter)
        if ae_filter: query = query.filter(POV.assigned_ae == ae_filter)
        if status_filter: query = query.filter(POV.status == status_filter)
        povs = query.order_by(POV.start_date.desc()).all()
        all_ses = sorted([se[0] for se in db.session.query(POV.assigned_se).filter(POV.assigned_se.isnot(None)).distinct().all()])
        all_aes = sorted([ae[0] for ae in db.session.query(POV.assigned_ae).filter(POV.assigned_ae.isnot(None)).distinct().all()])
        all_statuses = [('Active', 'Active'), ('On Hold', 'On Hold'), ('Closed Won', 'Closed Won'), ('Closed Lost', 'Closed Lost'), ('Pending Sales', 'Pending Sales')]
    except Exception as e:
        flash(f'An error occurred while loading the dashboard: {e}', 'danger')
    return render_template('dashboard.html',
                           povs=povs, all_ses=all_ses, all_aes=all_aes, all_statuses=all_statuses,
                           se_filter=se_filter, ae_filter=ae_filter, status_filter=status_filter,
                           start_date_from=start_date_from, start_date_to=start_date_to,
                           end_date_from=end_date_from, end_date_to=end_date_to)

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
        form.populate_obj(pov)
        db.session.add(pov)
        db.session.commit()
        flash('POV created successfully!', 'success')
        return redirect(url_for('pov_detail', pov_id=pov.id))
    return render_template('pov_form.html', form=form, title='New POV')

@app.route('/pov/<int:pov_id>/edit', methods=['GET', 'POST'])
def edit_pov(pov_id):
    pov = POV.query.get_or_404(pov_id)
    form = POVForm(obj=pov)
    if form.validate_on_submit():
        old_roadblock_category = pov.roadblock_category
        form.populate_obj(pov)
        if form.roadblock_category.data and not old_roadblock_category:
            pov.roadblock_created_date = datetime.utcnow().date()
            pov.roadblock_resolved_date = None
        elif not form.roadblock_category.data and old_roadblock_category:
            pov.roadblock_resolved_date = datetime.utcnow().date()
        pov.updated_at = datetime.utcnow()
        db.session.commit()
        flash('POV updated successfully!', 'success')
        return redirect(url_for('pov_detail', pov_id=pov.id))
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

@app.route('/analytics')
def analytics():
    metrics = get_pov_metrics()
    status_counts = db.session.query(POV.status, func.count(POV.id)).filter_by(deleted=False).group_by(POV.status).all()
    stage_counts_active = db.session.query(POV.current_stage, func.count(POV.id)).filter_by(deleted=False).filter(POV.status.in_(['In Trial', 'Pending Sales'])).group_by(POV.current_stage).all()
    return render_template('analytics.html', metrics=metrics,
                           status_chart_data=[{'label': status, 'value': count} for status, count in status_counts],
                           stage_chart_data=[{'label': stage, 'value': count} for stage, count in stage_counts_active])

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

@app.route('/export_csv')
def export_csv():
    try:
        povs = POV.query.filter_by(deleted=False).order_by(POV.start_date.desc()).all()
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Deal Name', 'Customer Name', 'Assigned SE', 'Assigned AE', 'Stage', 'Status', 'Start Date', 'Projected End Date', 'Actual Completion Date', 'Deal Amount ($)', 'Technical Win', 'Success Criteria', 'Roadblock Category', 'Roadblock Severity', 'Roadblock Owner', 'Roadblock Notes'])
        for pov in povs:
            writer.writerow([
                pov.deal_name, pov.customer_name, pov.assigned_se, pov.assigned_ae, pov.current_stage, pov.status,
                pov.start_date.strftime('%Y-%m-%d') if pov.start_date else '',
                pov.projected_end_date.strftime('%Y-%m-%d') if pov.projected_end_date else '',
                pov.actual_completion_date.strftime('%Y-%m-%d') if pov.actual_completion_date else '',
                pov.deal_amount, 'Yes' if pov.technical_win else 'No', pov.success_criteria,
                pov.roadblock_category, pov.roadblock_severity, pov.roadblock_owner, pov.roadblock_notes
            ])
        output.seek(0)
        output_bytes = BytesIO(output.getvalue().encode('utf-8-sig'))
        return send_file(output_bytes, mimetype='text/csv', as_attachment=True, download_name=f'pov_export_{datetime.utcnow().strftime("%Y-%m-%d")}.csv')
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
        povs_to_update = POV.query.filter(POV.id.in_(selected_povs)).all()
        for pov in povs_to_update:
            if action == 'delete':
                pov.deleted = True
                pov.deleted_at = datetime.utcnow()
            elif action == 'mark_won':
                pov.status = 'Closed Won'
            elif action == 'mark_lost':
                pov.status = 'Closed Lost'
        db.session.commit()
        flash(f'{len(povs_to_update)} POVs updated.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred: {e}', 'danger')
    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)