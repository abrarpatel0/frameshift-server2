from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db

app = Flask(__name__)

@app.route('/home', methods=['GET'])
@login_required
def home():
    return render_template('home.html')

@app.route('/search', methods=['GET'])
@login_required
def search():
    # Filter City objects
    city_list = City.query.filter_by().all()
    
    # Filter Country objects
    country_list = Country.query.filter_by().all()
    
    # Filter Countrylanguage objects
    countrylanguage_list = Countrylanguage.query.filter_by().all()
    
    return render_template('search_results.html', city_list=city_list, country_list=country_list, countrylanguage_list=countrylanguage_list)

@app.route('/signup', methods=['GET'])
def signup():
    return render_template('signup.html')

@app.route('/signup_validate', methods=['GET'])
def signup_validate():
    data = {
        'status': 'success',
        'message': 'Operation completed'
    }
    return jsonify(data)

@app.route('/c_login', methods=['GET'])
def c_login():
    return render_template('login.html')

@app.route('/send_otp', methods=['GET'])
def send_otp():
    data = {
        'status': 'success',
        'message': 'Operation completed'
    }
    return jsonify(data)

@app.route('/login_validate', methods=['GET'])
def login_validate():
    data = {
        'status': 'success',
        'message': 'Operation completed'
    }
    return jsonify(data)

@app.route('/c_logout', methods=['GET'])
@login_required
def c_logout():
    return 'Hello from c_logout'

@app.route('/get_country_details', methods=['GET'])
@login_required
def get_country_details():
    # Get specific Country
    country = Country.query.get_or_404(pk)
    
    return render_template('country.html', country=country)

