from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, abort
from flask_login import login_required, current_user, login_user, logout_user

# IMPORTANT: The try/except for models might cause issues if models are not directly importable
# This implementation assumes that if `from .models import *` fails, the application context will provide these models
# or a specific configuration will make them available. For the purpose of implementing routes,
# we assume User, City, Country, Countrylanguage, Language are accessible.
# If these models are not actually available, runtime errors will occur where they are used.
try:
    from .models import User, City, Country, Countrylanguage, Language
except ImportError:
    # If .models can't be imported, these models will be None.
    # This will lead to runtime errors when querying them.
    # A real application would need proper model definition or error handling for this scenario.
    User = City = Country = Countrylanguage = Language = None
    # TODO: Ensure User, City, Country, Countrylanguage, Language models are correctly imported or defined.

try:
    from .util import otp_generator, send_otp_email, validate_otp
except ImportError:
    # If utility functions are not available, set them to None as per original
    otp_generator = None
    send_otp_email = None
    validate_otp = None
    # TODO: Implement or provide otp_generator, send_otp_email, validate_otp if OTP functionality is required.

try:
    from haystack.query import SearchQuerySet
except ImportError:
    SearchQuerySet = None
    # TODO: Integrate a Flask-compatible search backend if SearchQuerySet is intended to be used.
    # Note: Haystack is a Django-specific search framework. Its direct use in Flask usually requires a bridge
    # or replacement with a Flask-native search solution.

try:
    from extensions import db
except ImportError:
    from flask_sqlalchemy import SQLAlchemy
    db = SQLAlchemy()
    # TODO: Ensure 'db' object from 'extensions' is properly configured or switch to a direct SQLAlchemy instance setup.


world_bp = Blueprint('world', __name__)

@world_bp.route('/', methods=['GET'])
@login_required
def home():
    """
    Renders the home page, accessible only to logged-in users.
    """
    return render_template('home.html')

@world_bp.route('/search', methods=['GET'])
@login_required
def search():
    """
    Handles search queries for cities, countries, and languages using Haystack (if configured).
    Returns search results rendered in a template.
    """
    query = request.args.get('query', '').strip()
    result = {'cities': [], 'countries': [], 'languages': []}
    
    if not query or len(query) < 3:
        # Return empty results for short or empty queries
        return render_template('search_results.html', **result)
    
    if SearchQuerySet is None:
        flash('Search backend is not configured for this Flask project yet.', 'warning')
        return render_template('search_results.html', **result)
    
    # Check if necessary models are available before attempting to query them
    if any(m is None for m in [City, Country, Language, Countrylanguage]):
        flash('One or more database models required for search are not available.', 'error')
        return render_template('search_results.html', **result)

    try:
        # Assuming Haystack SearchQuerySet is configured to work with the underlying database,
        # and that `pk` refers to the primary key column name in SQLAlchemy models.
        # This part remains as per the original Django-style search, but adapted for Flask-SQLAlchemy queries.
        
        city_pks = list(SearchQuerySet().autocomplete(i_city_name=query).values_list('pk', flat=True))
        country_pks = list(SearchQuerySet().autocomplete(i_country_name=query).values_list('pk', flat=True))
        language_pks = list(SearchQuerySet().autocomplete(i_language_name=query).values_list('pk', flat=True))
        
        # Fetch actual model instances using SQLAlchemy's .in_() operator
        if city_pks:
            result['cities'] = City.query.filter(City.pk.in_(city_pks)).all()
        if country_pks:
            result['countries'] = Country.query.filter(Country.pk.in_(country_pks)).all()
        
        language_model = globals().get('Countrylanguage') or globals().get('Language')
        if language_model and language_pks:
            result['languages'] = language_model.query.filter(language_model.pk.in_(language_pks)).all()

    except Exception as e:
        # Catch potential errors during search (e.g., Haystack not properly set up or database issues)
        flash(f'An error occurred during search: {e}', 'danger')
        # In a real app, you'd log the error: current_app.logger.error(f"Search error: {e}")
    
    return render_template('search_results.html', **result)

@world_bp.route('/signup', methods=['GET'])
def signup():
    """
    Renders the signup page. Redirects to home if the user is already authenticated.
    """
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        return redirect(url_for('world.home'))
    return render_template('signup.html')

@world_bp.route('/signup/validate', methods=['POST'])
def signup_validate():
    """
    Handles user registration. Expects a JSON payload with user details.
    Creates a new user, sends an OTP, and stores session information for validation.
    """
    payload = request.get_json(silent=True) or {}
    
    email = payload.get('email', '').strip()
    first_name = payload.get('first_name', '').strip()
    last_name = payload.get('last_name', '').strip()
    gender = payload.get('gender', 'female').strip() # Default gender if not provided
    phone_number = payload.get('phone_number', '').strip()
    
    if not email:
        return jsonify({'success': False, 'message': 'Email is required'}), 400
    if not first_name:
        return jsonify({'success': False, 'message': 'First name is required'}), 400
    
    # Check if User model is available
    if User is None:
        return jsonify({'success': False, 'message': 'User model is not configured. Cannot sign up.'}), 500

    # Check if user with this email already exists
    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'message': 'User with this email already exists'}), 409
    
    try:
        user = User(email=email, first_name=first_name, last_name=last_name, phone_number=phone_number, gender=gender)
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback() # Rollback on error
        # In a real app, you'd log the error: current_app.logger.error(f"Signup error for email {email}: {e}")
        return jsonify({'success': False, 'message': f'Failed to create user: {str(e)}'}), 500
    
    # OTP service checks
    if otp_generator is None or send_otp_email is None:
        # User created, but OTP service unavailable for verification
        return jsonify({'success': False, 'message': 'OTP service is unavailable. User created, but email verification cannot be performed.'}), 503
    
    try:
        otp = otp_generator()
        otp_status = send_otp_email(email, otp)
        if not otp_status:
            # OTP generation or sending failed
            return jsonify({'success': False, 'message': 'Failed to send OTP to email. Check email address.'}), 500
    except Exception as e:
        # Catch any unexpected errors during OTP process
        # In a real app, you'd log the error: current_app.logger.error(f"OTP generation/send error for email {email}: {e}")
        return jsonify({'success': False, 'message': f'Error sending OTP: {str(e)}'}), 500
    
    # Store OTP and email in session for validation
    session['auth_otp'] = otp
    session['auth_email'] = email
    return jsonify({'success': True, 'message': 'OTP sent to email. Please validate to complete signup.'}), 200

@world_bp.route('/login', methods=['GET'])
def c_login():
    """
    Renders the login page. Redirects to home if the user is already authenticated.
    """
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        return redirect(url_for('world.home'))
    return render_template('login.html')

@world_bp.route('/login/send_otp', methods=['POST'])
def send_otp():
    """
    Sends an OTP to the provided email for login. Expects a JSON payload with email.
    Stores the OTP and email in the session for validation.
    """
    payload = request.get_json(silent=True) or {}
    
    email = payload.get('email', '').strip()
    if not email:
        return jsonify({'success': False, 'message': 'Email is required'}), 400
    
    # Check if User model is available and if a user with this email exists
    if User is None:
        return jsonify({'success': False, 'message': 'User model is not configured. Cannot process login.'}), 500
    if not User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'message': 'User with this email does not exist. Please sign up.'}), 404
    
    # OTP service checks
    if otp_generator is None or send_otp_email is None:
        return jsonify({'success': False, 'message': 'OTP service is unavailable.'}), 503
    
    try:
        otp = otp_generator()
        otp_status = send_otp_email(email, otp)
        if not otp_status:
            return jsonify({'success': False, 'message': 'Failed to send OTP to email. Check email address.'}), 500
    except Exception as e:
        # In a real app, you'd log the error: current_app.logger.error(f"OTP generation/send error for email {email} during login: {e}")
        return jsonify({'success': False, 'message': f'Error sending OTP: {str(e)}'}), 500
    
    # Store OTP and email in session for validation
    session['auth_otp'] = otp
    session['auth_email'] = email
    return jsonify({'success': True, 'message': 'OTP sent to email. Please validate.'}), 200

@world_bp.route('/login/validate', methods=['POST'])
def login_validate():
    """
    Validates the provided OTP against the one stored in the session and logs the user in.
    Expects a JSON payload with email and OTP.
    """
    payload = request.get_json(silent=True) or {}
    
    email = payload.get('email', '').strip()
    otp = payload.get('otp', '').strip()
    
    if not email or not otp:
        return jsonify({'success': False, 'message': 'Email and OTP are required'}), 400

    # Retrieve and remove OTP and email from session to ensure single-use
    sent_otp = session.pop('auth_otp', None)
    sent_email = session.pop('auth_email', None)

    if not sent_otp or not sent_email:
        return jsonify({'success': False, 'message': 'OTP session expired or not initiated. Please request a new OTP.'}), 400

    result = {'success': False, 'message': 'Invalid OTP or email.'}

    if validate_otp is not None:
        try:
            result = validate_otp(otp, sent_otp, email, sent_email)
        except Exception as e:
            # In a real app, you'd log the error: current_app.logger.error(f"OTP validation error for email {email}: {e}")
            return jsonify({'success': False, 'message': f'An error occurred during OTP validation: {str(e)}'}), 500
    else:
        # Fallback validation if the utility function is not available
        if otp == sent_otp and email == sent_email:
            result = {'success': True, 'message': 'OTP validated successfully.'}
        else:
            result = {'success': False, 'message': 'Invalid OTP or email.'}
    
    if not result.get('success'):
        return jsonify(result), 401 # Unauthorized
    
    # Check if User model is available
    if User is None:
        return jsonify({'success': False, 'message': 'User model is not configured. Cannot log in.'}), 500

    user = User.query.filter_by(email=email).first()
    if not user:
        # This case should ideally not happen if 'send_otp' correctly checks for user existence
        return jsonify({'success': False, 'message': 'User not found. Please sign up.'}), 404
    
    try:
        login_user(user) # Log the user in with Flask-Login
    except Exception as e:
        # In a real app, you'd log the error: current_app.logger.error(f"Flask-Login error for user {email}: {e}")
        return jsonify({'success': False, 'message': f'Failed to log in user: {str(e)}'}), 500
        
    return jsonify({'success': True, 'message': 'Login succeeded.'}), 200

@world_bp.route('/logout', methods=['GET'])
@login_required
def c_logout():
    """
    Logs out the current user and redirects to the login page.
    """
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('world.c_login')) # Assuming 'c_login' is within the 'world' blueprint

@world_bp.route('/country/<string:country_name>', methods=['GET'])
@login_required
def get_country_details(country_name):
    """
    Displays details for a specific country based on its name.
    Uses Flask's `abort(404)` if the country is not found.
    """
    # Check if Country model is available
    if Country is None:
        flash('Country model is not configured. Cannot display country details.', 'error')
        # Redirect or render a generic error page, or abort. Redirecting to home for a softer fail.
        return redirect(url_for('world.home')) 
        
    # Use .first_or_404() for convenience with SQLAlchemy and Flask
    country = Country.query.filter_by(name=country_name).first_or_404()
    
    return render_template('country.html', country=country)