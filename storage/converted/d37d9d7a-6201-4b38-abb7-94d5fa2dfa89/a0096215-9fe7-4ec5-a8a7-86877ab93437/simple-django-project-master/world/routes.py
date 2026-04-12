from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user, login_user, logout_user
from sqlalchemy.exc import IntegrityError # Import for specific error handling

try:
    from .models import User, City, Country, Countrylanguage, Language # Ensure all models are explicitly imported
except ImportError:
    # If models are not in .models, assume they are available globally or raise an error later
    # For now, define placeholders to avoid NameError if import fails, but expect runtime errors if not truly available
    User = None
    City = None
    Country = None
    Countrylanguage = None
    Language = None

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
    db = SQLAlchemy()

world_bp = Blueprint('world', __name__)

@world_bp.route('/', methods=['GET'])
@login_required
def home():
    """
    Renders the home page.
    Requires user to be logged in.
    """
    return render_template('home.html')

@world_bp.route('/search', methods=['GET'])
@login_required
def search():
    """
    Handles search queries across cities, countries, and languages.
    Requires Flask-Haystack (SearchQuerySet) to be configured.
    """
    query = request.args.get('query', '').strip()
    result = {'cities': [], 'countries': [], 'languages': []}
    
    if not query or len(query) < 3:
        # Return empty results for short or empty queries
        return render_template('search_results.html', **result)
    
    if SearchQuerySet is None:
        flash('Search backend is not configured for this Flask project yet.', 'warning')
        return render_template('search_results.html', **result)
    
    # Perform search using Haystack SearchQuerySet
    city_pks = list(SearchQuerySet().autocomplete(i_city_name=query).values_list('pk', flat=True))
    country_pks = list(SearchQuerySet().autocomplete(i_country_name=query).values_list('pk', flat=True))
    language_pks = list(SearchQuerySet().autocomplete(i_language_name=query).values_list('pk', flat=True))
    
    # Fetch actual model instances using SQLAlchemy ORM
    if City:
        result['cities'] = [City.query.filter_by(pk=city_pk).first() for city_pk in city_pks if city_pk]
    if Country:
        result['countries'] = [Country.query.filter_by(pk=country_pk).first() for country_pk in country_pks if country_pk]

    # Dynamically select Language model based on what's available
    language_model = globals().get('Countrylanguage') or globals().get('Language')
    if language_model is not None:
        result['languages'] = [language_model.query.filter_by(pk=language_pk).first() for language_pk in language_pks if language_pk]
    
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
    Handles user registration.
    Expects a JSON payload with user details and sends an OTP via email.
    """
    if User is None:
        return jsonify({'success': False, 'message': 'User model not available, signup not possible.'})

    payload = request.get_json(silent=True) or {}
    
    email = payload.get('email', '').strip()
    first_name = payload.get('first_name', '').strip()
    last_name = payload.get('last_name', '').strip()
    gender = payload.get('gender', 'female').strip()
    phone_number = payload.get('phone_number', '').strip()
    
    if not email:
        return jsonify({'success': False, 'message': 'email not provided'})
    if not first_name:
        return jsonify({'success': False, 'message': 'first name not provided'})
    
    # Check if user already exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({'success': False, 'message': 'user with this email already exists'})

    try:
        user = User(email=email, first_name=first_name, last_name=last_name, phone_number=phone_number, gender=gender)
        db.session.add(user)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'user with this email already exists (integrity error)'})
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'an unexpected error occurred during signup'})
    
    if otp_generator is None or send_otp_email is None:
        return jsonify({'success': False, 'message': 'OTP service unavailable'})
    
    otp = otp_generator()
    otp_status = send_otp_email(email, otp)
    
    if not otp_status:
        # Optionally, delete the user if OTP email failed, or mark as unverified
        db.session.rollback() # Rollback user creation as well if email sending is critical
        return jsonify({'success': False, 'message': 'failed to send OTP email, please check email address'})
    
    session['auth_otp'] = otp
    session['auth_email'] = email
    return jsonify({'success': True, 'message': 'OTP sent to email'})

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
    Expects a JSON payload with 'email'.
    """
    payload = request.get_json(silent=True) or {}
    
    email = payload.get('email', '').strip()
    if not email:
        return jsonify({'success': False, 'message': 'email not provided'})
    
    if otp_generator is None or send_otp_email is None:
        return jsonify({'success': False, 'message': 'OTP service unavailable'})
    
    # Check if a user with this email exists before sending OTP
    if User is None or not User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'message': 'no user found with this email, please signup'})

    otp = otp_generator()
    otp_status = send_otp_email(email, otp)
    
    if not otp_status:
        return jsonify({'success': False, 'message': 'failed to send OTP email, please check email address'})
    
    session['auth_otp'] = otp
    session['auth_email'] = email
    return jsonify({'success': True, 'message': 'OTP sent to email'})

@world_bp.route('/login/validate', methods=['POST'])
def login_validate():
    """
    Validates the OTP and logs in the user.
    Expects a JSON payload with 'email' and 'otp'.
    """
    payload = request.get_json(silent=True) or {}
    
    email = payload.get('email', '').strip()
    otp = payload.get('otp', '').strip()
    
    if not email or not otp:
        return jsonify({'success': False, 'message': 'email and OTP are required'})

    sent_otp = session.get('auth_otp', '')
    sent_email = session.get('auth_email', '')
    
    result = {'success': False, 'message': 'invalid OTP or email'}

    if validate_otp is not None:
        result = validate_otp(otp, sent_otp, email, sent_email)
    else:
        # Fallback validation if `validate_otp` utility is not available
        if otp and email and otp == sent_otp and email == sent_email:
            result = {'success': True, 'message': 'OTP validated'}
        else:
            result = {'success': False, 'message': 'invalid OTP or email provided'}
    
    if not result.get('success'):
        return jsonify(result)
    
    # Clear OTP from session after validation attempt
    session.pop('auth_otp', None)
    session.pop('auth_email', None)

    if User is None:
        return jsonify({'success': False, 'message': 'User model not available, login not possible.'})

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'success': False, 'message': 'no user found with this email, please signup'})
    
    login_user(user)
    return jsonify({'success': True, 'message': 'Login succeeded'})

@world_bp.route('/logout', methods=['GET'])
@login_required
def c_logout():
    """
    Logs out the current user and redirects to the login page.
    Requires user to be logged in.
    """
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('world.c_login')) # Use blueprint name 'world.c_login'

@world_bp.route('/country/<country_name>', methods=['GET'])
@login_required
def get_country_details(country_name):
    """
    Displays details for a specific country.
    Uses Flask path converter for country_name.
    Requires user to be logged in.
    """
    if Country is None:
        flash('Country model not available, cannot retrieve country details.', 'error')
        return redirect(url_for('world.home')) # Redirect home if critical model is missing

    country = Country.query.filter_by(name=country_name).first_or_404()
    
    return render_template('country.html', country=country)
