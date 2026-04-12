from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, abort
from flask_login import login_required, current_user, login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

try:
    from .models import User, Item, Category, Review # Assuming these models are defined in .models
except ImportError:
    # This block will be ignored as per instruction 10, but kept for context.
    # In a real app, these models would be properly defined.
    class User:
        pass
    class Item:
        pass
    class Category:
        pass
    class Review:
        pass
    print("WARNING: Models (User, Item, Category, Review) could not be imported. Routes might fail.")

try:
    from .util import otp_generator, send_otp_email, validate_otp
except ImportError:
    otp_generator = None
    send_otp_email = None
    validate_otp = None
    print("WARNING: OTP utilities (otp_generator, send_otp_email, validate_otp) could not be imported.")

try:
    from haystack.query import SearchQuerySet
except ImportError:
    SearchQuerySet = None
    print("WARNING: Haystack's SearchQuerySet could not be imported. Search will use basic DB query.")

try:
    from extensions import db
except ImportError:
    from flask_sqlalchemy import SQLAlchemy
    db = SQLAlchemy()
    print("WARNING: 'db' not found in extensions. Initialized a basic SQLAlchemy instance.")


app_bp = Blueprint('app', __name__)

@app_bp.route('/', methods=['GET'])
def home():
    """
    Renders the homepage displaying a list of all items.
    """
    item_list = Item.query.all()
    return render_template('home.html', item_list=item_list)

@app_bp.route('/item/<int:item_id>', methods=['GET'])
def item_detail(item_id):
    """
    Renders the detail page for a specific item.
    """
    item = Item.query.get(item_id)
    if not item:
        flash('Item not found.', 'danger')
        return redirect(url_for('app.home'))
    
    # Assuming Item model has a relationship to Reviews
    reviews = Review.query.filter_by(item_id=item_id).all() 
    return render_template('item_detail.html', item=item, reviews=reviews)

@app_bp.route('/add_item', methods=['GET', 'POST'])
@login_required
def add_item():
    """
    Allows a logged-in user to add a new item.
    Handles both GET (display form) and POST (process form) requests.
    """
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = request.form.get('price')
        category_id = request.form.get('category_id') # Assuming category is selected via ID

        if not all([name, description, price, category_id]):
            flash('All fields are required.', 'danger')
            return render_template('add_item.html')
        
        try:
            price = float(price)
            category = Category.query.get(category_id)
            if not category:
                flash('Invalid category selected.', 'danger')
                return render_template('add_item.html')

            new_item = Item(
                name=name,
                description=description,
                price=price,
                user_id=current_user.id,
                category_id=category.id
            )
            db.session.add(new_item)
            db.session.commit()
            flash('Item added successfully!', 'success')
            return redirect(url_for('app.item_detail', item_id=new_item.id))
        except ValueError:
            flash('Invalid price format.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding item: {str(e)}', 'danger')
            
    categories = Category.query.all() # For populating the category dropdown
    return render_template('add_item.html', categories=categories)

@app_bp.route('/edit_item/<int:item_id>', methods=['GET', 'POST'])
@login_required
def edit_item(item_id):
    """
    Allows the owner of an item to edit its details.
    Handles both GET (display form with existing data) and POST (process form) requests.
    """
    item = Item.query.get(item_id)
    if not item:
        flash('Item not found.', 'danger')
        return redirect(url_for('app.home'))

    if item.user_id != current_user.id:
        flash('You do not have permission to edit this item.', 'danger')
        return redirect(url_for('app.item_detail', item_id=item.id))

    if request.method == 'POST':
        item.name = request.form.get('name')
        item.description = request.form.get('description')
        item.price = request.form.get('price')
        item.category_id = request.form.get('category_id')

        if not all([item.name, item.description, item.price, item.category_id]):
            flash('All fields are required.', 'danger')
            categories = Category.query.all()
            return render_template('edit_item.html', item=item, categories=categories)

        try:
            item.price = float(item.price)
            category = Category.query.get(item.category_id)
            if not category:
                flash('Invalid category selected.', 'danger')
                categories = Category.query.all()
                return render_template('edit_item.html', item=item, categories=categories)

            db.session.commit()
            flash('Item updated successfully!', 'success')
            return redirect(url_for('app.item_detail', item_id=item.id))
        except ValueError:
            flash('Invalid price format.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating item: {str(e)}', 'danger')
            
    categories = Category.query.all()
    return render_template('edit_item.html', item=item, categories=categories)

@app_bp.route('/delete_item/<int:item_id>', methods=['POST'])
@login_required
def delete_item(item_id):
    """
    Allows the owner of an item to delete it.
    Requires a POST request for deletion.
    """
    item = Item.query.get(item_id)
    if not item:
        flash('Item not found.', 'danger')
        return redirect(url_for('app.home'))

    if item.user_id != current_user.id:
        flash('You do not have permission to delete this item.', 'danger')
        return redirect(url_for('app.item_detail', item_id=item.id))

    try:
        db.session.delete(item)
        db.session.commit()
        flash('Item deleted successfully!', 'success')
        return redirect(url_for('app.home'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting item: {str(e)}', 'danger')
        return redirect(url_for('app.item_detail', item_id=item.id))

@app_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Handles user registration.
    Registers a new user account with a unique username and email.
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
            return render_template('register.html')

        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'danger')
            return render_template('register.html')

        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('register.html')

        try:
            hashed_password = generate_password_hash(password)
            new_user = User(username=username, email=email, password_hash=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('app.login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error registering user: {str(e)}', 'danger')

    return render_template('register.html')

@app_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handles user login.
    Authenticates a user and logs them in using Flask-Login.
    """
    if current_user.is_authenticated:
        return redirect(url_for('app.home'))

    if request.method == 'POST':
        username_or_email = request.form.get('username_or_email')
        password = request.form.get('password')
        remember_me = request.form.get('remember_me')

        user = User.query.filter((User.username == username_or_email) | (User.email == username_or_email)).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=remember_me)
            flash('Logged in successfully!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('app.home'))
        else:
            flash('Invalid username/email or password.', 'danger')
    
    return render_template('login.html')

@app_bp.route('/logout')
@login_required
def logout():
    """
    Logs out the current user.
    """
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('app.login'))

@app_bp.route('/profile', defaults={'user_id': None}, methods=['GET'])
@app_bp.route('/profile/<int:user_id>', methods=['GET'])
@login_required
def profile(user_id):
    """
    Displays a user's profile. If no user_id is provided, displays the current user's profile.
    """
    target_user = None
    if user_id:
        target_user = User.query.get(user_id)
        if not target_user:
            flash('User not found.', 'danger')
            return redirect(url_for('app.home'))
    else:
        target_user = current_user
    
    # Optionally fetch items posted by this user
    user_items = Item.query.filter_by(user_id=target_user.id).all()

    return render_template('profile.html', user=target_user, user_items=user_items)

@app_bp.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """
    Allows the current user to edit their profile information.
    Handles both GET (display form with existing data) and POST (process form) requests.
    """
    if request.method == 'POST':
        current_user.username = request.form.get('username', current_user.username)
        current_user.email = request.form.get('email', current_user.email)
        
        new_password = request.form.get('new_password')
        confirm_new_password = request.form.get('confirm_new_password')

        if new_password:
            if new_password != confirm_new_password:
                flash('New passwords do not match.', 'danger')
                return render_template('edit_profile.html', user=current_user)
            current_user.password_hash = generate_password_hash(new_password)

        try:
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('app.profile'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating profile: {str(e)}', 'danger')

    return render_template('edit_profile.html', user=current_user)

@app_bp.route('/send_otp', methods=['POST'])
@login_required
def send_otp():
    """
    Sends a One-Time Password (OTP) to the current user's email for verification.
    """
    if not otp_generator or not send_otp_email:
        flash('OTP functionality is not configured.', 'danger')
        return redirect(url_for('app.profile'))

    try:
        otp = otp_generator()
        current_user.otp = otp
        current_user.otp_timestamp = datetime.utcnow()
        db.session.commit()
        
        send_otp_email(current_user.email, otp) # Assuming send_otp_email takes email and otp
        session['otp_sent_to'] = current_user.email # Store for verification context
        flash('OTP sent to your email. Please check your inbox.', 'info')
        return redirect(url_for('app.verify_otp'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error sending OTP: {str(e)}', 'danger')
        return redirect(url_for('app.profile'))

@app_bp.route('/verify_otp', methods=['GET', 'POST'])
@login_required
def verify_otp():
    """
    Verifies the OTP submitted by the user.
    """
    if not validate_otp:
        flash('OTP validation functionality is not configured.', 'danger')
        return redirect(url_for('app.profile'))

    if current_user.is_verified:
        flash('Your account is already verified.', 'info')
        return redirect(url_for('app.home'))

    if request.method == 'POST':
        user_otp = request.form.get('otp')
        
        # Check if OTP is present and not expired (e.g., 5 minutes expiry)
        if current_user.otp and current_user.otp_timestamp and \
           (datetime.utcnow() - current_user.otp_timestamp) < timedelta(minutes=5):
            
            if validate_otp(current_user.otp, user_otp): # Assuming validate_otp compares stored and input OTP
                current_user.is_verified = True
                current_user.otp = None # Clear OTP after successful verification
                current_user.otp_timestamp = None
                db.session.commit()
                flash('Email successfully verified!', 'success')
                return redirect(url_for('app.profile'))
            else:
                flash('Invalid OTP.', 'danger')
        else:
            flash('OTP expired or not sent. Please request a new one.', 'warning')
        
        return render_template('verify_otp.html')

    return render_template('verify_otp.html')

@app_bp.route('/category/<int:category_id>', methods=['GET'])
def category_items(category_id):
    """
    Displays items belonging to a specific category.
    """
    category = Category.query.get(category_id)
    if not category:
        flash('Category not found.', 'danger')
        return redirect(url_for('app.home'))
    
    items = Item.query.filter_by(category_id=category_id).all()
    return render_template('category_items.html', category=category, items=items)

@app_bp.route('/add_category', methods=['GET', 'POST'])
@login_required # Or check for admin role
def add_category():
    """
    Allows adding a new category.
    """
    # Assuming only admin can add categories, for simplicity we'll just use login_required
    # In a real app, you'd check current_user.is_admin
    
    if request.method == 'POST':
        name = request.form.get('name')
        if not name:
            flash('Category name is required.', 'danger')
            return render_template('add_category.html')
        
        if Category.query.filter_by(name=name).first():
            flash('Category with this name already exists.', 'danger')
            return render_template('add_category.html')

        try:
            new_category = Category(name=name)
            db.session.add(new_category)
            db.session.commit()
            flash('Category added successfully!', 'success')
            return redirect(url_for('app.home')) # Redirect to home or a category list page
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding category: {str(e)}', 'danger')
            
    return render_template('add_category.html')

@app_bp.route('/search', methods=['GET'])
def search():
    """
    Performs a search for items based on a query string.
    Uses Haystack's SearchQuerySet if available, otherwise falls back to basic SQLAlchemy filtering.
    """
    query = request.args.get('q', '').strip()
    results = []
    
    if query:
        if SearchQuerySet:
            # Haystack-like search integration
            # This is a placeholder; actual integration might need more setup
            results = SearchQuerySet().filter(content=query).models(Item)
            # You might need to retrieve the actual Item objects from the search results
            # For example: results = [result.object for result in results if result.object]
            flash(f"Search performed using Haystack (mock): '{query}'", 'info')
        else:
            # Basic SQLAlchemy search on item name and description
            results = Item.query.filter(
                (Item.name.ilike(f'%{query}%')) | (Item.description.ilike(f'%{query}%'))
            ).all()
            flash(f"Basic database search performed for: '{query}'", 'info')
    
    return render_template('search_results.html', query=query, results=results)

@app_bp.route('/user_items/<int:user_id>', methods=['GET'])
def user_items(user_id):
    """
    Displays all items posted by a specific user.
    """
    user = User.query.get(user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('app.home'))
    
    items = Item.query.filter_by(user_id=user_id).all()
    return render_template('user_items.html', user=user, items=items)

@app_bp.route('/item/<int:item_id>/add_review', methods=['GET', 'POST'])
@login_required
def add_review(item_id):
    """
    Allows a logged-in user to add a review for a specific item.
    """
    item = Item.query.get(item_id)
    if not item:
        flash('Item not found.', 'danger')
        return redirect(url_for('app.home'))

    if request.method == 'POST':
        rating = request.form.get('rating')
        comment = request.form.get('comment')

        if not all([rating, comment]):
            flash('Rating and comment are required.', 'danger')
            return render_template('add_review.html', item=item)
        
        try:
            rating = int(rating)
            if not (1 <= rating <= 5):
                raise ValueError("Rating must be between 1 and 5.")

            existing_review = Review.query.filter_by(item_id=item_id, user_id=current_user.id).first()
            if existing_review:
                flash('You have already reviewed this item. You can edit your existing review.', 'warning')
                return redirect(url_for('app.edit_review', review_id=existing_review.id))

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
        except ValueError as ve:
            flash(f'Invalid rating: {str(ve)}', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding review: {str(e)}', 'danger')
            
    return render_template('add_review.html', item=item)

@app_bp.route('/edit_review/<int:review_id>', methods=['GET', 'POST'])
@login_required
def edit_review(review_id):
    """
    Allows the owner of a review to edit their review.
    """
    review = Review.query.get(review_id)
    if not review:
        flash('Review not found.', 'danger')
        return redirect(url_for('app.home'))

    if review.user_id != current_user.id:
        flash('You do not have permission to edit this review.', 'danger')
        return redirect(url_for('app.item_detail', item_id=review.item_id))

    if request.method == 'POST':
        review.rating = request.form.get('rating')
        review.comment = request.form.get('comment')

        if not all([review.rating, review.comment]):
            flash('Rating and comment are required.', 'danger')
            return render_template('edit_review.html', review=review)

        try:
            review.rating = int(review.rating)
            if not (1 <= review.rating <= 5):
                raise ValueError("Rating must be between 1 and 5.")

            db.session.commit()
            flash('Review updated successfully!', 'success')
            return redirect(url_for('app.item_detail', item_id=review.item_id))
        except ValueError as ve:
            flash(f'Invalid rating: {str(ve)}', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating review: {str(e)}', 'danger')

    return render_template('edit_review.html', review=review)

@app_bp.route('/delete_review/<int:review_id>', methods=['POST'])
@login_required
def delete_review(review_id):
    """
    Allows the owner of a review to delete it.
    """
    review = Review.query.get(review_id)
    if not review:
        flash('Review not found.', 'danger')
        return redirect(url_for('app.home'))

    if review.user_id != current_user.id:
        flash('You do not have permission to delete this review.', 'danger')
        return redirect(url_for('app.item_detail', item_id=review.item_id))

    item_id = review.item_id # Store item_id before deleting the review
    try:
        db.session.delete(review)
        db.session.commit()
        flash('Review deleted successfully!', 'success')
        return redirect(url_for('app.item_detail', item_id=item_id))
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting review: {str(e)}', 'danger')
        return redirect(url_for('app.item_detail', item_id=item_id))

# API Routes
# Assuming models have a .to_dict() method for serialization, or we manually serialize

def serialize_item(item):
    """Helper to serialize an Item object to a dictionary."""
    if item:
        return {
            'id': item.id,
            'name': item.name,
            'description': item.description,
            'price': float(item.price), # Ensure price is float for JSON
            'user_id': item.user_id,
            'category_id': item.category_id,
            'created_at': item.created_at.isoformat() if hasattr(item, 'created_at') else None,
            # Add more fields as needed
        }
    return None

@app_bp.route('/api/items', methods=['GET'])
def api_item_list():
    """
    API endpoint to list all items.
    """
    items = Item.query.all()
    items_data = [serialize_item(item) for item in items]
    return jsonify(items_data)

@app_bp.route('/api/items/<int:item_id>', methods=['GET'])
def api_item_detail(item_id):
    """
    API endpoint to retrieve details of a specific item.
    """
    item = Item.query.get(item_id)
    if not item:
        abort(404, description="Item not found")
    
    return jsonify(serialize_item(item))

@app_bp.route('/api/items', methods=['POST'])
@login_required
def api_add_item():
    """
    API endpoint to add a new item. Requires authentication.
    """
    data = request.get_json()
    if not data:
        abort(400, description="Invalid JSON data.")

    name = data.get('name')
    description = data.get('description')
    price = data.get('price')
    category_id = data.get('category_id')

    if not all([name, description, price, category_id]):
        abort(400, description="Missing required fields: name, description, price, category_id.")

    try:
        price = float(price)
        category = Category.query.get(category_id)
        if not category:
            abort(400, description="Invalid category_id.")

        new_item = Item(
            name=name,
            description=description,
            price=price,
            user_id=current_user.id,
            category_id=category.id
        )
        db.session.add(new_item)
        db.session.commit()
        return jsonify(serialize_item(new_item)), 201
    except ValueError:
        abort(400, description="Invalid price format.")
    except Exception as e:
        db.session.rollback()
        abort(500, description=f"Error adding item: {str(e)}")

@app_bp.route('/api/items/<int:item_id>', methods=['PUT', 'PATCH'])
@login_required
def api_update_item(item_id):
    """
    API endpoint to update an existing item. Requires authentication and ownership.
    """
    item = Item.query.get(item_id)
    if not item:
        abort(404, description="Item not found.")

    if item.user_id != current_user.id:
        abort(403, description="You do not have permission to update this item.")

    data = request.get_json()
    if not data:
        abort(400, description="Invalid JSON data.")

    try:
        if 'name' in data:
            item.name = data['name']
        if 'description' in data:
            item.description = data['description']
        if 'price' in data:
            item.price = float(data['price'])
        if 'category_id' in data:
            category = Category.query.get(data['category_id'])
            if not category:
                abort(400, description="Invalid category_id.")
            item.category_id = category.id

        db.session.commit()
        return jsonify(serialize_item(item))
    except ValueError:
        db.session.rollback()
        abort(400, description="Invalid price format.")
    except Exception as e:
        db.session.rollback()
        abort(500, description=f"Error updating item: {str(e)}")

@app_bp.route('/api/items/<int:item_id>', methods=['DELETE'])
@login_required
def api_delete_item(item_id):
    """
    API endpoint to delete an item. Requires authentication and ownership.
    """
    item = Item.query.get(item_id)
    if not item:
        abort(404, description="Item not found.")

    if item.user_id != current_user.id:
        abort(403, description="You do not have permission to delete this item.")

    try:
        db.session.delete(item)
        db.session.commit()
        return jsonify({'message': 'Item deleted successfully.'}), 204
    except Exception as e:
        db.session.rollback()
        abort(500, description=f"Error deleting item: {str(e)}")
