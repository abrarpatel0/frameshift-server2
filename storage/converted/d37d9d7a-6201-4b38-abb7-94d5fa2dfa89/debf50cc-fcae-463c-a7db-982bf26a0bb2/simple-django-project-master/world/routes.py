from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user, login_user, logout_user
try:
    from .models import *
except ImportError:
    # Requirement #10: Do NOT invent placeholder model classes, mock query classes, fake fallback objects, or sample data.
    # Keep the try/except ImportError for models as-is.
    pass

try:
    from .util import otp_generator, send_otp_email, validate_otp
except ImportError:
    otp_generator = None
    send_otp_email = None
    validate_otp = None

try:
    from haystack.query import SearchQuerySet
except ImportError:
    SearchQuerySet = None

try:
    from extensions import db
except ImportError:
    from flask_sqlalchemy import SQLAlchemy
    # This is a fallback definition for db if extensions.db isn't found.
    # It assumes db will be properly initialized elsewhere in the application.
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
    Handles the search functionality. Queries cities, countries, and languages
    using Haystack's SearchQuerySet if available.
    Returns JSON for short/empty queries, otherwise renders search results HTML.
    """
    query = request.args.get('query', '').strip()
    result = {'cities': [], 'countries': [], 'languages': []}

    if not query or len(query) < 3:
        # Assuming this is an AJAX endpoint for instant search, return JSON
        return jsonify(result)

    if SearchQuerySet is None:
        flash('Search backend is not configured for this Flask project yet.', 'warning')
        # If no search backend, render the template with empty results
        return render_template('search_results.html', **result)

    city_pks = []
    country_pks = []
    language_pks = []
    try:
        # Haystack SearchQuerySet methods are assumed to exist and function.
        # Catching potential runtime errors from the search backend.
        city_pks = list(SearchQuerySet().autocomplete(i_city_name=query).values_list('pk', flat=True))
        country_pks = list(SearchQuerySet().autocomplete(i_country_name=query).values_list('pk', flat=True))
        language_pks = list(SearchQuerySet().autocomplete(i_language_name=query).values_list('pk', flat=True))
    except Exception as e:
        flash(f'Error querying search backend: {e}', 'danger')
        return render_template('search_results.html', **result)

    # Fetch full model objects based on PKs from search
    CityModel = globals().get('City')
    if CityModel:
        result['cities'] = [CityModel.query.filter_by(pk=city_pk).first() for city_pk in city_pks]

    CountryModel = globals().get('Country')
    if CountryModel:
        result['countries'] = [CountryModel.query.filter_by(pk=country_pk).first() for country_pk in country_pks]

    # The original code provided a fallback for language_model
    LanguageModel = globals().get('Countrylanguage') or globals().get('Language')
    if LanguageModel:
        result['languages'] = [LanguageModel.query.filter_by(pk=language_pk).first() for language_pk in language_pks]

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
    Handles user signup validation and OTP sending.
    Expects a JSON payload with 'email', 'first_name', 'last_name', 'gender', 'phone_number'.
    Creates a new user and sends an OTP for verification.
    """
    payload = request.get_json(silent=True) or {}

    email = payload.get('email', '')
    first_name = payload.get('first_name', '')
    last_name = payload.get('last_name', '')
    gender = payload.get('gender', 'female')
    phone_number = payload.get('phone_number', '')

    if not email:
        return jsonify({'success': False, 'message': 'email not found'}), 400
    if not first_name:
        return jsonify({'success': False, 'message': 'first name not found'}), 400

    UserModel = globals().get('User')
    if not UserModel:
        # Return an error if the User model is not available (e.g., due to ImportError)
        return jsonify({'success': False, 'message': 'User model not available, cannot signup'}), 500

    try:
        # Check if user already exists
        if UserModel.query.filter_by(email=email).first():
            return jsonify({'success': False, 'message': 'user with this email already exists'}), 409 # Conflict

        user = UserModel(email=email, first_name=first_name, last_name=last_name, phone_number=phone_number, gender=gender)
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        # Log the actual exception for debugging in a real application
        return jsonify({'success': False, 'message': f'Error creating user: {str(e)}'}), 500

    if otp_generator is None or send_otp_email is None:
        # OTP service unavailable. User might be created but not verified.
        return jsonify({'success': False, 'message': 'OTP service unavailable'}), 503

    try:
        otp = otp_generator()
        otp_status = send_otp_email(email, otp)
        if not otp_status:
            return jsonify({'success': False, 'message': 'Incorrect email for OTP service or failed to send OTP'}), 400
    except Exception as e:
        # Catch errors during OTP generation or sending
        return jsonify({'success': False, 'message': f'Error sending OTP: {str(e)}'}), 500

    session['auth_otp'] = otp
    session['auth_email'] = email
    return jsonify({'success': True, 'message': 'OTP sent to email'})

@world_bp.route('/login', methods=['GET'])
def c_login():
    """
    Renders the login page.
    """
    return render_template('login.html')

@world_bp.route('/login/send_otp', methods=['POST'])
def send_otp():
    """
    Sends an OTP to the provided email for login.
    Expects a JSON payload with 'email'.
    """
    payload = request.get_json(silent=True) or {}

    email = payload.get('email', '')
    if not email:
        return jsonify({'success': False, 'message': 'email not found'}), 400

    if otp_generator is None or send_otp_email is None:
        return jsonify({'success': False, 'message': 'OTP service unavailable'}), 503

    try:
        otp = otp_generator()
        otp_status = send_otp_email(email, otp)
        if not otp_status:
            return jsonify({'success': False, 'message': 'Incorrect email for OTP service or failed to send OTP'}), 400
    except Exception as e:
        # Catch errors during OTP generation or sending
        return jsonify({'success': False, 'message': f'Error sending OTP: {str(e)}'}), 500

    session['auth_otp'] = otp
    session['auth_email'] = email
    return jsonify({'success': True, 'message': 'OTP sent'})

@world_bp.route('/login/validate', methods=['POST'])
def login_validate():
    """
    Validates the provided OTP for login.
    Expects a JSON payload with 'email' and 'otp'.
    If validation succeeds, logs in the user.
    """
    payload = request.get_json(silent=True) or {}

    email = payload.get('email', '')
    otp = payload.get('otp', '')
    sent_otp = session.get('auth_otp')
    sent_email = session.get('auth_email')

    if not email or not otp:
        return jsonify({'success': False, 'message': 'Email and OTP are required'}), 400
    if not sent_otp or not sent_email:
        # OTP session data might be missing or expired
        return jsonify({'success': False, 'message': 'OTP session data missing. Please request a new OTP.'}), 400

    result = {'success': False, 'message': 'Invalid OTP'}
    if validate_otp is not None:
        try:
            result = validate_otp(otp, sent_otp, email, sent_email)
        except Exception as e:
            result['message'] = f'Error during OTP validation: {str(e)}'
    else:
        # Fallback validation if OTP utility is not available
        if otp == sent_otp and email == sent_email:
            result = {'success': True, 'message': 'Validated'}
        else:
            result = {'success': False, 'message': 'Invalid OTP or email mismatch'}

    # Clear OTP session data immediately after validation attempt
    session.pop('auth_otp', None)
    session.pop('auth_email', None)

    if not result.get('success'):
        return jsonify(result), 401 # Unauthorized

    UserModel = globals().get('User')
    if not UserModel:
        # Return an error if the User model is not available
        return jsonify({'success': False, 'message': 'User model not available, cannot login'}), 500

    user = UserModel.query.filter_by(email=email).first()
    if not user:
        return jsonify({'success': False, 'message': 'User not found. Please signup.'}), 404 # Not Found

    login_user(user)
    flash('Login successful!', 'success')
    return jsonify({'success': True, 'message': 'Login succeeded'})

@world_bp.route('/logout', methods=['GET'])
@login_required
def c_logout():
    """
    Logs out the current user and redirects to the login page.
    """
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('world.c_login')) # Use blueprint name for url_for

@world_bp.route('/country/<string:country_name>', methods=['GET']) # Changed Django regex path to Flask converter
@login_required
def get_country_details(country_name):
    """
    Displays details for a specific country.
    Requires the user to be logged in.
    """
    CountryModel = globals().get('Country')
    if not CountryModel:
        flash('Country model not available.', 'error')
        return redirect(url_for('world.home')) # Redirect to home if model is missing

    country = CountryModel.query.filter_by(name=country_name).first()
    if not country:
        flash(f'Country "{country_name}" not found.', 'danger')
        return redirect(url_for('world.home')) # Redirect to home with message if country not found

    return render_template('country.html', country=country)