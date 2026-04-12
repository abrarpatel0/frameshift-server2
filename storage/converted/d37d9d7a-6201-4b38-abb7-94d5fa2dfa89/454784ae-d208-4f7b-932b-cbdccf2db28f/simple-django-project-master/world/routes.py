from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user, login_user, logout_user

# Attempt to import models explicitly. If not found, NameErrors will occur
# where models are used. As per instructions, do not invent placeholder models.
try:
    from .models import City, Country, User, Countrylanguage, Language
except ImportError:
    # If models cannot be imported, dependent routes will fail with NameError.
    # No further action here as per instructions not to fabricate models.
    pass

# Attempt to import OTP utilities. Fallbacks are provided for 'None'.
try:
    from .util import otp_generator, send_otp_email, validate_otp
except ImportError:
    otp_generator = None
    send_otp_email = None
    validate_otp = None

# Attempt to import Haystack. Fallback is provided for 'None'.
try:
    from haystack.query import SearchQuerySet
except ImportError:
    SearchQuerySet = None

# Attempt to import db from extensions. Fallback to SQLAlchemy definition.
# This assumes that if 'extensions' is unavailable, Flask-SQLAlchemy will be
# initialized elsewhere with `db.init_app(app)`.
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
    Renders the home page. Requires the user to be logged in.
    """
    return render_template('home.html')

@world_bp.route('/search', methods=['GET'])
@login_required
def search():
    """
    Handles search queries for cities, countries, and languages using Haystack.
    Renders search_results.html with the findings or appropriate messages.
    """
    query = request.args.get('query', '').strip()
    result = {'cities': [], 'countries': [], 'languages': [], 'query': query}

    if not query or len(query) < 3:
        if not query:
            flash('Please enter a search query.', 'info')
        elif len(query) < 3:
            flash('Search query must be at least 3 characters long.', 'info')
        return render_template('search_results.html', **result)

    if SearchQuerySet is None:
        flash('Search backend is not configured for this Flask project yet. Cannot perform search.', 'warning')
        return render_template('search_results.html', **result)

    try:
        city_pks = list(SearchQuerySet().autocomplete(i_city_name=query).values_list('pk', flat=True))
        country_pks = list(SearchQuerySet().autocomplete(i_country_name=query).values_list('pk', flat=True))
        language_pks = list(SearchQuerySet().autocomplete(i_language_name=query).values_list('pk', flat=True))

        # Query models using SQLAlchemy. Check if model classes are defined to prevent NameError.
        if 'City' in globals():
            result['cities'] = [City.query.filter_by(pk=city_pk).first() for city_pk in city_pks]
        if 'Country' in globals():
            result['countries'] = [Country.query.filter_by(pk=country_pk).first() for country_pk in country_pks]
        
        # Use the existing fallback logic for language model.
        language_model = globals().get('Countrylanguage') or globals().get('Language')
        if language_model:
            result['languages'] = [language_model.query.filter_by(pk=language_pk).first() for language_pk in language_pks]
        else:
            flash('Language model (Countrylanguage or Language) not found. Language search results might be incomplete.', 'warning')

    except Exception as e:
        flash(f'An error occurred during search: {e}', 'danger')
        # In a production app, you would log this exception: current_app.logger.error(f"Search error: {e}")
        return render_template('search_results.html', **result)

    return render_template('search_results.html', **result)

@world_bp.route('/signup', methods=['GET'])
def signup():
    """
    Renders the user signup page.
    """
    return render_template('signup.html')

@world_bp.route('/signup/validate', methods=['POST'])
def signup_validate():
    """
    Validates signup details and sends an OTP to the user's email for verification.
    If valid, creates a new user in the database. Returns JSON response.
    """
    payload = request.get_json(silent=True) or {}

    email = payload.get('email', '')
    first_name = payload.get('first_name', '')
    last_name = payload.get('last_name', '')
    gender = payload.get('gender', 'female') # Default to 'female' as per original
    phone_number = payload.get('phone_number', '')

    if not email:
        return jsonify({'success': False, 'message': 'Email not provided.'})
    if not first_name:
        return jsonify({'success': False, 'message': 'First name not provided.'})

    if 'User' not in globals():
        return jsonify({'success': False, 'message': 'User model is not defined. Cannot sign up.'})

    # Check if user already exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({'success': False, 'message': 'User with this email already exists.'})

    try:
        user = User(email=email, first_name=first_name, last_name=last_name, phone_number=phone_number, gender=gender)
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        # Log the error for debugging: current_app.logger.error(f"Error creating user: {e}")
        return jsonify({'success': False, 'message': f'Failed to create user due to a database error: {str(e)}'})

    if otp_generator is None or send_otp_email is None:
        return jsonify({'success': False, 'message': 'OTP service is unavailable. User created, but email verification cannot be sent.'})

    try:
        otp = otp_generator()
        otp_status = send_otp_email(email, otp)
        if not otp_status:
            return jsonify({'success': False, 'message': 'Failed to send OTP to email. Please check your email address.'})
    except Exception as e:
        # Log the error for debugging: current_app.logger.error(f"Error sending OTP for signup: {e}")
        return jsonify({'success': False, 'message': 'An error occurred while sending OTP.'})

    session['auth_otp'] = otp
    session['auth_email'] = email
    return jsonify({'success': True, 'message': 'OTP sent to your email for verification.'})


@world_bp.route('/login', methods=['GET'])
def c_login():
    """
    Renders the user login page.
    """
    return render_template('login.html')

@world_bp.route('/login/send_otp', methods=['POST'])
def send_otp():
    """
    Sends an OTP to the provided email for login verification. Returns JSON response.
    """
    payload = request.get_json(silent=True) or {}

    email = payload.get('email', '')
    if not email:
        return jsonify({'success': False, 'message': 'Email not provided.'})

    if 'User' not in globals():
        return jsonify({'success': False, 'message': 'User model is not defined. Cannot log in.'})

    # Check if user exists before sending OTP for login
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'success': False, 'message': 'No account found with this email. Please sign up.'})

    if otp_generator is None or send_otp_email is None:
        return jsonify({'success': False, 'message': 'OTP service is unavailable.'})

    try:
        otp = otp_generator()
        otp_status = send_otp_email(email, otp)
        if not otp_status:
            return jsonify({'success': False, 'message': 'Failed to send OTP to email. Please check your email address.'})
    except Exception as e:
        # Log the error for debugging: current_app.logger.error(f"Error sending OTP for login: {e}")
        return jsonify({'success': False, 'message': 'An error occurred while sending OTP.'})

    session['auth_otp'] = otp
    session['auth_email'] = email
    return jsonify({'success': True, 'message': 'OTP sent to your email.'})

@world_bp.route('/login/validate', methods=['POST'])
def login_validate():
    """
    Validates the provided OTP for user login. If successful, logs the user in.
    Returns JSON response.
    """
    payload = request.get_json(silent=True) or {}

    email = payload.get('email', '')
    otp = payload.get('otp', '')
    
    # Pop from session to ensure OTP is single-use and for security
    sent_otp = session.pop('auth_otp', None) 
    sent_email = session.pop('auth_email', None)

    if not email or not otp:
        return jsonify({'success': False, 'message': 'Email and OTP are required.'})

    result = {'success': False, 'message': 'Invalid OTP or email. Please try again.'}

    if validate_otp is not None:
        result = validate_otp(otp, sent_otp, email, sent_email)
    else:
        # Fallback if validate_otp utility is not available
        if otp and email and otp == sent_otp and email == sent_email:
            result = {'success': True, 'message': 'OTP validated successfully.'}
        else:
            result = {'success': False, 'message': 'OTP validation service unavailable or invalid OTP/email.'}

    if not result.get('success'):
        return jsonify(result)

    if 'User' not in globals():
        return jsonify({'success': False, 'message': 'User model is not defined. Cannot complete login.'})

    user = User.query.filter_by(email=email).first()
    if not user:
        # This case should ideally not happen if 'send_otp' validated user existence.
        return jsonify({'success': False, 'message': 'No user found with this email. Please sign up.'})

    login_user(user)
    return jsonify({'success': True, 'message': 'Login succeeded.'})

@world_bp.route('/logout', methods=['GET'])
@login_required
def c_logout():
    """
    Logs out the current user and redirects to the login page.
    Requires the user to be logged in.
    """
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('world.c_login')) # Use blueprint prefix for url_for

@world_bp.route('/country/<string:country_name>', methods=['GET'])
@login_required
def get_country_details(country_name):
    """
    Displays details for a specific country based on its name.
    Requires the user to be logged in.
    """
    if 'Country' not in globals():
        flash('Country model is not defined. Cannot retrieve country details.', 'danger')
        return render_template('country.html', country=None)

    # Use first_or_404() which is typically added by Flask-SQLAlchemy.
    # If not using Flask-SQLAlchemy, this would need manual error handling:
    # country = Country.query.filter_by(name=country_name).first()
    # if country is None: abort(404)
    country = Country.query.filter_by(name=country_name).first_or_404()

    return render_template('country.html', country=country)