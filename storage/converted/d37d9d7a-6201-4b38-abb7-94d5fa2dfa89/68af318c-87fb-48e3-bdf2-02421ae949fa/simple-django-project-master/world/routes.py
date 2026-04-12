from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user, login_user, logout_user
try:
    # Attempt to import specific models. If .models cannot be imported,
    # these classes will not be defined. Routes will use globals().get()
    # to check for their presence before attempting to use them.
    from .models import User, City, Country, Countrylanguage
except ImportError:
    pass # Let globals().get() handle the case where models are not imported.

try:
    from .util import otp_generator, send_otp_email, validate_otp
except ImportError:
    # Set utility functions to None if import fails, routes will check for None.
    otp_generator = None
    send_otp_email = None
    validate_otp = None

try:
    from haystack.query import SearchQuerySet
except ImportError:
    # Set SearchQuerySet to None if import fails, search route will check for None.
    SearchQuerySet = None

try:
    from extensions import db
except ImportError:
    # Fallback for db if extensions module is not present.
    from flask_sqlalchemy import SQLAlchemy
    db = SQLAlchemy()

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
    Handles search queries across cities, countries, and languages using Haystack.
    Requires the Haystack search backend and relevant models to be configured.
    """
    query = request.args.get('query', '').strip()
    result = {'cities': [], 'countries': [], 'languages': []}
    
    # If query is too short, return empty results immediately
    if not query or len(query) < 3:
        return jsonify(result)
    
    # Check if SearchQuerySet (Haystack) is available
    if SearchQuerySet is None:
        flash('Search backend is not configured for this Flask project yet.', 'warning')
        # Even if search backend is not configured, render the results page with empty data
        return render_template('search_results.html', **result)
    
    # Dynamically get model classes to ensure they were imported successfully
    _City = globals().get('City')
    _Country = globals().get('Country')
    _Countrylanguage = globals().get('Countrylanguage')
    _Language = globals().get('Language') # Fallback if Countrylanguage is not used
    
    # If critical models are not available, inform and return empty results
    if not _City or not _Country:
        flash('Required database models (City or Country) are not available for search.', 'danger')
        return render_template('search_results.html', **result)

    # Perform autocomplete search using Haystack (SearchQuerySet)
    city_pks = list(SearchQuerySet().autocomplete(i_city_name=query).values_list('pk', flat=True))
    country_pks = list(SearchQuerySet().autocomplete(i_country_name=query).values_list('pk', flat=True))
    language_pks = list(SearchQuerySet().autocomplete(i_language_name=query).values_list('pk', flat=True))
    
    # Fetch actual model instances using SQLAlchemy ORM
    result['cities'] = [_City.query.filter_by(pk=city_pk).first() for city_pk in city_pks]
    result['countries'] = [_Country.query.filter_by(pk=country_pk).first() for country_pk in country_pks]
    
    # Handle language model dynamically based on what's available
    language_model = _Countrylanguage or _Language
    if language_model is not None:
        result['languages'] = [language_model.query.filter_by(pk=language_pk).first() for language_pk in language_pks]
    else:
        # If no language model is found, log or flash a message
        flash('Language model (Countrylanguage or Language) is not available, language search results may be incomplete.', 'info')
    
    return render_template('search_results.html', **result)

@world_bp.route('/signup', methods=['GET'])
def signup():
    """
    Renders the user signup form.
    """
    return render_template('signup.html')

@world_bp.route('/signup/validate', methods=['POST'])
def signup_validate():
    """
    Validates user signup details, attempts to create a new user,
    and sends an OTP for email verification.
    """
    payload = request.get_json(silent=True) or {}
    
    email = payload.get('email', '')
    first_name = payload.get('first_name', '')
    last_name = payload.get('last_name', '')
    gender = payload.get('gender', 'female')
    phone_number = payload.get('phone_number', '')
    
    # Basic input validation
    if not email:
        return jsonify({'success': False, 'message': 'Email address is required.'})
    if not first_name:
        return jsonify({'success': False, 'message': 'First name is required.'})

    _User = globals().get('User')
    if not _User:
        return jsonify({'success': False, 'message': 'User model not available, cannot complete signup.'})
    
    # Attempt to create a new user
    try:
        user = _User(email=email, first_name=first_name, last_name=last_name, phone_number=phone_number, gender=gender)
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback() # Rollback in case of any database error
        # A more specific check for unique constraint violation (e.g., email) could be added here
        return jsonify({'success': False, 'message': 'User with this email already exists or a database error occurred.'})
    
    # Check if OTP service is available
    if otp_generator is None or send_otp_email is None:
        # If OTP service is unavailable, it's problematic for verification.
        # For security, roll back user creation and inform the user.
        db.session.delete(user)
        db.session.commit()
        return jsonify({'success': False, 'message': 'OTP service is currently unavailable, please try again later.'})
    
    # Generate and send OTP
    otp = otp_generator()
    otp_status = send_otp_email(email, otp)
    if not otp_status:
        # If sending OTP fails, roll back user creation.
        db.session.delete(user)
        db.session.commit()
        return jsonify({'success': False, 'message': 'Failed to send OTP to the provided email, please check your email address.'})
    
    # Store OTP and email in session for validation
    session['auth_otp'] = otp
    session['auth_email'] = email
    return jsonify({'success': True, 'message': 'OTP sent to your email for verification.'})

@world_bp.route('/login', methods=['GET'])
def c_login():
    """
    Renders the user login form.
    """
    return render_template('login.html')

@world_bp.route('/login/send_otp', methods=['POST'])
def send_otp():
    """
    Sends an OTP to the provided email for user login.
    Checks if a user with the email exists before sending.
    """
    payload = request.get_json(silent=True) or {}
    
    email = payload.get('email', '')
    if not email:
        return jsonify({'success': False, 'message': 'Email address is required.'})
    
    _User = globals().get('User')
    if not _User:
        return jsonify({'success': False, 'message': 'User model not available, cannot send OTP.'})

    # Check if a user with this email exists
    user_exists = _User.query.filter_by(email=email).first()
    if not user_exists:
        return jsonify({'success': False, 'message': 'No account found with this email. Please sign up first.'})

    # Check if OTP service is available
    if otp_generator is None or send_otp_email is None:
        return jsonify({'success': False, 'message': 'OTP service is currently unavailable.'})
    
    # Generate and send OTP
    otp = otp_generator()
    otp_status = send_otp_email(email, otp)
    if not otp_status:
        return jsonify({'success': False, 'message': 'Failed to send OTP to the provided email.'})
    
    # Store OTP and email in session for validation
    session['auth_otp'] = otp
    session['auth_email'] = email
    return jsonify({'success': True, 'message': 'OTP sent to your email for login.'})

@world_bp.route('/login/validate', methods=['POST'])
def login_validate():
    """
    Validates the provided OTP against the one stored in the session.
    If valid, logs the user in.
    """
    payload = request.get_json(silent=True) or {}
    
    email = payload.get('email', '')
    otp = payload.get('otp', '')
    sent_otp = session.get('auth_otp', '')
    sent_email = session.get('auth_email', '')
    
    # Use the custom OTP validation utility if available, otherwise fallback to simple comparison
    if validate_otp is not None:
        result = validate_otp(otp, sent_otp, email, sent_email)
    else:
        is_valid = bool(otp and email and otp == sent_otp and email == sent_email)
        result = {'success': is_valid, 'message': 'OTP validated successfully.' if is_valid else 'Invalid OTP or email provided.'}
    
    if not result.get('success'):
        return jsonify(result)
    
    _User = globals().get('User')
    if not _User:
        return jsonify({'success': False, 'message': 'User model not available, cannot complete login.'})

    # Retrieve the user from the database
    user = _User.query.filter_by(email=email).first()
    if not user:
        # This case should ideally be caught earlier in send_otp, but included for robustness.
        return jsonify({'success': False, 'message': 'No user found with this email. Please sign up first.'})
    
    # Log in the user using Flask-Login
    login_user(user)
    
    # Clear OTP related session data after successful login
    session.pop('auth_otp', None)
    session.pop('auth_email', None)
    
    return jsonify({'success': True, 'message': 'Login succeeded.'})

@world_bp.route('/logout', methods=['GET'])
@login_required
def c_logout():
    """
    Logs out the current user and redirects them to the login page.
    Requires user to be logged in.
    """
    logout_user()
    flash('You have been logged out successfully.', 'info')
    # Redirect to the login page, specifying the blueprint name
    return redirect(url_for('world.c_login'))

# Converted Django-style regex route to Flask's path converter
@world_bp.route('/country/<path:country_name>', methods=['GET'])
@login_required
def get_country_details(country_name):
    """
    Retrieves and displays details for a specific country based on its name.
    Requires user to be logged in.
    """
    _Country = globals().get('Country')
    if not _Country:
        flash('Country model not available to fetch details.', 'danger')
        return redirect(url_for('world.home')) # Redirect to home or an error page
    
    # Query the Country model for the country by name, raising 404 if not found
    country = _Country.query.filter_by(name=country_name).first_or_404()
    
    return render_template('country.html', country=country)