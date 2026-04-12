from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user, login_user, logout_user
try:
    from .models import *
except ImportError:
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
    db = SQLAlchemy()

app_bp = Blueprint('app', __name__)

@app_bp.route('/', methods=['GET'])
def home():
    # Get all Item objects
    item_list = Item.query.all()
    
    return render_template('home.html', item_list=item_list)
