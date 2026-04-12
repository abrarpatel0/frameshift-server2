from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user, login_user, logout_user
try:
    from .models import City, Country, User, Countrylanguage, Language # Ensure all needed models are imported
except ImportError:
    # If models are not in .models, they might be in a global context or another module.
    # For now, we assume they will be resolvable at runtime or the app needs a proper model setup.
    City = None
    Country = None
    User = None
    Countrylanguage = None
    Language = None
    # TODO: Ensure models (City, Country, User, Countrylanguage, Language) are properly imported or defined.

try:
    from .util import otp_generator, send_otp_email, validate_otp
except ImportError:
    otp_generator = None
    send_otp_email = None
    validate_otp = None
    # TODO: Ensure otp utility functions (otp_generator, send_otp_email, validate_otp) are available.

try:
    from haystack.query import SearchQuerySet
except ImportError:
    SearchQuerySet = None
    # TODO: Ensure Flask-Haystack (or similar) is configured if search functionality is critical.

try:
    from extensions import db
except ImportError:
    from flask_sqlalchemy import SQLAlchemy
    db = SQLAlchemy()
    # TODO: Ensure db is correctly initialized with the Flask app (e.g., db.init_app(app)) if not imported from extensions.

world_bp = Blueprint('world', __name__)

@world_bp.route('/', methods=['GET'])
@login_required
def home():
    """
    Renders the home page. Requires user to be logged in.
    """
    return render_template('home.html')

@world_bp.route('/search', methods=['GET'])
@login_required
def search():
    """
    Handles global search queries for cities, countries, and languages.
    Uses Haystack if configured, otherwise returns an empty result with a warning.
    """
    query = request.args.get('query', '').strip()
    result = {'cities': [], 'countries': [], 'languages': []}
    
    if not query or len(query) < 3:
        return jsonify(result)
    
    if SearchQuerySet is None:
        flash('Search backend is not configured for this Flask project yet.', 'warning')
        # Fallback to render a template even if search backend is missing
        return render_template('search_results.html', **result)
    
    # Haystack integration
    city_pks = list(SearchQuerySet().autocomplete(i_city_name=query).values_list('pk', flat=True))
    country_pks = list(SearchQuerySet().autocomplete(i_country_name=query).values_list('pk', flat=True))
    language_pks = list(SearchQuerySet().autocomplete(i_language_name=query).values_list('pk', flat=True))
    
    # Retrieve actual model instances using SQLAlchemy
    if City:
        result['cities'] = [City.query.filter_by(pk=city_pk).first() for city_pk in city_pks if city_pk]
    else:
        flash('City model not available for search.', 'error')
        
    if Country:
        result['countries'] = [Country.query.filter_by(pk=country_pk).first() for country_pk in country_pks if country_pk]
    else:
        flash('Country model not available for search.', 'error')

    # Handle conditional language model (Countrylanguage or Language)
    language_model = globals().get('Countrylanguage') or globals().get('Language')
    if language_model is not None:
        result['languages'] = [language_model.query.filter_by(pk=language_pk).first() for language_pk in language_pks if language_pk]
    else:
        flash('Language model (Countrylanguage or Language) not available for search.', 'error')
    
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
    Handles user registration. Creates a new user and sends an OTP via email.
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
    
    if User is None:
        return jsonify({'success': False, 'message': 'User model not available, cannot sign up.'})

    try:
        user = User(email=email, first_name=first_name, last_name=last_name, phone_number=phone_number, gender=gender)
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        # This could be a unique constraint error (e.g., email already exists) or other DB error.
        # A more specific error message might be desirable in a production app.
        return jsonify({'success': False, 'message': f'user registration failed: {str(e)}'})
    
    if otp_generator is None or send_otp_email is None:
        return jsonify({'success': False, 'message': 'OTP service unavailable'})
    
    otp = otp_generator()
    otp_status = send_otp_email(email, otp)
    if not otp_status:
        # User created, but OTP email failed. This needs a robust retry/notification mechanism.
        return jsonify({'success': False, 'message': 'incorrect email or failed to send OTP'})
    
    session['auth_otp'] = otp
    session['auth_email'] = email
    return jsonify({'success': True, 'message': 'otp sent to email'})

@world_bp.route('/login', methods=['GET'])
def c_login():
    """
    Renders the user login page.
    """
    return render_template('login.html')

@world_bp.route('/login/send_otp', methods=['POST'])
def send_otp():
    """
    Sends a one-time password (OTP) to the provided email for login.
    """
    payload = request.get_json(silent=True) or {}
    
    email = payload.get('email', '')
    if not email:
        return jsonify({'success': False, 'message': 'email not found'})
    
    if otp_generator is None or send_otp_email is None:
        return jsonify({'success': False, 'message': 'OTP service unavailable'})
    
    otp = otp_generator()
    otp_status = send_otp_email(email, otp)
    if not otp_status:
        return jsonify({'success': False, 'message': 'incorrect email or failed to send OTP'})
    
    session['auth_otp'] = otp
    session['auth_email'] = email
    return jsonify({'success': True, 'message': 'otp sent'})

@world_bp.route('/login/validate', methods=['POST'])
def login_validate():
    """
    Validates the provided OTP and logs in the user if successful.
    """
    payload = request.get_json(silent=True) or {}
    
    email = payload.get('email', '')
    otp = payload.get('otp', '')
    sent_otp = session.get('auth_otp', '')
    sent_email = session.get('auth_email', '')
    
    if validate_otp is not None:
        result = validate_otp(otp, sent_otp, email, sent_email)
    else:
        # Fallback manual validation if validate_otp utility is not available
        is_valid = bool(otp and email and otp == sent_otp and email == sent_email)
        result = {'success': is_valid, 'message': 'validated' if is_valid else 'invalid otp'}
    
    if not result.get('success'):
        return jsonify(result)
    
    if User is None:
        return jsonify({'success': False, 'message': 'User model not available, cannot log in.'})

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'success': False, 'message': 'please signup'})
    
    login_user(user)
    # Clear OTP related session variables after successful login
    session.pop('auth_otp', None)
    session.pop('auth_email', None)
    return jsonify({'success': True, 'message': 'login succeeded'})

@world_bp.route('/logout', methods=['GET'])
@login_required
def c_logout():
    """
    Logs out the current user and redirects to the login page.
    """
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('world.c_login')) # Use blueprint prefix for url_for

@world_bp.route('/country/<path:country_name>', methods=['GET'])
@login_required
def get_country_details(country_name):
    """
    Displays details for a specific country based on its name.
    Uses Flask's path converter for country_name which can include slashes.
    """
    if Country is None:
        flash('Country model not available.', 'error')
        return render_template('404.html'), 404 # Or some other appropriate error template

    # Get specific Country or return 404 if not found
    country = Country.query.filter_by(name=country_name).first_or_404()
    
    return render_template('country.html', country=country)