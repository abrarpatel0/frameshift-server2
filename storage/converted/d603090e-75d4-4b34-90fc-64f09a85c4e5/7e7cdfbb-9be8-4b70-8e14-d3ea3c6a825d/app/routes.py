from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, abort
from flask_login import login_required, current_user, login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

try:
    from .models import User, Item, Category, Review, OTP
except ImportError:
    # As per instructions, do not invent mock classes.
    # If models are not imported, routes relying on them will raise NameError.
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
    """
    Renders the home page with a list of all items.
    """
    item_list = Item.query.all()
    
    return render_template('home.html', item_list=item_list)

@app_bp.route('/item/<int:item_id>', methods=['GET'])
def item_detail(item_id):
    """
    Displays the details of a specific item, including its reviews.
    """
    item = Item.query.get_or_404(item_id)
    reviews = Review.query.filter_by(item_id=item_id).all()
    return render_template('item_detail.html', item=item, reviews=reviews)

@app_bp.route('/item/create', methods=['GET', 'POST'])
@login_required
def item_create():
    """
    Allows a logged-in user to create a new item.
    """
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price_str = request.form.get('price')
        category_id_str = request.form.get('category_id')

        if not all([name, description, price_str, category_id_str]):
            flash('All fields are required.', 'danger')
            return redirect(url_for('app.item_create'))

        try:
            price = float(price_str)
            if price <= 0:
                raise ValueError("Price must be positive.")
            category_id = int(category_id_str)
        except ValueError:
            flash('Invalid price or category ID.', 'danger')
            return redirect(url_for('app.item_create'))

        category = Category.query.get(category_id)
        if not category:
            flash('Selected category does not exist.', 'danger')
            return redirect(url_for('app.item_create'))

        try:
            new_item = Item(
                name=name,
                description=description,
                price=price,
                category_id=category_id,
                user_id=current_user.id
            )
            db.session.add(new_item)
            db.session.commit()
            flash('Item created successfully!', 'success')
            return redirect(url_for('app.item_detail', item_id=new_item.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating item: {str(e)}', 'danger')
    
    categories = Category.query.all()
    return render_template('item_form.html', categories=categories, title='Create Item')

@app_bp.route('/item/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def item_edit(item_id):
    """
    Allows the owner of an item to edit its details.
    """
    item = Item.query.get_or_404(item_id)

    if item.user_id != current_user.id:
        flash('You are not authorized to edit this item.', 'danger')
        return redirect(url_for('app.item_detail', item_id=item.id))

    if request.method == 'POST':
        item.name = request.form.get('name')
        item.description = request.form.get('description')
        price_str = request.form.get('price')
        category_id_str = request.form.get('category_id')

        if not all([item.name, item.description, price_str, category_id_str]):
            flash('All fields are required.', 'danger')
            return redirect(url_for('app.item_edit', item_id=item.id))
        
        try:
            item.price = float(price_str)
            if item.price <= 0:
                raise ValueError("Price must be positive.")
            item.category_id = int(category_id_str)
        except ValueError:
            flash('Invalid price or category ID.', 'danger')
            return redirect(url_for('app.item_edit', item_id=item.id))

        category = Category.query.get(item.category_id)
        if not category:
            flash('Selected category does not exist.', 'danger')
            return redirect(url_for('app.item_edit', item_id=item.id))

        try:
            db.session.commit()
            flash('Item updated successfully!', 'success')
            return redirect(url_for('app.item_detail', item_id=item.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating item: {str(e)}', 'danger')

    categories = Category.query.all()
    return render_template('item_form.html', item=item, categories=categories, title='Edit Item')

@app_bp.route('/item/<int:item_id>/delete', methods=['POST'])
@login_required
def item_delete(item_id):
    """
    Allows the owner of an item to delete it.
    """
    item = Item.query.get_or_404(item_id)

    if item.user_id != current_user.id:
        flash('You are not authorized to delete this item.', 'danger')
        return redirect(url_for('app.item_detail', item_id=item.id))

    try:
        # Delete associated reviews first if they are not cascaded
        Review.query.filter_by(item_id=item.id).delete(synchronize_session=False)
        db.session.delete(item)
        db.session.commit()
        flash('Item deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting item: {str(e)}', 'danger')
    
    return redirect(url_for('app.home'))

@app_bp.route('/category/<int:category_id>', methods=['GET'])
def category_detail(category_id):
    """
    Displays items belonging to a specific category.
    """
    category = Category.query.get_or_404(category_id)
    items = Item.query.filter_by(category_id=category_id).all()
    return render_template('category_detail.html', category=category, items=items)

@app_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Allows a new user to register an account.
    Handles optional OTP verification.
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
            return redirect(url_for('app.register'))

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('app.register'))
        
        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'danger')
            return redirect(url_for('app.register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('app.register'))

        try:
            hashed_password = generate_password_hash(password)
            # Mark as inactive until OTP if used, otherwise active immediately
            new_user = User(username=username, email=email, password_hash=hashed_password, 
                            is_active=(not (otp_generator and send_otp_email)))
            db.session.add(new_user)
            db.session.commit()

            if otp_generator and send_otp_email:
                otp_code = otp_generator()
                otp_expiry = datetime.utcnow() + timedelta(minutes=10)
                
                otp_record = OTP(user_id=new_user.id, code=otp_code, expiry=otp_expiry)
                db.session.add(otp_record)
                db.session.commit()
                
                send_otp_email(new_user.email, otp_code)
                session['user_id_for_otp'] = new_user.id
                flash('Registration successful! Please check your email for OTP to activate your account.', 'info')
                return redirect(url_for('app.verify_otp'))
            else:
                flash('Registration successful! You can now log in.', 'success')
                return redirect(url_for('app.login'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error during registration: {str(e)}', 'danger')
    
    return render_template('register.html')

@app_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handles user login.
    Supports optional OTP verification.
    """
    if current_user.is_authenticated:
        return redirect(url_for('app.home'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = bool(request.form.get('remember'))

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            if not user.is_active:
                flash('Your account is not active. Please verify your OTP or complete registration.', 'warning')
                if otp_generator and send_otp_email:
                    # Allow resending OTP if not active and OTP is enabled
                    otp_code = otp_generator()
                    otp_expiry = datetime.utcnow() + timedelta(minutes=10)
                    otp_record = OTP(user_id=user.id, code=otp_code, expiry=otp_expiry)
                    db.session.add(otp_record)
                    db.session.commit()
                    send_otp_email(user.email, otp_code)
                    session['user_id_for_otp'] = user.id
                    flash('A new OTP has been sent to your email to activate your account.', 'info')
                    return redirect(url_for('app.verify_otp'))
                return redirect(url_for('app.login')) # No OTP configured, just fail if not active

            if otp_generator and send_otp_email:
                otp_code = otp_generator()
                otp_expiry = datetime.utcnow() + timedelta(minutes=10)
                
                # Create a new OTP for login attempt
                otp_record = OTP(user_id=user.id, code=otp_code, expiry=otp_expiry)
                db.session.add(otp_record)
                db.session.commit()
                send_otp_email(user.email, otp_code)
                
                session['user_id_for_otp'] = user.id
                flash('OTP sent to your email. Please verify to log in.', 'info')
                return redirect(url_for('app.verify_otp'))
            else:
                login_user(user, remember=remember)
                flash('Logged in successfully!', 'success')
                return redirect(request.args.get('next') or url_for('app.home'))
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

@app_bp.route('/profile', methods=['GET'])
@login_required
def user_profile_current():
    """
    Displays the profile of the currently logged-in user.
    """
    user_items = Item.query.filter_by(user_id=current_user.id).all()
    user_reviews = Review.query.filter_by(user_id=current_user.id).all()
    return render_template('profile.html', user=current_user, user_items=user_items, user_reviews=user_reviews)

@app_bp.route('/profile/<int:user_id>', methods=['GET'])
def user_profile_public(user_id):
    """
    Displays the public profile of a specific user.
    """
    user = User.query.get_or_404(user_id)
    user_items = Item.query.filter_by(user_id=user_id).all()
    user_reviews = Review.query.filter_by(user_id=user_id).all()
    return render_template('profile.html', user=user, user_items=user_items, user_reviews=user_reviews)

@app_bp.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    """
    Handles OTP verification for registration or login.
    """
    user_id_for_otp = session.get('user_id_for_otp')
    if not user_id_for_otp:
        flash('No pending OTP verification.', 'warning')
        return redirect(url_for('app.login'))

    user = User.query.get(user_id_for_otp)
    if not user:
        flash('Invalid user for OTP verification.', 'danger')
        session.pop('user_id_for_otp', None)
        return redirect(url_for('app.login'))

    if not validate_otp:
        flash('OTP verification is not configured.', 'danger')
        session.pop('user_id_for_otp', None)
        return redirect(url_for('app.login'))

    if request.method == 'POST':
        otp_code_entered = request.form.get('otp_code')

        try:
            if validate_otp(user.id, otp_code_entered):
                user.is_active = True # Activate user on successful OTP
                db.session.commit()
                session.pop('user_id_for_otp', None) # Clear OTP session data
                login_user(user) # Log in the user after verification
                flash('Account activated and logged in successfully!', 'success')
                return redirect(url_for('app.home'))
            else:
                flash('Invalid or expired OTP. Please try again.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error during OTP verification: {str(e)}', 'danger')

    return render_template('verify_otp.html', user_email=user.email)

@app_bp.route('/search', methods=['GET'])
def search_view():
    """
    Handles item search functionality.
    Uses Haystack (SearchQuerySet) if available, otherwise performs basic LIKE search.
    """
    query = request.args.get('q', '').strip()
    search_results = []
    
    if query:
        if SearchQuerySet:
            # Assumes SearchQuerySet().auto_query(query).models(Item).load_all()
            # would return objects directly or objects that have a .object attribute
            try:
                sqs_results = SearchQuerySet().auto_query(query).models(Item)
                for result in sqs_results:
                    if hasattr(result, 'object'):
                        search_results.append(result.object)
                    else:
                        # Fallback if result.object is not directly populated by Haystack setup
                        item = Item.query.get(result.pk)
                        if item:
                            search_results.append(item)
                flash(f"Search using configured search backend for '{query}'", 'info')
            except Exception as e:
                flash(f"Search backend error: {str(e)}. Falling back to basic search.", 'warning')
                SearchQuerySet = None # Disable for this request if it failed
        
        if not SearchQuerySet: # Fallback to basic SQLAlchemy LIKE search if no search backend or it failed
            search_results = Item.query.filter(
                (Item.name.ilike(f'%{query}%')) |
                (Item.description.ilike(f'%{query}%'))
            ).all()
            if not search_results:
                flash(f"No results found for '{query}'.", 'info')
            else:
                flash(f"Basic search for '{query}' yielded {len(search_results)} results.", 'info')
    else:
        flash('Please enter a search query.', 'warning')
        
    return render_template('search_results.html', query=query, search_results=search_results)

@app_bp.route('/item/<int:item_id>/review', methods=['GET', 'POST'])
@login_required
def add_review(item_id):
    """
    Allows a logged-in user to add a review to a specific item.
    """
    item = Item.query.get_or_404(item_id)

    if request.method == 'POST':
        rating_str = request.form.get('rating')
        comment = request.form.get('comment')

        if not all([rating_str, comment]):
            flash('Rating and comment are required.', 'danger')
            return redirect(url_for('app.add_review', item_id=item.id))
        
        try:
            rating = int(rating_str)
            if not (1 <= rating <= 5):
                raise ValueError("Rating must be between 1 and 5.")
        except ValueError:
            flash('Invalid rating. Please provide a number between 1 and 5.', 'danger')
            return redirect(url_for('app.add_review', item_id=item.id))
        
        existing_review = Review.query.filter_by(item_id=item.id, user_id=current_user.id).first()
        if existing_review:
            flash('You have already reviewed this item. You can edit your existing review if allowed.', 'warning')
            # In a full app, you might redirect to an edit_review route or allow editing on this page
            return redirect(url_for('app.item_detail', item_id=item.id)) 

        try:
            new_review = Review(
                item_id=item.id,
                user_id=current_user.id,
                rating=rating,
                comment=comment
            )
            db.session.add(new_review)
            db.session.commit()
            flash('Review added successfully!', 'success')
            return redirect(url_for('app.item_detail', item_id=item.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding review: {str(e)}', 'danger')

    return render_template('review_form.html', item=item, title='Add Review')