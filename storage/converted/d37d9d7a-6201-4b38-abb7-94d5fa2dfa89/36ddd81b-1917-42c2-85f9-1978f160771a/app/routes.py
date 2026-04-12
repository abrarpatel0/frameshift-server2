from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user, login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError, OperationalError
from datetime import datetime, timedelta

try:
    from .models import User, Item, Category # Assuming these models are defined
except ImportError:
    # This block will only be triggered if models.py is not found or empty.
    # We will assume models exist for the purpose of implementing routes.
    # If they truly don't exist in the project, routes would fail at runtime.
    class User:
        # Placeholder for User model methods used in routes
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
            self.id = 1 # Dummy ID
        def set_password(self, password):
            self.password_hash = generate_password_hash(password)
        def check_password(self, password):
            return check_password_hash(self.password_hash, password) if hasattr(self, 'password_hash') else False
        def get_id(self): return str(self.id)
        @property
        def is_active(self): return True # For Flask-Login
        @property
        def is_authenticated(self): return True # For Flask-Login
        @property
        def is_anonymous(self): return False # For Flask-Login
        query = type('UserQuery', (object,), {'get': lambda self, id: None, 'filter_by': lambda self, **kwargs: self, 'first': lambda self: None, 'all': lambda self: []})()
    
    class Item:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
            self.id = 1
        query = type('ItemQuery', (object,), {'get': lambda self, id: None, 'filter_by': lambda self, **kwargs: self, 'all': lambda self: []})()
    
    class Category:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
            self.id = 1
        query = type('CategoryQuery', (object,), {'get': lambda self, id: None, 'all': lambda self: []})()

    # Define minimal placeholder classes to avoid NameErrors if models.py is truly missing
    # In a real application, this would indicate a serious problem and these placeholders
    # would lead to runtime errors for any ORM operation.
    print("WARNING: models.py or some models within it could not be imported. Using placeholder classes.")


try:
    from .util import otp_generator, send_otp_email, validate_otp, generate_password_reset_token, validate_password_reset_token
except ImportError:
    otp_generator = None
    send_otp_email = None
    validate_otp = None
    generate_password_reset_token = None
    validate_password_reset_token = None
    print("WARNING: util.py or some functions within it could not be imported. OTP and Password Reset functionality will be limited.")


try:
    from haystack.query import SearchQuerySet # Unlikely to be used directly in Flask without a Flask-specific integration
except ImportError:
    SearchQuerySet = None

try:
    from extensions import db
except ImportError:
    # Fallback for db if extensions.py is not found
    from flask_sqlalchemy import SQLAlchemy
    db = SQLAlchemy()
    print("WARNING: extensions.py or db from it could not be imported. Using fallback SQLAlchemy instance.")


app_bp = Blueprint('app', __name__)

@app_bp.route('/', methods=['GET'])
def home():
    """
    Renders the home page, displaying a list of all items.
    """
    item_list = Item.query.all()
    return render_template('home.html', item_list=item_list)


@app_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Handles user registration.
    GET: Displays the registration form.
    POST: Processes the registration form, creates a new user, and redirects to login.
    """
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        return redirect(url_for('app.home'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not username or not email or not password or not confirm_password:
            flash('All fields are required.', 'danger')
            return render_template('register.html', username=username, email=email)

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html', username=username, email=email)

        try:
            if User.query.filter_by(username=username).first():
                flash('Username already taken. Please choose a different one.', 'danger')
                return render_template('register.html', username=username, email=email)
            if User.query.filter_by(email=email).first():
                flash('Email already registered. Please use a different email.', 'danger')
                return render_template('register.html', username=username, email=email)

            new_user = User(username=username, email=email)
            new_user.set_password(password) # Assuming User model has set_password method
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('app.login'))
        except IntegrityError:
            db.session.rollback()
            flash('An account with this username or email already exists.', 'danger')
        except OperationalError:
            db.session.rollback()
            flash('Database error during registration. Please try again.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'An unexpected error occurred: {e}', 'danger')

    return render_template('register.html')


@app_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handles user login.
    GET: Displays the login form.
    POST: Processes the login form, authenticates the user, and redirects to home or the next page.
    """
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        return redirect(url_for('app.home'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember_me = request.form.get('remember_me')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password): # Assuming User model has check_password method
            login_user(user, remember=remember_me)
            flash('Logged in successfully!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('app.home'))
        else:
            flash('Invalid username or password.', 'danger')
    
    return render_template('login.html')


@app_bp.route('/logout')
@login_required
def logout():
    """
    Logs out the current user and redirects to the login page.
    """
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('app.login'))


@app_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """
    Displays and allows updating the current user's profile.
    GET: Displays the user's profile information.
    POST: Processes updates to the user's profile.
    """
    if request.method == 'POST':
        # Example fields to update: email, username
        new_username = request.form.get('username')
        new_email = request.form.get('email')
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_new_password = request.form.get('confirm_new_password')

        user_updated = False

        if new_username and new_username != current_user.username:
            if User.query.filter_by(username=new_username).first() is None:
                current_user.username = new_username
                user_updated = True
            else:
                flash('Username already exists.', 'danger')
                return render_template('profile.html', user=current_user)

        if new_email and new_email != current_user.email:
            if User.query.filter_by(email=new_email).first() is None:
                current_user.email = new_email
                user_updated = True
            else:
                flash('Email already exists.', 'danger')
                return render_template('profile.html', user=current_user)

        if new_password:
            if not current_password or not current_user.check_password(current_password):
                flash('Incorrect current password.', 'danger')
                return render_template('profile.html', user=current_user)
            if new_password != confirm_new_password:
                flash('New passwords do not match.', 'danger')
                return render_template('profile.html', user=current_user)
            
            current_user.set_password(new_password)
            user_updated = True
            flash('Password updated successfully!', 'success')

        if user_updated:
            try:
                db.session.commit()
                flash('Your profile has been updated.', 'success')
            except OperationalError:
                db.session.rollback()
                flash('Database error while updating profile. Please try again.', 'danger')
            except Exception as e:
                db.session.rollback()
                flash(f'An unexpected error occurred: {e}', 'danger')
        else:
            flash('No changes detected.', 'info')


    return render_template('profile.html', user=current_user)


@app_bp.route('/item/<int:item_id>')
def item_detail(item_id):
    """
    Displays the details of a specific item.
    """
    item = Item.query.get(item_id)
    if not item:
        flash('Item not found.', 'danger')
        return redirect(url_for('app.home'))
    return render_template('item_detail.html', item=item)


@app_bp.route('/item/create', methods=['GET', 'POST'])
@login_required
def item_create():
    """
    Allows a logged-in user to create a new item.
    GET: Displays the item creation form.
    POST: Processes the form, creates a new item, and redirects to its detail page.
    """
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = request.form.get('price')
        category_id = request.form.get('category')

        if not name or not description or not price or not category_id:
            flash('All fields are required.', 'danger')
            # Fetch categories again for re-rendering the form
            categories = Category.query.all()
            return render_template('item_create.html', categories=categories, name=name, description=description, price=price, selected_category=category_id)

        try:
            price_float = float(price)
            category = Category.query.get(int(category_id))

            if not category:
                flash('Invalid category selected.', 'danger')
                categories = Category.query.all()
                return render_template('item_create.html', categories=categories, name=name, description=description, price=price, selected_category=category_id)

            new_item = Item(
                name=name,
                description=description,
                price=price_float,
                user_id=current_user.id, # Assign current user as owner
                category_id=category.id
            )
            db.session.add(new_item)
            db.session.commit()
            flash('Item created successfully!', 'success')
            return redirect(url_for('app.item_detail', item_id=new_item.id))
        except ValueError:
            flash('Price must be a valid number.', 'danger')
        except OperationalError:
            db.session.rollback()
            flash('Database error during item creation. Please try again.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'An unexpected error occurred: {e}', 'danger')
        
        # If an error occurred, re-render the form with existing data and categories
        categories = Category.query.all()
        return render_template('item_create.html', categories=categories, name=name, description=description, price=price, selected_category=category_id)

    # For GET request
    categories = Category.query.all()
    return render_template('item_create.html', categories=categories)


@app_bp.route('/item/update/<int:item_id>', methods=['GET', 'POST'])
@login_required
def item_update(item_id):
    """
    Allows the owner of an item to update its details.
    GET: Displays the item update form pre-filled with existing data.
    POST: Processes the form, updates the item, and redirects to its detail page.
    """
    item = Item.query.get(item_id)
    if not item:
        flash('Item not found.', 'danger')
        return redirect(url_for('app.home'))

    if item.user_id != current_user.id:
        flash('You are not authorized to update this item.', 'danger')
        return redirect(url_for('app.item_detail', item_id=item.id))

    if request.method == 'POST':
        item.name = request.form.get('name')
        item.description = request.form.get('description')
        price = request.form.get('price')
        category_id = request.form.get('category')

        if not item.name or not item.description or not price or not category_id:
            flash('All fields are required.', 'danger')
            categories = Category.query.all()
            return render_template('item_update.html', item=item, categories=categories, selected_category=item.category_id)

        try:
            item.price = float(price)
            category = Category.query.get(int(category_id))
            if not category:
                flash('Invalid category selected.', 'danger')
                categories = Category.query.all()
                return render_template('item_update.html', item=item, categories=categories, selected_category=item.category_id)
            item.category_id = category.id

            db.session.commit()
            flash('Item updated successfully!', 'success')
            return redirect(url_for('app.item_detail', item_id=item.id))
        except ValueError:
            flash('Price must be a valid number.', 'danger')
        except OperationalError:
            db.session.rollback()
            flash('Database error during item update. Please try again.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'An unexpected error occurred: {e}', 'danger')
        
        categories = Category.query.all()
        return render_template('item_update.html', item=item, categories=categories, selected_category=item.category_id)


    # For GET request
    categories = Category.query.all()
    return render_template('item_update.html', item=item, categories=categories, selected_category=item.category_id)


@app_bp.route('/item/delete/<int:item_id>', methods=['POST'])
@login_required
def item_delete(item_id):
    """
    Allows the owner of an item to delete it.
    Requires a POST request for safety.
    """
    item = Item.query.get(item_id)
    if not item:
        flash('Item not found.', 'danger')
        return redirect(url_for('app.home'))

    if item.user_id != current_user.id:
        flash('You are not authorized to delete this item.', 'danger')
        return redirect(url_for('app.item_detail', item_id=item.id))

    try:
        db.session.delete(item)
        db.session.commit()
        flash('Item deleted successfully!', 'success')
        return redirect(url_for('app.home')) # Redirect to home or item list
    except OperationalError:
        db.session.rollback()
        flash('Database error during item deletion. Please try again.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'An unexpected error occurred: {e}', 'danger')
        return redirect(url_for('app.item_detail', item_id=item.id))


@app_bp.route('/categories', methods=['GET'])
def category_list():
    """
    Displays a list of all categories.
    """
    categories = Category.query.all()
    return render_template('category_list.html', categories=categories)


@app_bp.route('/category/<int:category_id>', methods=['GET'])
def category_detail(category_id):
    """
    Displays details of a specific category and items belonging to it.
    """
    category = Category.query.get(category_id)
    if not category:
        flash('Category not found.', 'danger')
        return redirect(url_for('app.category_list'))

    items_in_category = Item.query.filter_by(category_id=category.id).all()
    return render_template('category_detail.html', category=category, items=items_in_category)


@app_bp.route('/search', methods=['GET'])
def search():
    """
    Handles site-wide search functionality.
    If Haystack's SearchQuerySet is available, it uses that.
    Otherwise, it performs a basic keyword search on Item names and descriptions.
    """
    query = request.args.get('q', '').strip()
    results = []

    if query:
        if SearchQuerySet: # If Haystack is available (though typically Flask apps don't use Django Haystack directly)
            # This part would need a Flask-compatible search solution, not Django Haystack.
            # Assuming a custom Flask-Haystack-like integration or direct Elasticsearch/Solr client.
            # For demonstration, we'll keep the idea but note it's not directly Django Haystack.
            # TODO: Replace with a Flask-compatible search integration if SearchQuerySet refers to a custom Flask search.
            flash("SearchQuerySet (Haystack) integration is not typically used directly in Flask. Falling back to basic DB search.", 'info')
            
            # Fallback to basic DB search regardless of SearchQuerySet presence for robustness
            results = Item.query.filter(
                (Item.name.ilike(f'%{query}%')) |
                (Item.description.ilike(f'%{query}%'))
            ).all()

        else: # Basic database search
            results = Item.query.filter(
                (Item.name.ilike(f'%{query}%')) |
                (Item.description.ilike(f'%{query}%'))
            ).all()
            
    return render_template('search_results.html', query=query, results=results)


@app_bp.route('/send_otp', methods=['POST'])
def send_otp():
    """
    Sends a One-Time Password (OTP) to the user's email for verification.
    Requires `otp_generator` and `send_otp_email` utilities.
    """
    email = request.form.get('email')
    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({'success': False, 'message': 'No account found with that email.'}), 404

    if otp_generator and send_otp_email:
        try:
            otp = otp_generator()
            # Store OTP in session or user model for verification
            # Assuming user model has an otp_secret or a temporary storage for OTP
            # For demonstration, we'll use session, but database storage (with expiry) is more robust.
            session['otp_email'] = email
            session['otp_code'] = otp
            session['otp_expiry'] = (datetime.now() + timedelta(minutes=5)).isoformat() # OTP valid for 5 minutes

            send_otp_email(email, otp)
            return jsonify({'success': True, 'message': 'OTP sent to your email.'}), 200
        except Exception as e:
            print(f"Error sending OTP: {e}")
            return jsonify({'success': False, 'message': 'Failed to send OTP. Please try again.'}), 500
    else:
        return jsonify({'success': False, 'message': 'OTP functionality is not configured.'}), 501


@app_bp.route('/verify_otp', methods=['POST'])
def verify_otp():
    """
    Verifies the One-Time Password (OTP) submitted by the user.
    Requires `validate_otp` utility.
    """
    email = request.form.get('email')
    user_otp = request.form.get('otp')

    stored_email = session.get('otp_email')
    stored_otp = session.get('otp_code')
    otp_expiry_str = session.get('otp_expiry')

    if not all([stored_email, stored_otp, otp_expiry_str]):
        return jsonify({'success': False, 'message': 'OTP session expired or not initiated.'}), 400

    otp_expiry = datetime.fromisoformat(otp_expiry_str)

    if datetime.now() > otp_expiry:
        session.pop('otp_email', None)
        session.pop('otp_code', None)
        session.pop('otp_expiry', None)
        return jsonify({'success': False, 'message': 'OTP has expired.'}), 400

    if email != stored_email:
        return jsonify({'success': False, 'message': 'Email mismatch for OTP verification.'}), 400

    if validate_otp:
        if validate_otp(stored_otp, user_otp): # Assuming validate_otp compares stored and user-input
            user = User.query.filter_by(email=email).first()
            if user:
                login_user(user) # Log the user in after successful OTP verification
                session.pop('otp_email', None)
                session.pop('otp_code', None)
                session.pop('otp_expiry', None)
                flash('OTP verified and logged in successfully!', 'success')
                return jsonify({'success': True, 'message': 'OTP verified. Logging you in.', 'redirect': url_for('app.home')}), 200
            else:
                return jsonify({'success': False, 'message': 'User not found after OTP verification.'}), 404
        else:
            return jsonify({'success': False, 'message': 'Invalid OTP.'}), 401
    else:
        return jsonify({'success': False, 'message': 'OTP validation functionality is not configured.'}), 501


@app_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    """
    Handles forgotten password requests.
    GET: Displays the forgot password form.
    POST: Processes the form, sends a password reset link to the user's email.
    """
    if current_user.is_authenticated:
        return redirect(url_for('app.home'))

    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()

        if user:
            if generate_password_reset_token and send_otp_email: # Using send_otp_email as a generic email sender
                try:
                    token = generate_password_reset_token(user) # Assuming this function generates and stores a token
                    reset_link = url_for('app.reset_password', token=token, _external=True)
                    send_otp_email(user.email, f"Click the link to reset your password: {reset_link}", subject="Password Reset Request")
                    flash('A password reset link has been sent to your email address.', 'info')
                except Exception as e:
                    print(f"Error sending password reset email: {e}")
                    flash('Failed to send password reset email. Please try again later.', 'danger')
            else:
                flash('Password reset functionality is not configured.', 'danger')
        else:
            # For security, we give the same message whether the email exists or not
            flash('If an account with that email exists, a password reset link has been sent.', 'info')
        
        return redirect(url_for('app.login')) # Redirect to login after sending email (or not)

    return render_template('forgot_password.html')


@app_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """
    Allows a user to reset their password using a valid token.
    GET: Displays the reset password form if the token is valid.
    POST: Processes the form, updates the user's password, and redirects to login.
    """
    if current_user.is_authenticated:
        return redirect(url_for('app.home'))

    if not validate_password_reset_token:
        flash('Password reset functionality is not configured.', 'danger')
        return redirect(url_for('app.login'))

    user = validate_password_reset_token(token) # Assuming this function returns user if token is valid and not expired

    if not user:
        flash('The password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('app.forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_new_password = request.form.get('confirm_new_password')

        if not new_password or not confirm_new_password:
            flash('Both password fields are required.', 'danger')
            return render_template('reset_password.html', token=token)

        if new_password != confirm_new_password:
            flash('Passwords do not match.', 'danger')
            return render_template('reset_password.html', token=token)

        try:
            user.set_password(new_password)
            # Invalidate the token after use (e.g., delete it from DB or mark as used)
            # TODO: Implement token invalidation logic in util.py or here if token is db-backed.
            db.session.commit()
            flash('Your password has been reset successfully. Please log in.', 'success')
            return redirect(url_for('app.login'))
        except OperationalError:
            db.session.rollback()
            flash('Database error during password reset. Please try again.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'An unexpected error occurred: {e}', 'danger')

    return render_template('reset_password.html', token=token)