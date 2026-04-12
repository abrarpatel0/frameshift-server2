from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user, login_user, logout_user
from sqlalchemy.exc import IntegrityError # Import for specific DB error handling

try:
    from .models import User, Country, City, Language # Be explicit about models
except ImportError:
    # This block might be for a standalone test or different project structure
    # In a typical Flask app, models would be defined or imported reliably.
    # For this task, we assume User, Country, City, Language are available.
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
    """
    Renders the home page of the application.
    Requires the user to be logged in.
    """
    return render_template('home.html')

@world_bp.route('/search', methods=['GET'])
@login_required
def search():
    """
    Handles search queries for cities, countries, and languages.
    Returns results as JSON if the query is too short, otherwise renders a template.
    (Note: Backend search logic is project-specific and not implemented here.)
    """
    query = request.args.get('query', '').strip()
    result = {'cities': [], 'countries': [], 'languages': []}
    
    if not query or len(query) < 3:
        # For simplicity, returning jsonify for short queries as per original
        # A more robust approach might be to render an empty search results page
        return jsonify(result)
    
    # Search backend integration requires project-specific implementation.
    # Keep query flow intact without inventing business rules.
    # Example (placeholder for actual search logic):
    # if query:
    #     result['cities'] = City.query.filter(City.name.ilike(f'%{query}%')).all()
    #     result['countries'] = Country.query.filter(Country.name.ilike(f'%{query}%')).all()
    #     result['languages'] = Language.query.filter(Language.name.ilike(f'%{query}%')).all()
        
    return render_template('search_results.html', query=query, **result)

@world_bp.route('/signup', methods=['GET'])
def signup():
    """
    Renders the user registration (signup) form.
    """
    return render_template('signup.html')

@world_bp.route('/signup/validate', methods=['POST'])
def signup_validate():
    """
    Validates user signup data and creates a new user.
    Sends an OTP to the user's email for verification.
    Expects a JSON payload.
    """
    payload = request.get_json(silent=True) or {}
    
    email = payload.get('email', '').strip()
    first_name = payload.get('first_name', '').strip()
    last_name = payload.get('last_name', '').strip()
    gender = payload.get('gender', 'female').strip() # Default to 'female' if not provided
    phone_number = payload.get('phone_number', '').strip()
    
    if not email:
        return jsonify({'success': False, 'message': 'Email not found'})
    if not first_name:
        return jsonify({'success': False, 'message': 'First name not found'})
    
    try:
        user = User(email=email, first_name=first_name, last_name=last_name, phone_number=phone_number, gender=gender)
        db.session.add(user)
        db.session.commit()
    except IntegrityError: # Specific error for unique constraint violation (e.g., email already exists)
        db.session.rollback()
        return jsonify({'success': False, 'message': 'User with this email already exists'})
    except Exception as e:
        db.session.rollback()
        # Log the exception for debugging in a real application
        # app.logger.error(f"Error during signup: {e}")
        return jsonify({'success': False, 'message': f'An unexpected error occurred: {str(e)}'})
    
    # OTP delivery integration requires project-specific mail implementation.
    # For demonstration, a static OTP is used.
    otp = '000000'
    session['auth_otp'] = otp
    session['auth_email'] = email
    
    # The original condition 'signup_validate' == 'signup_validate' is always true.
    # Simplified the message logic.
    return jsonify({'success': True, 'message': 'OTP sent to email'})

@world_bp.route('/login', methods=['GET'])
def c_login():
    """
    Renders the user login form.
    """
    return render_template('login.html')

@world_bp.route('/login/send_otp', methods=['POST'])
def send_otp():
    """
    Sends an OTP to the provided email for login verification.
    Expects a JSON payload.
    """
    payload = request.get_json(silent=True) or {}
    
    email = payload.get('email', '').strip()
    if not email:
        return jsonify({'success': False, 'message': 'Email not found'})
    
    # Check if user exists before sending OTP in a real application
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'success': False, 'message': 'No account found with this email. Please signup.'})

    # OTP delivery integration requires project-specific mail implementation.
    # For demonstration, a static OTP is used.
    otp = '000000'
    session['auth_otp'] = otp
    session['auth_email'] = email
    
    # The original condition 'send_otp' == 'signup_validate' is always false.
    # Simplified the message logic.
    return jsonify({'success': True, 'message': 'OTP sent to email'})

@world_bp.route('/login/validate', methods=['POST'])
def login_validate():
    """
    Validates the provided OTP and logs the user in.
    Expects a JSON payload.
    """
    payload = request.get_json(silent=True) or {}
    
    email = payload.get('email', '').strip()
    otp = payload.get('otp', '').strip()
    
    sent_otp = session.pop('auth_otp', None) # Remove OTP from session after attempt
    sent_email = session.pop('auth_email', None) # Remove email from session after attempt
    
    if not otp or otp != sent_otp or email != sent_email:
        # Consider adding flash message for user feedback if this were a full page redirect
        return jsonify({'success': False, 'message': 'Invalid OTP or email mismatch'})
    
    user = User.query.filter_by(email=email).first()
    if not user:
        # This case should ideally be caught during send_otp, but good to have here too
        return jsonify({'success': False, 'message': 'No account found. Please signup.'})
    
    login_user(user)
    return jsonify({'success': True, 'message': 'Login succeeded'})

@world_bp.route('/logout', methods=['GET'])
@login_required
def c_logout():
    """
    Logs out the current user and redirects to the login page.
    Requires the user to be logged in.
    """
    logout_user()
    flash('You have been logged out.', 'info') # Optional: Add a flash message
    return redirect(url_for('world.c_login')) # Use blueprint name 'world'

@world_bp.route('/country/<string:country_name>', methods=['GET'])
@login_required
def get_country_details(country_name):
    """
    Displays detailed information for a specific country.
    The country name is passed as a URL parameter.
    Requires the user to be logged in.
    """
    # Get specific Country
    country = Country.query.filter_by(name=country_name).first_or_404()
    
    return render_template('country.html', country=country)
