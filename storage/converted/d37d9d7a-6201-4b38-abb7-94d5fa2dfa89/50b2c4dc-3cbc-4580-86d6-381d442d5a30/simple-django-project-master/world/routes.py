from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user, login_user, logout_user
import logging

# Configure basic logging for better error visibility
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    from .models import User, City, Country, Countrylanguage, Language # Ensure all models are imported
except ImportError:
    # If models cannot be imported, they will be handled by explicit checks in functions
    # For example, City.query will raise an error if City is not defined.
    # We will assume models are correctly set up in a real application.
    logging.warning("Models could not be imported. Ensure 'models.py' exists and is correctly configured.")
    User, City, Country, Countrylanguage, Language = None, None, None, None, None # Define as None to avoid NameError

try:
    from .util import otp_generator, send_otp_email, validate_otp
except ImportError:
    logging.warning("OTP utility functions (otp_generator, send_otp_email, validate_otp) not found. OTP features will be unavailable.")
    otp_generator = None
    send_otp_email = None
    validate_otp = None

try:
    from haystack.query import SearchQuerySet
except ImportError:
    logging.warning("Haystack SearchQuerySet not found. Search functionality will be limited or unavailable.")
    SearchQuerySet = None

try:
    from extensions import db
except ImportError:
    # Fallback for db if not in extensions; assumes it will be initialized later or in global scope.
    # In a real Flask app, `db` should be initialized with an app context.
    from flask_sqlalchemy import SQLAlchemy
    db = SQLAlchemy()
    logging.warning("Flask-SQLAlchemy `db` instance not found in 'extensions'. Using a default SQLAlchemy instance. Ensure it's properly initialized with your Flask app.")

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
    Handles global search queries for cities, countries, and languages.
    Requires the Haystack search backend to be configured.
    """
    query = request.args.get('query', '').strip()
    result = {'cities': [], 'countries': [], 'languages': []}
    
    if not query or len(query) < 3:
        # For an empty or too short query, return empty results
        # If it's an AJAX request, return JSON; otherwise, render template with empty results
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return jsonify(result)
        return render_template('search_results.html', **result)
    
    if SearchQuerySet is None:
        flash('Search backend is not configured for this Flask project yet.', 'warning')
        return render_template('search_results.html', **result)
    
    try:
        city_pks = list(SearchQuerySet().autocomplete(i_city_name=query).values_list('pk', flat=True))
        country_pks = list(SearchQuerySet().autocomplete(i_country_name=query).values_list('pk', flat=True))
        language_pks = list(SearchQuerySet().autocomplete(i_language_name=query).values_list('pk', flat=True))
        
        # Check if models are available before querying
        if City:
            result['cities'] = City.query.filter(City.id.in_(city_pks)).all() if city_pks else []
        if Country:
            result['countries'] = Country.query.filter(Country.id.in_(country_pks)).all() if country_pks else []
        
        # Use Countrylanguage or Language based on availability
        language_model = globals().get('Countrylanguage') or globals().get('Language')
        if language_model:
            result['languages'] = language_model.query.filter(language_model.id.in_(language_pks)).all() if language_pks else []
        
    except Exception as e:
        logging.error(f"Error during search query: {e}")
        flash('An error occurred during search. Please try again later.', 'danger')
        # Return empty results or specific error for API calls
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            return jsonify({'error': 'Search failed', 'message': str(e)}), 500
        return render_template('search_results.html', **result)
    
    if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
        # Convert model objects to a serializable format if returning JSON
        json_result = {
            'cities': [c.to_dict() if hasattr(c, 'to_dict') else {'id': c.id, 'name': c.name} for c in result['cities']],
            'countries': [c.to_dict() if hasattr(c, 'to_dict') else {'id': c.id, 'name': c.name} for c in result['countries']],
            'languages': [l.to_dict() if hasattr(l, 'to_dict') else {'id': l.id, 'name': l.name} for l in result['languages']],
        }
        return jsonify(json_result)

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
    Handles the signup validation process, creates a new user, and sends an OTP.
    Expects JSON payload with user details.
    """
    payload = request.get_json(silent=True) or {}
    
    email = payload.get('email', '')
    if not email:
        return jsonify({'success': False, 'message': 'Email not found'}), 400
    
    first_name = payload.get('first_name', '')
    last_name = payload.get('last_name', '')
    gender = payload.get('gender', 'female') # Default to 'female' if not provided
    phone_number = payload.get('phone_number', '')
    
    if not first_name:
        return jsonify({'success': False, 'message': 'First name not found'}), 400
    
    if User is None:
        return jsonify({'success': False, 'message': 'User model not available, cannot signup.'}), 500

    try:
        # Check if user already exists
        if User.query.filter_by(email=email).first():
            return jsonify({'success': False, 'message': 'User with this email already exists'}), 409

        user = User(email=email, first_name=first_name, last_name=last_name, phone_number=phone_number, gender=gender)
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error during user signup: {e}")
        return jsonify({'success': False, 'message': 'Failed to create user. Please try again or check server logs.'}), 500
    
    if otp_generator is None or send_otp_email is None:
        return jsonify({'success': False, 'message': 'OTP service unavailable. User registered, but cannot verify.'}), 503
    
    try:
        otp = otp_generator()
        otp_status = send_otp_email(email, otp)
        if not otp_status:
            return jsonify({'success': False, 'message': 'Incorrect email or failed to send OTP'}), 400
    except Exception as e:
        logging.error(f"Error sending OTP during signup: {e}")
        return jsonify({'success': False, 'message': 'Failed to send OTP due to an internal error.'}), 500
    
    session['auth_otp'] = otp
    session['auth_email'] = email
    # The original condition 'signup_validate' == 'signup_validate' always evaluates to true
    return jsonify({'success': True, 'message': 'OTP sent to email'}), 200

@world_bp.route('/login', methods=['GET'])
def c_login():
    """
    Renders the user login page.
    """
    return render_template('login.html')

@world_bp.route('/login/send_otp', methods=['POST'])
def send_otp():
    """
    Sends an OTP to the provided email for login.
    Expects JSON payload with email.
    """
    payload = request.get_json(silent=True) or {}
    
    email = payload.get('email', '')
    if not email:
        return jsonify({'success': False, 'message': 'Email not found'}), 400
    
    if User is None:
        return jsonify({'success': False, 'message': 'User model not available, cannot login.'}), 500

    # Check if the user exists before sending OTP
    user_exists = User.query.filter_by(email=email).first()
    if not user_exists:
        return jsonify({'success': False, 'message': 'No user found with this email. Please sign up.'}), 404

    if otp_generator is None or send_otp_email is None:
        return jsonify({'success': False, 'message': 'OTP service unavailable'}), 503
    
    try:
        otp = otp_generator()
        otp_status = send_otp_email(email, otp)
        if not otp_status:
            return jsonify({'success': False, 'message': 'Incorrect email or failed to send OTP'}), 400
    except Exception as e:
        logging.error(f"Error sending OTP during login: {e}")
        return jsonify({'success': False, 'message': 'Failed to send OTP due to an internal error.'}), 500
    
    session['auth_otp'] = otp
    session['auth_email'] = email
    # The original condition 'send_otp' == 'signup_validate' always evaluates to false
    return jsonify({'success': True, 'message': 'OTP sent'}), 200

@world_bp.route('/login/validate', methods=['POST'])
def login_validate():
    """
    Validates the provided OTP for login and logs the user in.
    Expects JSON payload with email and OTP.
    """
    payload = request.get_json(silent=True) or {}
    
    email = payload.get('email', '')
    otp = payload.get('otp', '')
    sent_otp = session.pop('auth_otp', None) # Pop to ensure OTP can only be used once
    sent_email = session.pop('auth_email', None) # Pop to ensure OTP can only be used once
    
    if not all([email, otp, sent_otp, sent_email]):
        return jsonify({'success': False, 'message': 'Missing email, OTP, or session data expired.'}), 400

    result = {'success': False, 'message': 'Invalid OTP or email.'}

    if validate_otp is not None:
        try:
            result = validate_otp(otp, sent_otp, email, sent_email)
        except Exception as e:
            logging.error(f"Error validating OTP: {e}")
            return jsonify({'success': False, 'message': 'An error occurred during OTP validation.'}), 500
    else:
        # Fallback validation if validate_otp utility is not available
        if otp == sent_otp and email == sent_email:
            result = {'success': True, 'message': 'OTP validated'}
        else:
            result = {'success': False, 'message': 'Invalid OTP or email.'}
    
    if not result.get('success'):
        return jsonify(result), 401
    
    if User is None:
        return jsonify({'success': False, 'message': 'User model not available, cannot login.'}), 500

    user = User.query.filter_by(email=email).first()
    if not user:
        # This case should ideally not happen if send_otp checked for user existence
        return jsonify({'success': False, 'message': 'Please signup first. User not found.'}), 404
    
    try:
        login_user(user)
    except Exception as e:
        logging.error(f"Error during user login: {e}")
        return jsonify({'success': False, 'message': 'Failed to log in user.'}), 500
        
    return jsonify({'success': True, 'message': 'Login succeeded'}), 200

@world_bp.route('/logout', methods=['GET'])
@login_required
def c_logout():
    """
    Logs out the current user and redirects to the login page.
    """
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('world.c_login')) # Use blueprint name for url_for

@world_bp.route('/country/<path:country_name>', methods=['GET'])
@login_required
def get_country_details(country_name):
    """
    Displays details for a specific country.
    Uses <path:country_name> to capture country names with special characters or slashes.
    """
    if Country is None:
        flash('Country model not available, cannot retrieve country details.', 'danger')
        return redirect(url_for('world.home')) # Redirect to home or error page

    try:
        # Get specific Country by name
        country = Country.query.filter_by(name=country_name).first_or_404(description=f'Country {country_name} not found.')
        return render_template('country.html', country=country)
    except Exception as e:
        logging.error(f"Error retrieving country details for {country_name}: {e}")
        flash('An error occurred while fetching country details.', 'danger')
        return redirect(url_for('world.home')) # Redirect to home or an appropriate error page