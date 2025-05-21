# POV Tracker - Sales Engineering

A Flask-based web application for managing customer Proof of Value (POV) engagements for sales engineering teams.

## Features

- Track POV status, stage, and progress
- Assign POVs to Sales Engineers and Account Executives
- Record roadblocks and notes
- Filter and search for POVs
- Export POV data to CSV (future)

## Project Structure

```
pov-tracker/
│
├── app.py                 # Main application file
├── models.py              # Database models
├── pov_tracker.db         # SQLite database (generated)
│
├── templates/             # Jinja2 templates
│   ├── layout.html        # Base template
│   ├── dashboard.html     # Main dashboard view
│   ├── pov_form.html      # Add/Edit POV form
│   └── pov_detail.html    # Detailed POV view
│
└── static/                # Static assets (CSS, JS, etc.)
    └── custom.css         # Custom styling (optional)
```

## Tech Stack

- **Flask**: Web framework
- **Flask-SQLAlchemy**: ORM for database operations
- **WTForms**: Form handling and validation
- **Bootstrap 5**: Responsive UI components
- **SQLite**: Database (easily upgradable to PostgreSQL)

## Setup and Installation

### Prerequisites

- Python 3.8+
- pip

### Installation Steps

1. Clone the repository:
   ```
   git clone <repository-url>
   cd pov-tracker
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install flask flask-sqlalchemy flask-wtf
   ```

4. Initialize the database:
   ```
   flask init-db
   ```

5. (Optional) Add sample data:
   ```
   flask seed-db
   ```

6. Run the application:
   ```
   flask run
   ```

7. Access the application in your browser at `http://127.0.0.1:5000/`

## Usage

### Dashboard

- Overview of all POVs
- Filter by SE, AE, or status
- Quick actions: View, Edit, Mark Complete

### Adding a New POV

1. Click "New POV" button from dashboard
2. Fill in required fields
3. Submit the form

### Managing POVs

1. View POV details
2. Add notes
3. Update stages
4. Mark POVs as complete (Won/Lost)

## Future Enhancements

- User authentication
- Advanced filtering and sorting
- Export data to CSV/Excel
- Email notifications
- Integration with CRM systems

## License

This project is proprietary and confidential.