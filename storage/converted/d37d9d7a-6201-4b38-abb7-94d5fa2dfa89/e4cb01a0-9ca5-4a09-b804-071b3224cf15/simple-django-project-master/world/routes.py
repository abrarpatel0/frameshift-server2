from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user, login_user, logout_user
try:
    from .models import User, City, Country, Language, Countrylanguage # Assuming these models exist in .models
except ImportError:
    # If models cannot be imported, most routes attempting database operations will fail at runtime.
    # This block is retained as per the provided code structure, implying models might be optional or dynamically loaded.
    # Checks using `if 'ModelName' in globals():` are added in routes to handle this gracefully.
    pass

try:
    from .util import otp_generator, send_otp_email, validate_otp
except ImportError:
    # OTP utilities are optional based on the project setup.
    # Routes check if these are None before using them.
    otp_generator = None
    send_otp_email = None
    validate_otp = None

try:
    from haystack.query import SearchQuerySet
except ImportError:
    # Search functionality is optional and checked in the search route.
    SearchQuerySet = None

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
    Renders the home page for logged-in users.
    """
    return render_template('home.html')

@world_bp.route('/search', methods=['GET'])
@login_required
def search():
    """
    Handles search queries for cities, countries, and languages using a Haystack-like interface.
    Requires user to be logged in. Returns results rendered in 'search_results.html' or JSON.
    """
    query = request.args.get('query', '').strip()
    result = {'cities': [], 'countries': [], 'languages': []}

    if not query or len(query) < 3:
        # Return empty results for short or empty queries
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return jsonify(result)
        else:
            flash('Please enter at least 3 characters to search.', 'info')
            return render_template('search_results.html', **result)

    if SearchQuerySet is None:
        flash('Search backend is not configured for this Flask project yet.', 'warning')
        return render_template('search_results.html', **result)

    try:
        # Perform searches using Haystack SearchQuerySet (assuming 'pk' is the primary key attribute)
        city_pks = list(SearchQuerySet().autocomplete(i_city_name=query).values_list('pk', flat=True))
        country_pks = list(SearchQuerySet().autocomplete(i_country_name=query).values_list('pk', flat=True))
        language_pks = list(SearchQuerySet().autocomplete(i_language_name=query).values_list('pk', flat=True))

        # Retrieve full model objects from the database using collected primary keys
        if 'City' in globals() and city_pks:
            result['cities'] = City.query.filter(City.pk.in_(city_pks)).all()
        else:
            if city_pks: flash('City model not found, cannot retrieve city search results.', 'error')

        if 'Country' in globals() and country_pks:
            result['countries'] = Country.query.filter(Country.pk.in_(country_pks)).all()
        else:
            if country_pks: flash('Country model not found, cannot retrieve country search results.', 'error')

        language_model = globals().get('Countrylanguage') or globals().get('Language')
        if language_model is not None and language_pks:
            result['languages'] = language_model.query.filter(language_model.pk.in_(language_pks)).all()
        else:
            if language_pks: flash('Language model (Countrylanguage or Language) not found, cannot retrieve language search results.', 'error')

    except Exception as e:
        # Catch any exceptions during the search or database retrieval
        flash(f'An error occurred during search: {e}', 'danger')
        print(f"Search error: {e}") # Log the error for debugging
        return render_template('search_results.html', **result)

    return render_template('search_results.html', **result)

@world_bp.route('/signup', methods=['GET'])
def signup():
    """
    Renders the signup page.
    """
    return render_template('signup.html')

@world_bp.route('/signup/validate', methods=['POST'])
def signup_validate():
    """
    Handles user registration. Creates a new user and sends an OTP for verification.
    Expects a JSON payload with 'email', 'first_name', 'last_name', 'gender', 'phone_number'.
    """
    payload = request.get_json(silent=True) or {}

    email = payload.get('email', '').strip()
    first_name = payload.get('first_name', '').strip()
    last_name = payload.get('last_name', '').strip()
    gender = payload.get('gender', 'female').strip() # Default to 'female' if not provided
    phone_number = payload.get('phone_number', '').strip()

    if not email:
        return jsonify({'success': False, 'message': 'email not provided'})
    if not first_name:
        return jsonify({'success': False, 'message': 'first name not provided'})

    if 'User' not in globals():
        return jsonify({'success': False, 'message': 'User model not available for signup.'})

    try:
        # Check if user already exists by email before attempting to add
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({'success': False, 'message': 'user with this email already exists'})

        user = User(email=email, first_name=first_name, last_name=last_name, phone_number=phone_number, gender=gender)
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Signup error: {e}") # Log the error for debugging
        return jsonify({'success': False, 'message': 'an error occurred during user creation'})

    if otp_generator is None or send_otp_email is None:
        # If OTP service is unavailable, decide whether to allow signup without verification
        # For now, it indicates an issue with verification.
        return jsonify({'success': False, 'message': 'OTP service unavailable'})

    try:
        otp = otp_generator()
        otp_status = send_otp_email(email, otp)
        if not otp_status:
            return jsonify({'success': False, 'message': 'failed to send OTP to email'})
    except Exception as e:
        print(f"Error sending OTP during signup: {e}")
        return jsonify({'success': False, 'message': 'error sending OTP'})

    session['auth_otp'] = otp
    session['auth_email'] = email
    return jsonify({'success': True, 'message': 'otp sent to email'})

@world_bp.route('/login', methods=['GET'])
def c_login():
    """
    Renders the login page.
    """
    return render_template('login.html')

@world_bp.route('/login/send_otp', methods=['POST'])
def send_otp():
    """
    Handles sending OTP for user login.
    Expects a JSON payload with 'email'.
    """
    payload = request.get_json(silent=True) or {}

    email = payload.get('email', '').strip()
    if not email:
        return jsonify({'success': False, 'message': 'email not provided'})

    if 'User' not in globals():
        return jsonify({'success': False, 'message': 'User model not available for login check.'})

    # Check if a user with this email exists before sending OTP
    user_exists = User.query.filter_by(email=email).first()
    if not user_exists:
        return jsonify({'success': False, 'message': 'no user found with this email, please signup'})

    if otp_generator is None or send_otp_email is None:
        return jsonify({'success': False, 'message': 'OTP service unavailable'})

    try:
        otp = otp_generator()
        otp_status = send_otp_email(email, otp)
        if not otp_status:
            return jsonify({'success': False, 'message': 'incorrect email or failed to send OTP'})
    except Exception as e:
        print(f"Error sending OTP during login: {e}")
        return jsonify({'success': False, 'message': 'error sending OTP'})

    session['auth_otp'] = otp
    session['auth_email'] = email
    return jsonify({'success': True, 'message': 'otp sent to email'})

@world_bp.route('/login/validate', methods=['POST'])
def login_validate():
    """
    Validates OTP for login and logs the user in if successful.
    Expects a JSON payload with 'email' and 'otp'.
    """
    payload = request.get_json(silent=True) or {}

    email = payload.get('email', '').strip()
    otp = payload.get('otp', '').strip()
    sent_otp = session.pop('auth_otp', None) # Pop to ensure OTP is used only once
    sent_email = session.pop('auth_email', None) # Pop to ensure email context is used only once

    if not email or not otp:
        return jsonify({'success': False, 'message': 'email or OTP not provided'})
    if not sent_otp or not sent_email:
        return jsonify({'success': False, 'message': 'OTP session expired or not initiated'})

    result = {'success': False, 'message': 'invalid OTP'}
    if validate_otp is not None:
        try:
            result = validate_otp(otp, sent_otp, email, sent_email)
        except Exception as e:
            print(f"Error during OTP validation: {e}")
            result['message'] = 'error during OTP validation'
    else:
        # Fallback validation if `validate_otp` utility is not available
        if otp == sent_otp and email == sent_email:
            result = {'success': True, 'message': 'OTP validated'}
        else:
            result = {'success': False, 'message': 'invalid OTP or email mismatch'}

    if not result.get('success'):
        return jsonify(result)

    if 'User' not in globals():
        return jsonify({'success': False, 'message': 'User model not available for login.'})

    user = User.query.filter_by(email=email).first()
    if not user:
        # This case should ideally be caught earlier in send_otp, but as a safeguard
        return jsonify({'success': False, 'message': 'user not found, please signup'})

    login_user(user)
    # Clear session values related to OTP authentication after successful login
    session.pop('auth_email', None)
    return jsonify({'success': True, 'message': 'login succeeded'})

@world_bp.route('/logout', methods=['GET'])
@login_required
def c_logout():
    """
    Logs out the current user and redirects to the login page.
    Requires user to be logged in.
    """
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('world.c_login'))

@world_bp.route('/country/<string:country_name>', methods=['GET'])
@login_required
def get_country_details(country_name):
    """
    Displays details for a specific country by its name.
    Requires user to be logged in.
    """
    if 'Country' not in globals():
        flash('Country model not available to fetch country details.', 'error')
        return redirect(url_for('world.home'))

    # Get specific Country or return 404 if not found
    country = Country.query.filter_by(name=country_name).first_or_404()

    return render_template('country.html', country=country)