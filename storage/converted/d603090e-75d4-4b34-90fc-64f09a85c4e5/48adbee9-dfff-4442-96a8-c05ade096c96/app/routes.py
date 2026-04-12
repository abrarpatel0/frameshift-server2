from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user, login_user, logout_user
import bcrypt # For password hashing

try:
    from .models import User, Item # Assuming these are the primary models needed
except ImportError:
    # If models cannot be imported, routes dependent on them will flash an error.
    # Per requirement 11, we avoid fabricating mock classes.
    User = None
    Item = None

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
    # Fallback if extensions.db is not found. Assumes db is an SQLAlchemy instance.
    from flask_sqlalchemy import SQLAlchemy
    # TODO: If extensions.db is not available, ensure this SQLAlchemy instance is
    # properly initialized with the Flask app context (e.g., db.init_app(app)).
    # As 'app' is not in scope here, this assumes it happens elsewhere.
    db = SQLAlchemy()

app_bp = Blueprint('app', __name__)

@app_bp.route('/', methods=['GET'])
def home():
    """
    Displays the home page with a list of all items.
    """
    item_list = []
    if Item:
        item_list = Item.query.all()
    else:
        flash("Item model not available. Cannot display items.", "error")
    
    return render_template('home.html', item_list=item_list)

@app_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handles user login. Displays the login form on GET and processes credentials on POST.
    """
    if current_user.is_authenticated:
        return redirect(url_for('app.home'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember_me = request.form.get('remember_me') == 'on'
        
        if not User:
            flash("User model not available for login.", "error")
            return render_template('login.html', username=username)
        
        user = User.query.filter_by(username=username).first()

        if user and user.password_hash and bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
            login_user(user, remember=remember_me)
            flash('Logged in successfully.', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('app.home'))
        else:
            flash('Invalid username or password.', 'danger')
    
    return render_template('login.html')

@app_bp.route('/logout')
@login_required
def logout():
    """
    Logs out the current user.
    """
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('app.home'))

@app_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Handles user registration. Displays the registration form on GET and creates a new user on POST.
    """
    if current_user.is_authenticated:
        return redirect(url_for('app.home'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not User:
            flash("User model not available for registration.", "error")
            return render_template('register.html', username=username, email=email)
            
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html', username=username, email=email)

        existing_user = User.query.filter_by(username=username).first()
        existing_email = User.query.filter_by(email=email).first()

        if existing_user:
            flash('Username already taken.', 'danger')
        elif existing_email:
            flash('Email already registered.', 'danger')
        else:
            try:
                hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                new_user = User(username=username, email=email, password_hash=hashed_password)
                db.session.add(new_user)
                db.session.commit()
                flash('Registration successful! Please log in.', 'success')
                return redirect(url_for('app.login'))
            except Exception as e:
                db.session.rollback()
                flash(f'An error occurred during registration: {e}', 'danger')
    
    return render_template('register.html')

@app_bp.route('/profile')
@login_required
def profile():
    """
    Displays the current user's profile information.
    """
    if not User:
        flash("User model not available.", "error")
        return redirect(url_for('app.home'))
        
    user = current_user
    return render_template('profile.html', user=user)

@app_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """
    Allows the current user to edit their profile information.
    Displays the edit form on GET and processes updates on POST.
    """
    if not User:
        flash("User model not available for profile editing.", "error")
        return redirect(url_for('app.profile'))

    user = current_user
    if request.method == 'POST':
        user.email = request.form.get('email')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if new_password:
            if new_password == confirm_password:
                user.password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            else:
                flash('New passwords do not match.', 'danger')
                return render_template('edit_profile.html', user=user)

        try:
            db.session.commit()
            flash('Profile updated successfully.', 'success')
            return redirect(url_for('app.profile'))
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred while updating profile: {e}', 'danger')
    
    return render_template('edit_profile.html', user=user)

@app_bp.route('/profile/delete', methods=['POST'])
@login_required
def delete_profile():
    """
    Deletes the current user's account. This is a POST-only route for security.
    """
    if not User:
        flash("User model not available for profile deletion.", "error")
        return redirect(url_for('app.profile'))

    user = current_user
    try:
        logout_user() # Log out the user before deleting
        db.session.delete(user)
        db.session.commit()
        flash('Your account has been deleted.', 'info')
        return redirect(url_for('app.home'))
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred while deleting your account: {e}', 'danger')
        return redirect(url_for('app.profile'))

@app_bp.route('/items/<int:item_id>')
def item_detail(item_id):
    """
    Displays the details of a specific item.
    """
    if not Item:
        flash("Item model not available.", "error")
        return redirect(url_for('app.home'))

    item = Item.query.get_or_404(item_id)
    return render_template('item_detail.html', item=item)

@app_bp.route('/items/new', methods=['GET', 'POST'])
@login_required
def create_item():
    """
    Allows logged-in users to create a new item.
    Displays the form on GET and processes item creation on POST.
    """
    if not Item:
        flash("Item model not available for creation.", "error")
        return redirect(url_for('app.home'))

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = request.form.get('price')

        if not name or not description or not price:
            flash('All fields are required.', 'danger')
            return render_template('create_item.html', name=name, description=description, price=price)
        
        try:
            price = float(price)
            # Assuming item has a user_id foreign key to link to the creator
            new_item = Item(name=name, description=description, price=price, user_id=current_user.id)
            db.session.add(new_item)
            db.session.commit()
            flash('Item created successfully!', 'success')
            return redirect(url_for('app.item_detail', item_id=new_item.id))
        except ValueError:
            flash('Price must be a valid number.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred while creating the item: {e}', 'danger')

    return render_template('create_item.html')

@app_bp.route('/items/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_item(item_id):
    """
    Allows the owner of an item to edit its details.
    Displays the edit form on GET and processes updates on POST.
    """
    if not Item:
        flash("Item model not available for editing.", "error")
        return redirect(url_for('app.home'))

    item = Item.query.get_or_404(item_id)

    # Ensure current user is the owner of the item
    if item.user_id != current_user.id:
        flash('You are not authorized to edit this item.', 'danger')
        return redirect(url_for('app.item_detail', item_id=item.id))

    if request.method == 'POST':
        item.name = request.form.get('name')
        item.description = request.form.get('description')
        price = request.form.get('price')

        if not item.name or not item.description or not price:
            flash('All fields are required.', 'danger')
            return render_template('edit_item.html', item=item)

        try:
            item.price = float(price)
            db.session.commit()
            flash('Item updated successfully!', 'success')
            return redirect(url_for('app.item_detail', item_id=item.id))
        except ValueError:
            flash('Price must be a valid number.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred while updating the item: {e}', 'danger')
    
    return render_template('edit_item.html', item=item)

@app_bp.route('/items/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_item(item_id):
    """
    Deletes an item. This is a POST-only route for security.
    Only the owner of the item can delete it.
    """
    if not Item:
        flash("Item model not available for deletion.", "error")
        return redirect(url_for('app.home'))

    item = Item.query.get_or_404(item_id)

    # Ensure current user is the owner of the item
    if item.user_id != current_user.id:
        flash('You are not authorized to delete this item.', 'danger')
        return redirect(url_for('app.item_detail', item_id=item.id))

    try:
        db.session.delete(item)
        db.session.commit()
        flash('Item deleted successfully!', 'info')
        return redirect(url_for('app.home'))
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred while deleting the item: {e}', 'danger')
        return redirect(url_for('app.item_detail', item_id=item.id))

@app_bp.route('/search')
def search():
    """
    Handles item search functionality. Uses Haystack if available, otherwise performs basic DB search.
    """
    query = request.args.get('q', '')
    results = []
    
    if not Item:
        flash("Item model not available for search.", "error")
        return render_template('search_results.html', query=query, results=results)

    if query:
        if SearchQuerySet: # If Haystack is available (e.g., via a Flask-Haystack equivalent or mock)
            try:
                # Assuming Haystack integration searches 'Item' models and provides object wrappers
                haystack_results = SearchQuerySet().filter(content=query)
                results = [r.object for r in haystack_results if r.object]
                flash("Search performed using Haystack.", "info")
            except Exception as e:
                flash(f"Haystack search failed, falling back to database: {e}", "warning")
                # Fallback to basic SQLAlchemy search if Haystack fails
                results = Item.query.filter(
                    (Item.name.ilike(f'%{query}%')) | 
                    (Item.description.ilike(f'%{query}%'))
                ).all()
        else: # Fallback to basic SQLAlchemy search if Haystack is not available
            results = Item.query.filter(
                (Item.name.ilike(f'%{query}%')) | 
                (Item.description.ilike(f'%{query}%'))
            ).all()
            flash("Search performed using basic database query.", "info")
    
    return render_template('search_results.html', query=query, results=results)

@app_bp.route('/request-otp', methods=['GET', 'POST'])
@login_required
def request_otp():
    """
    Requests an OTP to be sent to the user's email.
    """
    if not otp_generator or not send_otp_email:
        flash("OTP functionality is not configured.", "warning")
        return redirect(url_for('app.profile'))

    if request.method == 'POST':
        # Generate OTP
        otp = otp_generator()
        
        # Store OTP in session for verification
        session['otp'] = otp
        session['otp_user_id'] = current_user.id

        # Send OTP via email
        try:
            # Assuming current_user has an 'email' attribute
            send_otp_email(current_user.email, otp)
            flash('OTP has been sent to your email.', 'success')
            return redirect(url_for('app.verify_otp'))
        except Exception as e:
            flash(f'Failed to send OTP: {e}', 'danger')
            # Clear OTP from session if sending failed
            session.pop('otp', None)
            session.pop('otp_user_id', None)
    
    return render_template('request_otp.html')

@app_bp.route('/verify-otp', methods=['GET', 'POST'])
@login_required
def verify_otp():
    """
    Verifies the OTP entered by the user.
    """
    if not validate_otp:
        flash("OTP functionality is not configured.", "warning")
        return redirect(url_for('app.profile'))

    # Check if an OTP was actually requested for the current user
    if 'otp' not in session or session.get('otp_user_id') != current_user.id:
        flash('No OTP request found or request expired. Please request a new one.', 'danger')
        return redirect(url_for('app.request_otp'))
    
    if request.method == 'POST':
        user_otp = request.form.get('otp')
        stored_otp = session.get('otp')

        if validate_otp(user_otp, stored_otp): # Assuming validate_otp handles comparison and expiry
            flash('OTP verified successfully!', 'success')
            # Clear OTP from session after successful verification
            session.pop('otp', None)
            session.pop('otp_user_id', None)
            # You might want to set a session variable indicating OTP is verified for a specific action
            # e.g., session['otp_verified_for_sensitive_action'] = True
            return redirect(url_for('app.profile')) # Or whatever action OTP was for
        else:
            flash('Invalid OTP. Please try again.', 'danger')
    
    return render_template('verify_otp.html')