from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user, login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash

# Attempt to import models and extensions
try:
    from .models import *
except ImportError:
    # This block is preserved as per instruction 11.
    # In a real application, proper error handling or a clear indication that
    # models are missing would be necessary. Operations expecting models will fail.
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
    # This block is preserved as per instruction 11.
    # If extensions.db is truly unavailable, this initializes a new SQLAlchemy instance,
    # which might not be the one your models are bound to.
    from flask_sqlalchemy import SQLAlchemy
    db = SQLAlchemy()

app_bp = Blueprint('app', __name__)

@app_bp.route('/', methods=['GET'])
def home():
    """
    Displays a list of all items on the home page.
    """
    item_list = Item.query.all()
    return render_template('home.html', item_list=item_list)


@app_bp.route('/item/<int:item_id>/', methods=['GET'])
def item_detail(item_id):
    """
    Displays the details of a specific item.
    """
    item = Item.query.get_or_404(item_id)
    return render_template('item_detail.html', item=item)


@app_bp.route('/item/create/', methods=['GET', 'POST'])
@login_required
def item_create():
    """
    Handles the creation of a new item.
    GET: Displays the item creation form.
    POST: Processes the form submission, creates the item, and associates it with the current user.
    """
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = request.form.get('price')
        category_id = request.form.get('category')

        if not all([name, description, price, category_id]):
            flash('All fields are required.', 'danger')
            return render_template('item_form.html', item=None, categories=Category.query.all())

        try:
            price = float(price)
            category = Category.query.get(category_id)
            if not category:
                flash('Invalid category selected.', 'danger')
                return render_template('item_form.html', item=None, categories=Category.query.all())

            new_item = Item(
                name=name,
                description=description,
                price=price,
                user_id=current_user.id,
                category_id=category.id
            )
            db.session.add(new_item)
            db.session.commit()
            flash('Item created successfully!', 'success')
            return redirect(url_for('app.item_detail', item_id=new_item.id))
        except ValueError:
            flash('Price must be a valid number.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating item: {e}', 'danger')

    categories = Category.query.all()
    return render_template('item_form.html', item=None, categories=categories)


@app_bp.route('/item/<int:item_id>/update/', methods=['GET', 'POST'])
@login_required
def item_update(item_id):
    """
    Handles the update of an existing item.
    GET: Displays the item update form pre-filled with existing data.
    POST: Processes the form submission and updates the item.
    Only the item's owner can update it.
    """
    item = Item.query.get_or_404(item_id)

    if item.user_id != current_user.id:
        flash('You are not authorized to update this item.', 'danger')
        return redirect(url_for('app.item_detail', item_id=item.id))

    if request.method == 'POST':
        item.name = request.form.get('name')
        item.description = request.form.get('description')
        item.price = request.form.get('price')
        item.category_id = request.form.get('category')

        if not all([item.name, item.description, item.price, item.category_id]):
            flash('All fields are required.', 'danger')
            return render_template('item_form.html', item=item, categories=Category.query.all())

        try:
            item.price = float(item.price)
            category = Category.query.get(item.category_id)
            if not category:
                flash('Invalid category selected.', 'danger')
                return render_template('item_form.html', item=item, categories=Category.query.all())

            db.session.commit()
            flash('Item updated successfully!', 'success')
            return redirect(url_for('app.item_detail', item_id=item.id))
        except ValueError:
            flash('Price must be a valid number.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating item: {e}', 'danger')

    categories = Category.query.all()
    return render_template('item_form.html', item=item, categories=categories)


@app_bp.route('/item/<int:item_id>/delete/', methods=['POST'])
@login_required
def item_delete(item_id):
    """
    Handles the deletion of an existing item.
    Only the item's owner can delete it.
    """
    item = Item.query.get_or_404(item_id)

    if item.user_id != current_user.id:
        flash('You are not authorized to delete this item.', 'danger')
        return redirect(url_for('app.item_detail', item_id=item.id))

    try:
        db.session.delete(item)
        db.session.commit()
        flash('Item deleted successfully!', 'success')
        return redirect(url_for('app.home'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting item: {e}', 'danger')
        return redirect(url_for('app.item_detail', item_id=item.id))


@app_bp.route('/categories/', methods=['GET'])
def category_list():
    """
    Displays a list of all categories.
    """
    categories = Category.query.all()
    return render_template('category_list.html', categories=categories)


@app_bp.route('/category/<int:category_id>/', methods=['GET'])
def category_detail(category_id):
    """
    Displays details of a specific category and items belonging to it.
    """
    category = Category.query.get_or_404(category_id)
    items_in_category = Item.query.filter_by(category_id=category.id).all()
    return render_template('category_detail.html', category=category, items=items_in_category)


@app_bp.route('/register/', methods=['GET', 'POST'])
def register():
    """
    Handles user registration.
    GET: Displays the registration form.
    POST: Processes the form submission, creates a new user, and logs them in.
    """
    if current_user.is_authenticated:
        return redirect(url_for('app.home'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not all([username, email, password, confirm_password]):
            flash('All fields are required.', 'danger')
            return render_template('register.html')

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html', username=username, email=email)

        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return render_template('register.html', email=email)

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('register.html', username=username)

        try:
            hashed_password = generate_password_hash(password)
            new_user = User(username=username, email=email, password_hash=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            flash('Registration successful and you have been logged in!', 'success')
            return redirect(url_for('app.home'))
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred during registration: {e}', 'danger')

    return render_template('register.html')


@app_bp.route('/login/', methods=['GET', 'POST'])
def login():
    """
    Handles user login.
    GET: Displays the login form.
    POST: Processes the form submission, authenticates the user, and logs them in.
    """
    if current_user.is_authenticated:
        return redirect(url_for('app.home'))

    if request.method == 'POST':
        username_or_email = request.form.get('username_or_email')
        password = request.form.get('password')
        remember = request.form.get('remember_me') == 'on'

        user = User.query.filter((User.username == username_or_email) | (User.email == username_or_email)).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=remember)
            flash('Logged in successfully!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('app.home'))
        else:
            flash('Invalid username/email or password.', 'danger')

    return render_template('login.html')


@app_bp.route('/logout/')
@login_required
def logout():
    """
    Logs out the current user.
    """
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('app.home'))


@app_bp.route('/profile/', methods=['GET'])
@login_required
def user_profile():
    """
    Displays the current user's profile and their created items.
    """
    user_items = Item.query.filter_by(user_id=current_user.id).all()
    return render_template('profile.html', user=current_user, items=user_items)


@app_bp.route('/search/', methods=['GET'])
def search():
    """
    Handles item search functionality.
    Uses Haystack SearchQuerySet if available, otherwise performs a basic SQLAlchemy LIKE search.
    """
    query = request.args.get('q', '').strip()
    results = []

    if query:
        if SearchQuerySet:
            # Assuming SearchQuerySet.models(Item).filter(content=query) is the pattern
            # This would typically return SearchResult objects, from which you extract the actual model object.
            try:
                sqs_results = SearchQuerySet().models(Item).filter(content=query)
                results = [result.object for result in sqs_results if result.object]
                flash(f"Search performed using Haystack for '{query}'.", 'info')
            except Exception as e:
                flash(f"Haystack search failed, falling back to basic search: {e}", 'warning')
                # Fallback to basic search if Haystack fails
                results = Item.query.filter(
                    (Item.name.ilike(f'%{query}%')) |
                    (Item.description.ilike(f'%{query}%'))
                ).all()
        else:
            # Basic SQLAlchemy search if Haystack is not available
            results = Item.query.filter(
                (Item.name.ilike(f'%{query}%')) |
                (Item.description.ilike(f'%{query}%'))
            ).all()
            flash(f"Basic search performed for '{query}'.", 'info')
    else:
        flash('Please enter a search query.', 'warning')

    return render_template('search_results.html', query=query, results=results)


@app_bp.route('/otp/setup/', methods=['GET', 'POST'])
@login_required
def otp_setup():
    """
    Handles OTP (One-Time Password) setup for the current user.
    GET: Displays the OTP setup form.
    POST: Generates and sends an OTP, then expects a verification code.
    """
    if not otp_generator or not send_otp_email or not validate_otp:
        flash('OTP functionality is not enabled or fully configured.', 'danger')
        return redirect(url_for('app.home'))

    if request.method == 'POST':
        if not current_user.email:
            flash('Your account does not have an email associated. Cannot set up OTP.', 'danger')
            return redirect(url_for('app.user_profile'))

        # If current_user already has otp_secret, prompt to confirm reset or inform.
        # For simplicity, we'll just regenerate.
        if current_user.otp_secret:
            flash('OTP is already set up. A new secret will be generated, invalidating old codes.', 'warning')

        try:
            secret = otp_generator() # Generate a new secret
            current_user.otp_secret = secret
            current_user.otp_enabled = False # Mark as not yet enabled until verified
            db.session.commit() # Save the secret to the user

            # Send OTP email
            # Assuming send_otp_email takes (recipient_email, secret)
            send_otp_email(current_user.email, secret)
            flash('An OTP has been sent to your email. Please verify it to complete setup.', 'info')
            return redirect(url_for('app.otp_verify')) # Redirect to verification page
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to set up OTP: {e}', 'danger')

    return render_template('otp_setup.html')


@app_bp.route('/otp/verify/', methods=['GET', 'POST'])
@login_required
def otp_verify():
    """
    Verifies an OTP provided by the user.
    GET: Displays the OTP verification form.
    POST: Validates the entered OTP.
    """
    if not otp_generator or not send_otp_email or not validate_otp:
        flash('OTP functionality is not enabled or fully configured.', 'danger')
        return redirect(url_for('app.home'))

    if not current_user.otp_secret:
        flash('OTP setup not initiated. Please set up OTP first.', 'warning')
        return redirect(url_for('app.otp_setup'))

    if request.method == 'POST':
        otp_code = request.form.get('otp_code')
        if not otp_code:
            flash('Please enter the OTP code.', 'danger')
            return render_template('otp_verify.html')

        try:
            # Assuming validate_otp takes (secret, code) and returns True/False
            if validate_otp(current_user.otp_secret, otp_code):
                current_user.otp_enabled = True # Mark OTP as enabled
                db.session.commit()
                flash('OTP verified successfully! Two-factor authentication is now enabled.', 'success')
                return redirect(url_for('app.user_profile'))
            else:
                flash('Invalid OTP code. Please try again.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error verifying OTP: {e}', 'danger')

    return render_template('otp_verify.html')


@app_bp.route('/admin/dashboard/', methods=['GET'])
@login_required
def admin_dashboard():
    """
    Placeholder for an admin dashboard.
    Requires an additional check for user's admin status.
    """
    # Assuming current_user has an 'is_admin' attribute
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        flash('You are not authorized to view the admin dashboard.', 'danger')
        return redirect(url_for('app.home'))

    # Example admin-specific data fetching
    all_users = User.query.all()
    all_items = Item.query.all()
    # TODO: Implement more comprehensive admin logic and data display as needed.

    return render_template('admin_dashboard.html', users=all_users, items=all_items)