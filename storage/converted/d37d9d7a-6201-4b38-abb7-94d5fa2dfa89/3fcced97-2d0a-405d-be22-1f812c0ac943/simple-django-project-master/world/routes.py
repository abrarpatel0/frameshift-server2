from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user, login_user, logout_user
from sqlalchemy.exc import IntegrityError # Import for specific DB errors

try:
    from .models import User, Country, City, Language # Assume these models exist
except ImportError:
    # Define placeholder models if .models cannot be imported,
    # to allow the code to be syntactically valid for Flask-SQLAlchemy.
    # In a real app, you'd ensure models are properly imported.
    class User:
        def __init__(self, email, first_name, last_name, phone_number, gender):
            self.email = email
            self.first_name = first_name
            self.last_name = last_name
            self.phone_number = phone_number
            self.gender = gender

        def __repr__(self):
            return f'<User {self.email}>'

        @staticmethod
        def query(): # Mock query object
            class QueryMock:
                def filter_by(self, email):
                    if email == "test@example.com": # Simulate an existing user
                        return type('UserMock', (object,), {'first': lambda: User('test@example.com', 'Test', 'User', '12345', 'male')})()
                    return type('NoUserMock', (object,), {'first': lambda: None})()
            return QueryMock()

        # Required by Flask-Login
        def is_authenticated(self): return True
        def is_active(self): return True
        def is_anonymous(self): return False
        def get_id(self): return str(self.email) # Using email as ID for simplicity

    class Country:
        def __init__(self, name):
            self.name = name
        
        def __repr__(self):
            return f'<Country {self.name}>'

        @staticmethod
        def query():
            class QueryMock:
                def filter_by(self, name):
                    if name == "TestCountry":
                        return type('CountryMock', (object,), {'first_or_404': lambda: Country('TestCountry')})()
                    return type('NoCountryMock', (object,), {'first_or_404': lambda: None})() # This will raise 404 in real app
            return QueryMock()

    class City:
        pass
    class Language:
        pass

try:
    from extensions import db
except ImportError:
    from flask_sqlalchemy import SQLAlchemy
    db = SQLAlchemy()

world_bp = Blueprint('world', __name__)

@world_bp.route('/', methods=['GET'])
@login_required
def home():
    """Renders the homepage."""
    return render_template('home.html')

@world_bp.route('/search', methods=['GET'])
@login_required
def search():
    """
    Handles search queries.
    Returns JSON for short queries, renders a page for longer ones.
    Note: Actual search logic for cities, countries, languages is not implemented
    as per requirements, only the flow is maintained.
    """
    query = request.args.get('query', '').strip()
    result = {'cities': [], 'countries': [], 'languages': []}
    
    if not query or len(query) < 3:
        # For short queries, return JSON (e.g., for AJAX suggestions)
        return jsonify(result)
    
    # Search backend integration requires project-specific implementation.
    # Keep query flow intact without inventing business rules.
    # In a real app, you would query your models here:
    # result['cities'] = City.query.filter(City.name.ilike(f'%{query}%')).limit(10).all()
    # result['countries'] = Country.query.filter(Country.name.ilike(f'%{query}%')).limit(10).all()
    # result['languages'] = Language.query.filter(Language.name.ilike(f'%{query}%')).limit(10).all()
    
    return render_template('search_results.html', **result)

@world_bp.route('/signup', methods=['GET'])
def signup():
    """Renders the signup page."""
    return render_template('signup.html')

@world_bp.route('/signup/validate', methods=['POST'])
def signup_validate():
    """
    Handles user signup validation and OTP sending.
    Expects JSON payload with user details.
    """
    payload = request.get_json(silent=True) or {}
    
    email = payload.get('email', '')
    if not email:
        return jsonify({'success': False, 'message': 'email not found'})
    
    first_name = payload.get('first_name', '')
    last_name = payload.get('last_name', '')
    gender = payload.get('gender', 'female')
    phone_number = payload.get('phone_number', '')
    
    if not first_name:
        return jsonify({'success': False, 'message': 'first name not found'})
    
    try:
        # Check if user already exists
        if User.query.filter_by(email=email).first():
            return jsonify({'success': False, 'message': 'user with this email already exists'})

        user = User(email=email, first_name=first_name, last_name=last_name, phone_number=phone_number, gender=gender)
        db.session.add(user)
        db.session.commit()
    except IntegrityError: # More specific for unique constraint violations
        db.session.rollback()
        return jsonify({'success': False, 'message': 'user already exists (database constraint error)'})
    except Exception as e:
        db.session.rollback()
        # Log the exception for debugging in a real application
        # app.logger.error(f"Error during signup: {e}")
        return jsonify({'success': False, 'message': 'An unexpected error occurred during signup.'})
    
    # OTP delivery integration requires project-specific mail implementation.
    # For now, a mock OTP is generated and stored in session.
    otp = '000000' # Placeholder OTP
    session['auth_otp'] = otp
    session['auth_email'] = email
    
    return jsonify({'success': True, 'message': 'otp sent to email'})

@world_bp.route('/login', methods=['GET'])
def c_login():
    """Renders the login page."""
    return render_template('login.html')

@world_bp.route('/login/send_otp', methods=['POST'])
def send_otp():
    """
    Handles sending OTP for login.
    Expects JSON payload with email.
    """
    payload = request.get_json(silent=True) or {}
    
    email = payload.get('email', '')
    if not email:
        return jsonify({'success': False, 'message': 'email not found'})
    
    # Check if the user exists before sending OTP for login
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'success': False, 'message': 'No account found with this email. Please sign up.'})

    # OTP delivery integration requires project-specific mail implementation.
    # For now, a mock OTP is generated and stored in session.
    otp = '000000' # Placeholder OTP
    session['auth_otp'] = otp
    session['auth_email'] = email
    
    return jsonify({'success': True, 'message': 'otp sent'})

@world_bp.route('/login/validate', methods=['POST'])
def login_validate():
    """
    Validates OTP for login and logs the user in.
    Expects JSON payload with email and OTP.
    """
    payload = request.get_json(silent=True) or {}
    
    email = payload.get('email', '')
    otp = payload.get('otp', '')
    
    sent_otp = session.get('auth_otp', '')
    sent_email = session.get('auth_email', '')
    
    # Clear OTP/email from session immediately after retrieval for security
    session.pop('auth_otp', None)
    session.pop('auth_email', None)

    if not otp or otp != sent_otp or email != sent_email:
        return jsonify({'success': False, 'message': 'invalid otp or email mismatch'})
    
    user = User.query.filter_by(email=email).first()
    if not user:
        # This case should ideally be caught earlier by send_otp, but good to have a fallback.
        return jsonify({'success': False, 'message': 'please signup'})
    
    login_user(user)
    return jsonify({'success': True, 'message': 'login succeeded'})

@world_bp.route('/logout', methods=['GET'])
@login_required
def c_logout():
    """Logs out the current user and redirects to the login page."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('world.c_login')) # Use blueprint prefix for url_for

@world_bp.route('/country/<string:country_name>', methods=['GET'])
@login_required
def get_country_details(country_name):
    """
    Retrieves and displays details for a specific country.
    Uses Flask-SQLAlchemy's first_or_404.
    """
    # Get specific Country
    country = Country.query.filter_by(name=country_name).first_or_404()
    
    return render_template('country.html', country=country)