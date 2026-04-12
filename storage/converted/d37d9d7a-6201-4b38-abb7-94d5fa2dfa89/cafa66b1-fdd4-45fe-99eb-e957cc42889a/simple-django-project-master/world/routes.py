from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user, login_user, logout_user
try:
    from .models import User, Country, City, Language # Explicitly import models used
except ImportError:
    # As per instructions, do not invent model classes.
    # If these models are not available, the routes using them will fail.
    # This block prevents import error if models are in a different setup, but
    # the code assumes they exist for the functionality.
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
    """Renders the home page, accessible only to logged-in users."""
    return render_template('home.html')

@world_bp.route('/search', methods=['GET'])
@login_required
def search():
    """
    Handles global search across countries, cities, and languages.
    Requires a minimum query length.
    """
    query = request.args.get('query', '').strip()
    result = {'cities': [], 'countries': [], 'languages': []}
    
    if not query or len(query) < 3:
        # If query is too short or empty, return results template with empty lists
        return render_template('search_results.html', query=query, **result)
    
    try:
        # Search backend integration using SQLAlchemy
        # Using ilike for case-insensitive partial matching
        result['countries'] = Country.query.filter(Country.name.ilike(f'%{query}%')).all()
        result['cities'] = City.query.filter(City.name.ilike(f'%{query}%')).all()
        result['languages'] = Language.query.filter(Language.name.ilike(f'%{query}%')).all()
    except Exception as e:
        # Log the exception for debugging purposes
        print(f"Error during search: {e}")
        flash("An error occurred during search. Please try again.", 'danger')
        # Ensure result is empty on error
        result = {'cities': [], 'countries': [], 'languages': []}
        
    return render_template('search_results.html', query=query, **result)

@world_bp.route('/signup', methods=['GET'])
def signup():
    """Renders the signup page."""
    return render_template('signup.html')

@world_bp.route('/signup/validate', methods=['POST'])
def signup_validate():
    """
    Validates signup data, creates a new user, and sends a placeholder OTP.
    Expects JSON payload.
    """
    payload = request.get_json(silent=True) or {}
    
    email = payload.get('email', '')
    if not email:
        return jsonify({'success': False, 'message': 'Email not provided'})
    first_name = payload.get('first_name', '')
    last_name = payload.get('last_name', '')
    gender = payload.get('gender', 'female') # Default 'female' as per original
    phone_number = payload.get('phone_number', '')
    
    if not first_name:
        return jsonify({'success': False, 'message': 'First name not provided'})
    
    # Check if a user with this email already exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({'success': False, 'message': 'User with this email already exists. Please login.'})

    try:
        user = User(email=email, first_name=first_name, last_name=last_name, phone_number=phone_number, gender=gender)
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        # More specific error message could be derived from 'e' if needed
        return jsonify({'success': False, 'message': f'Failed to create user: {str(e)}'})
    
    # OTP delivery integration requires project-specific mail implementation.
    # Placeholder OTP for demonstration.
    otp = '000000' # In a real app, this would be generated and emailed
    session['auth_otp'] = otp
    session['auth_email'] = email
    # Consider adding an OTP expiry time to the session as well.
    
    flash("A verification code has been sent to your email. Please check your inbox.", 'success')
    return jsonify({'success': True, 'message': 'OTP sent to email'})

@world_bp.route('/login', methods=['GET'])
def c_login():
    """Renders the login page."""
    return render_template('login.html')

@world_bp.route('/login/send_otp', methods=['POST'])
def send_otp():
    """
    Sends a placeholder OTP to the user's email for login.
    Expects JSON payload.
    """
    payload = request.get_json(silent=True) or {}
    
    email = payload.get('email', '')
    if not email:
        return jsonify({'success': False, 'message': 'Email not provided'})
    
    # Check if the user exists before sending an OTP for login
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'success': False, 'message': 'No account found with that email. Please sign up.'})

    # OTP delivery integration requires project-specific mail implementation.
    # Placeholder OTP for demonstration.
    otp = '000000' # In a real app, this would be generated and emailed
    session['auth_otp'] = otp
    session['auth_email'] = email
    # Consider adding an OTP expiry time to the session as well.
    
    flash("A verification code has been sent to your email. Please check your inbox.", 'success')
    return jsonify({'success': True, 'message': 'OTP sent to email'})

@world_bp.route('/login/validate', methods=['POST'])
def login_validate():
    """
    Validates the provided OTP against the one in session and logs the user in.
    Expects JSON payload.
    """
    payload = request.get_json(silent=True) or {}
    
    email = payload.get('email', '')
    otp = payload.get('otp', '')
    
    # Retrieve and clear OTP/email from session to prevent replay attacks
    sent_otp = session.pop('auth_otp', None)
    sent_email = session.pop('auth_email', None)
    
    if not otp or otp != sent_otp or email != sent_email:
        flash("Invalid or expired OTP. Please try again.", 'danger')
        return jsonify({'success': False, 'message': 'Invalid OTP'})
    
    user = User.query.filter_by(email=email).first()
    if not user:
        flash("No account found with that email. Please sign up.", 'warning')
        return jsonify({'success': False, 'message': 'Please signup'})
    
    login_user(user)
    flash(f"Welcome back, {user.first_name}!", 'success')
    return jsonify({'success': True, 'message': 'Login succeeded'})

@world_bp.route('/logout', methods=['GET'])
@login_required
def c_logout():
    """Logs out the current user and redirects to the login page."""
    logout_user()
    flash("You have been logged out.", 'info')
    return redirect(url_for('world.c_login')) # Use blueprint name for url_for

@world_bp.route('/country/<path:country_name>', methods=['GET'])
@login_required
def get_country_details(country_name):
    """
    Retrieves and displays details for a specific country by its name.
    Uses Flask's path converter to allow slashes in country names if needed.
    """
    # Get specific Country using SQLAlchemy's query.filter_by and first_or_404
    # .first_or_404() automatically raises a 404 error if no country is found.
    country = Country.query.filter_by(name=country_name).first_or_404()
    
    return render_template('country.html', country=country)
