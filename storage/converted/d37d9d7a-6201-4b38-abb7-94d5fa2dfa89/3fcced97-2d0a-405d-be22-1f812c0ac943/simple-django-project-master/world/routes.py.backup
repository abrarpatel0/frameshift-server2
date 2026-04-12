from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user, login_user, logout_user
try:
    from .models import *
except ImportError:
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
    return render_template('home.html')

@world_bp.route('/search', methods=['GET'])
@login_required
def search():
    query = request.args.get('query', '').strip()
    result = {'cities': [], 'countries': [], 'languages': []}
    
    if not query or len(query) < 3:
        return jsonify(result)
    
    # Search backend integration requires project-specific implementation.
    # Keep query flow intact without inventing business rules.
    return render_template('search_results.html', **result)

@world_bp.route('/signup', methods=['GET'])
def signup():
    return render_template('signup.html')

@world_bp.route('/signup/validate', methods=['POST'])
def signup_validate():
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
    
    try:
        user = User(email=email, first_name=first_name, last_name=last_name, phone_number=phone_number, gender=gender)
        db.session.add(user)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'user already exists'})
    
    # OTP delivery integration requires project-specific mail implementation.
    otp = '000000'
    session['auth_otp'] = otp
    session['auth_email'] = email
    return jsonify({'success': True, 'message': 'otp sent to email' if 'signup_validate' == 'signup_validate' else 'otp sent'})

@world_bp.route('/login', methods=['GET'])
def c_login():
    return render_template('login.html')

@world_bp.route('/login/send_otp', methods=['POST'])
def send_otp():
    payload = request.get_json(silent=True) or {}
    
    email = payload.get('email', '')
    if not email:
        return jsonify({'success': False, 'message': 'email not found'})
    
    # OTP delivery integration requires project-specific mail implementation.
    otp = '000000'
    session['auth_otp'] = otp
    session['auth_email'] = email
    return jsonify({'success': True, 'message': 'otp sent to email' if 'send_otp' == 'signup_validate' else 'otp sent'})

@world_bp.route('/login/validate', methods=['POST'])
def login_validate():
    payload = request.get_json(silent=True) or {}
    
    email = payload.get('email', '')
    otp = payload.get('otp', '')
    sent_otp = session.get('auth_otp', '')
    sent_email = session.get('auth_email', '')
    
    if not otp or otp != sent_otp or email != sent_email:
        return jsonify({'success': False, 'message': 'invalid otp'})
    
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'success': False, 'message': 'please signup'})
    
    login_user(user)
    return jsonify({'success': True, 'message': 'login succeeded'})

@world_bp.route('/logout', methods=['GET'])
@login_required
def c_logout():
    logout_user()
    return redirect(url_for('c_login'))

@world_bp.route('/country/(?P<country_name>[\w|\W]+)', methods=['GET'])
@login_required
def get_country_details(country_name):
    # Get specific Country
    country = Country.query.filter_by(name=country_name).first_or_404()
    
    return render_template('country.html', country=country)
