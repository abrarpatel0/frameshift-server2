from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user, login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
import datetime

try:
    from .models import User, Item, Review, OTP, Cart, CartItem, WishlistItem, Order, OrderItem, Transaction, Category
except ImportError:
    # If models cannot be imported, this indicates a setup issue.
    # For this exercise, we assume models are correctly defined and importable.
    # In a real application, you might raise an error or have mock objects for testing.
    User = Item = Review = OTP = Cart = CartItem = WishlistItem = Order = OrderItem = Transaction = Category = None
    print("Warning: Models could not be imported. Ensure .models is correctly defined.")


try:
    from .util import otp_generator, send_otp_email, validate_otp
except ImportError:
    otp_generator = None
    send_otp_email = None
    validate_otp = None
    print("Warning: OTP utility functions could not be imported.")


try:
    from haystack.query import SearchQuerySet
except ImportError:
    SearchQuerySet = None
    print("Warning: Haystack SearchQuerySet could not be imported.")


try:
    from extensions import db
except ImportError:
    from flask_sqlalchemy import SQLAlchemy
    db = SQLAlchemy()
    print("Warning: extensions.db not found, falling back to basic SQLAlchemy initialization.")


app_bp = Blueprint('app', __name__)

@app_bp.route('/', methods=['GET'])
def home():
    """
    Renders the home page displaying a list of all items.
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
            flash('Username already exists. Please choose a different one.', 'danger')
            return render_template('register.html')

        if User.query.filter_by(email=email).first():
            flash('Email already registered. Please use a different email.', 'danger')
            return render_template('register.html')

        try:
            hashed_password = generate_password_hash(password)
            new_user = User(username=username, email=email, password_hash=hashed_password, is_active=True)
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('app.login'))
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred during registration: {str(e)}', 'danger')
            return render_template('register.html')

    return render_template('register.html')

@app_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handles user login.
    GET: Displays the login form.
    POST: Authenticates the user and redirects to the home page or dashboard.
    """
    if current_user.is_authenticated:
        return redirect(url_for('app.home'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
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
    Logs out the current user and redirects to the home page.
    """
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('app.home'))

@app_bp.route('/otp_login', methods=['GET', 'POST'])
def otp_login():
    """
    Handles OTP-based login.
    GET: Displays the OTP request form.
    POST (request OTP): Sends an OTP to the user's email.
    POST (verify OTP): Verifies the OTP and logs in the user.
    """
    if current_user.is_authenticated:
        return redirect(url_for('app.home'))

    if otp_generator is None or send_otp_email is None or validate_otp is None:
        flash('OTP functionality is not available.', 'danger')
        return redirect(url_for('app.login'))

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'request_otp':
            email = request.form.get('email')
            user = User.query.filter_by(email=email).first()

            if user:
                otp_code = otp_generator()
                try:
                    # Store OTP in DB
                    existing_otp = OTP.query.filter_by(user_id=user.id).first()
                    if existing_otp:
                        existing_otp.otp_code = otp_code
                        existing_otp.created_at = datetime.datetime.now()
                    else:
                        new_otp = OTP(user_id=user.id, otp_code=otp_code)
                        db.session.add(new_otp)
                    db.session.commit()
                    send_otp_email(user.email, otp_code)
                    session['otp_email'] = email # Store email in session to verify later
                    flash('An OTP has been sent to your email.', 'success')
                    return render_template('otp_login.html', otp_sent=True, email=email)
                except Exception as e:
                    db.session.rollback()
                    flash(f'Failed to send OTP: {str(e)}', 'danger')
            else:
                flash('No account found with that email address.', 'danger')
            return render_template('otp_login.html')

        elif action == 'verify_otp':
            email = session.pop('otp_email', None)
            otp_entered = request.form.get('otp')

            if not email:
                flash('OTP session expired or invalid request.', 'danger')
                return redirect(url_for('app.otp_login'))

            user = User.query.filter_by(email=email).first()
            if not user:
                flash('User not found for OTP verification.', 'danger')
                return redirect(url_for('app.otp_login'))

            stored_otp_obj = OTP.query.filter_by(user_id=user.id).first()
            
            if stored_otp_obj and validate_otp(stored_otp_obj.otp_code, otp_entered):
                login_user(user)
                db.session.delete(stored_otp_obj) # Invalidate OTP after successful login
                db.session.commit()
                flash('Logged in successfully via OTP!', 'success')
                return redirect(url_for('app.home'))
            else:
                flash('Invalid or expired OTP.', 'danger')
                return render_template('otp_login.html', otp_sent=True, email=email) # Re-render verification form

    return render_template('otp_login.html')


@app_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """
    Allows authenticated users to view and update their profile.
    GET: Displays the user's profile information.
    POST: Updates the user's profile information.
    """
    if request.method == 'POST':
        # Example: Update email or username (excluding password for simplicity here)
        email = request.form.get('email')
        username = request.form.get('username')

        if not email or not username:
            flash('Email and username cannot be empty.', 'danger')
            return render_template('profile.html', user=current_user)

        # Check if new email/username already exists and is not current user's
        if User.query.filter(User.email == email, User.id != current_user.id).first():
            flash('This email is already taken by another user.', 'danger')
            return render_template('profile.html', user=current_user)
        if User.query.filter(User.username == username, User.id != current_user.id).first():
            flash('This username is already taken by another user.', 'danger')
            return render_template('profile.html', user=current_user)
        
        try:
            current_user.email = email
            current_user.username = username
            db.session.commit()
            flash('Your profile has been updated.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred while updating profile: {str(e)}', 'danger')
        
        return redirect(url_for('app.profile'))
    
    return render_template('profile.html', user=current_user)


@app_bp.route('/item/<int:item_id>')
def item_detail(item_id):
    """
    Displays the details of a specific item.
    """
    item = Item.query.get_or_404(item_id)
    reviews = Review.query.filter_by(item_id=item_id).all()
    return render_template('item_detail.html', item=item, reviews=reviews)

@app_bp.route('/item/add', methods=['GET', 'POST'])
@login_required
def item_add():
    """
    Allows logged-in users (e.g., admins/sellers) to add a new item.
    GET: Displays the add item form.
    POST: Processes the form data and creates a new item.
    """
    # Example authorization: Only admin users can add items
    if not current_user.is_admin: # Assuming User model has an 'is_admin' attribute
        flash('You do not have permission to add items.', 'danger')
        return redirect(url_for('app.home'))

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = request.form.get('price')
        stock = request.form.get('stock')
        category_id = request.form.get('category_id')
        image_url = request.form.get('image_url')

        if not all([name, description, price, stock, category_id]):
            flash('All required fields must be filled.', 'danger')
            return render_template('item_form.html', item=None)

        try:
            new_item = Item(
                name=name,
                description=description,
                price=float(price),
                stock=int(stock),
                category_id=int(category_id),
                image_url=image_url if image_url else None
            )
            db.session.add(new_item)
            db.session.commit()
            flash('Item added successfully!', 'success')
            return redirect(url_for('app.item_detail', item_id=new_item.id))
        except ValueError:
            flash('Invalid price or stock value.', 'danger')
            db.session.rollback()
        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'danger')
            db.session.rollback()

    categories = Category.query.all() # Assuming Category model exists
    return render_template('item_form.html', item=None, categories=categories)


@app_bp.route('/item/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def item_edit(item_id):
    """
    Allows logged-in users (e.g., admins/sellers) to edit an existing item.
    GET: Displays the edit item form pre-filled with item data.
    POST: Processes the form data and updates the item.
    """
    item = Item.query.get_or_404(item_id)
    
    # Example authorization: Only admin users can edit items
    if not current_user.is_admin: # Assuming User model has an 'is_admin' attribute
        flash('You do not have permission to edit items.', 'danger')
        return redirect(url_for('app.item_detail', item_id=item.id))

    if request.method == 'POST':
        try:
            item.name = request.form.get('name')
            item.description = request.form.get('description')
            item.price = float(request.form.get('price'))
            item.stock = int(request.form.get('stock'))
            item.category_id = int(request.form.get('category_id'))
            item.image_url = request.form.get('image_url')

            db.session.commit()
            flash('Item updated successfully!', 'success')
            return redirect(url_for('app.item_detail', item_id=item.id))
        except ValueError:
            flash('Invalid price or stock value.', 'danger')
            db.session.rollback()
        except Exception as e:
            flash(f'An error occurred: {str(e)}', 'danger')
            db.session.rollback()

    categories = Category.query.all()
    return render_template('item_form.html', item=item, categories=categories)

@app_bp.route('/item/<int:item_id>/delete', methods=['POST'])
@login_required
def item_delete(item_id):
    """
    Allows logged-in users (e.g., admins/sellers) to delete an item.
    """
    item = Item.query.get_or_404(item_id)

    # Example authorization: Only admin users can delete items
    if not current_user.is_admin: # Assuming User model has an 'is_admin' attribute
        flash('You do not have permission to delete items.', 'danger')
        return redirect(url_for('app.item_detail', item_id=item.id))

    try:
        db.session.delete(item)
        db.session.commit()
        flash('Item deleted successfully!', 'success')
        return redirect(url_for('app.home'))
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred during deletion: {str(e)}', 'danger')
        return redirect(url_for('app.item_detail', item_id=item.id))


@app_bp.route('/search', methods=['GET'])
def search():
    """
    Handles item search functionality using Haystack (or a simple query if not available).
    """
    query = request.args.get('q', '').strip()
    results = []

    if query:
        if SearchQuerySet:
            # Using Haystack's SearchQuerySet
            sqs_results = SearchQuerySet().autocomplete(content_auto=query).models(Item)
            for result in sqs_results:
                # result.object gives the actual model instance
                if result.object:
                    results.append(result.object)
        else:
            # Fallback to simple SQLAlchemy filter if Haystack is not available
            results = Item.query.filter(Item.name.ilike(f'%{query}%') | Item.description.ilike(f'%{query}%')).all()
    
    return render_template('search_results.html', query=query, results=results)


@app_bp.route('/cart')
@login_required
def cart_detail():
    """
    Displays the current user's shopping cart.
    """
    user_cart = Cart.query.filter_by(user_id=current_user.id).first()
    cart_items = []
    total_price = 0

    if user_cart:
        cart_items = CartItem.query.filter_by(cart_id=user_cart.id).all()
        for item in cart_items:
            total_price += item.quantity * item.item.price if item.item else 0
    
    return render_template('cart.html', cart_items=cart_items, total_price=total_price)

@app_bp.route('/add_to_cart', methods=['POST'])
@login_required
def add_to_cart():
    """
    Adds an item to the current user's cart.
    Accepts item_id and quantity as form data.
    """
    item_id = request.form.get('item_id')
    quantity = request.form.get('quantity', 1, type=int)

    if not item_id or quantity <= 0:
        flash('Invalid item or quantity.', 'danger')
        return redirect(request.referrer or url_for('app.home'))

    item = Item.query.get(item_id)
    if not item:
        flash('Item not found.', 'danger')
        return redirect(request.referrer or url_for('app.home'))

    if item.stock < quantity:
        flash(f'Not enough stock for {item.name}. Available: {item.stock}', 'danger')
        return redirect(request.referrer or url_for('app.item_detail', item_id=item.id))

    try:
        user_cart = Cart.query.filter_by(user_id=current_user.id).first()
        if not user_cart:
            user_cart = Cart(user_id=current_user.id)
            db.session.add(user_cart)
            db.session.commit() # Commit to get cart.id

        cart_item = CartItem.query.filter_by(cart_id=user_cart.id, item_id=item.id).first()
        if cart_item:
            cart_item.quantity += quantity
        else:
            cart_item = CartItem(cart_id=user_cart.id, item_id=item.id, quantity=quantity)
            db.session.add(cart_item)
        
        db.session.commit()
        flash(f'{quantity} x {item.name} added to cart.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding item to cart: {str(e)}', 'danger')
    
    return redirect(request.referrer or url_for('app.cart_detail'))


@app_bp.route('/update_cart_item', methods=['POST'])
@login_required
def update_cart_item():
    """
    Updates the quantity of an item in the current user's cart.
    Accepts cart_item_id and new_quantity as form data.
    """
    cart_item_id = request.form.get('cart_item_id', type=int)
    new_quantity = request.form.get('quantity', type=int)

    if not cart_item_id or new_quantity is None or new_quantity < 0:
        flash('Invalid request to update cart item.', 'danger')
        return redirect(url_for('app.cart_detail'))

    try:
        user_cart = Cart.query.filter_by(user_id=current_user.id).first()
        if not user_cart:
            flash('Your cart is empty.', 'danger')
            return redirect(url_for('app.cart_detail'))

        cart_item = CartItem.query.filter_by(id=cart_item_id, cart_id=user_cart.id).first()
        if not cart_item:
            flash('Cart item not found.', 'danger')
            return redirect(url_for('app.cart_detail'))
        
        if new_quantity == 0:
            db.session.delete(cart_item)
            flash(f'{cart_item.item.name} removed from cart.', 'info')
        else:
            if cart_item.item.stock < new_quantity:
                flash(f'Not enough stock for {cart_item.item.name}. Available: {cart_item.item.stock}', 'danger')
                return redirect(url_for('app.cart_detail'))
            cart_item.quantity = new_quantity
            flash(f'Quantity for {cart_item.item.name} updated.', 'success')
        
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating cart item: {str(e)}', 'danger')
    
    return redirect(url_for('app.cart_detail'))


@app_bp.route('/remove_from_cart', methods=['POST'])
@login_required
def remove_from_cart():
    """
    Removes an item from the current user's cart.
    Accepts cart_item_id as form data.
    """
    cart_item_id = request.form.get('cart_item_id', type=int)

    if not cart_item_id:
        flash('Invalid request to remove item from cart.', 'danger')
        return redirect(url_for('app.cart_detail'))

    try:
        user_cart = Cart.query.filter_by(user_id=current_user.id).first()
        if not user_cart:
            flash('Your cart is empty.', 'danger')
            return redirect(url_for('app.cart_detail'))

        cart_item = CartItem.query.filter_by(id=cart_item_id, cart_id=user_cart.id).first()
        if not cart_item:
            flash('Cart item not found.', 'danger')
            return redirect(url_for('app.cart_detail'))

        item_name = cart_item.item.name if cart_item.item else "Item"
        db.session.delete(cart_item)
        db.session.commit()
        flash(f'{item_name} removed from your cart.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error removing item from cart: {str(e)}', 'danger')
    
    return redirect(url_for('app.cart_detail'))


@app_bp.route('/wishlist')
@login_required
def wishlist_detail():
    """
    Displays the current user's wishlist.
    """
    wishlist_items = WishlistItem.query.filter_by(user_id=current_user.id).all()
    return render_template('wishlist.html', wishlist_items=wishlist_items)


@app_bp.route('/add_to_wishlist', methods=['POST'])
@login_required
def add_to_wishlist():
    """
    Adds an item to the current user's wishlist.
    Accepts item_id as form data.
    """
    item_id = request.form.get('item_id', type=int)

    if not item_id:
        flash('Invalid item.', 'danger')
        return redirect(request.referrer or url_for('app.home'))

    item = Item.query.get(item_id)
    if not item:
        flash('Item not found.', 'danger')
        return redirect(request.referrer or url_for('app.home'))

    try:
        existing_wishlist_item = WishlistItem.query.filter_by(user_id=current_user.id, item_id=item_id).first()
        if existing_wishlist_item:
            flash(f'{item.name} is already in your wishlist.', 'info')
        else:
            new_wishlist_item = WishlistItem(user_id=current_user.id, item_id=item_id)
            db.session.add(new_wishlist_item)
            db.session.commit()
            flash(f'{item.name} added to your wishlist.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding item to wishlist: {str(e)}', 'danger')
    
    return redirect(request.referrer or url_for('app.wishlist_detail'))


@app_bp.route('/remove_from_wishlist', methods=['POST'])
@login_required
def remove_from_wishlist():
    """
    Removes an item from the current user's wishlist.
    Accepts wishlist_item_id as form data.
    """
    wishlist_item_id = request.form.get('wishlist_item_id', type=int)

    if not wishlist_item_id:
        flash('Invalid request to remove item from wishlist.', 'danger')
        return redirect(url_for('app.wishlist_detail'))

    try:
        wishlist_item = WishlistItem.query.filter_by(id=wishlist_item_id, user_id=current_user.id).first()
        if not wishlist_item:
            flash('Wishlist item not found.', 'danger')
            return redirect(url_for('app.wishlist_detail'))

        item_name = wishlist_item.item.name if wishlist_item.item else "Item"
        db.session.delete(wishlist_item)
        db.session.commit()
        flash(f'{item_name} removed from your wishlist.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error removing item from wishlist: {str(e)}', 'danger')
    
    return redirect(url_for('app.wishlist_detail'))


@app_bp.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    """
    Handles the checkout process.
    GET: Displays the checkout page with cart contents and asks for shipping/payment info.
    POST: Processes the order, creates an Order and OrderItems, clears the cart.
    """
    user_cart = Cart.query.filter_by(user_id=current_user.id).first()
    if not user_cart or not user_cart.items: # user_cart.items assumes a relationship
        flash('Your cart is empty. Please add items before checking out.', 'warning')
        return redirect(url_for('app.cart_detail'))

    cart_items = CartItem.query.filter_by(cart_id=user_cart.id).all()
    if not cart_items:
        flash('Your cart is empty. Please add items before checking out.', 'warning')
        return redirect(url_for('app.cart_detail'))

    total_amount = 0
    for cart_item in cart_items:
        if cart_item.item and cart_item.item.stock >= cart_item.quantity:
            total_amount += cart_item.quantity * cart_item.item.price
        else:
            flash(f"Not enough stock for {cart_item.item.name}. Please adjust quantity.", "danger")
            return redirect(url_for('app.cart_detail'))

    if request.method == 'POST':
        # This is where you'd process payment, shipping address, etc.
        # For this example, we'll simulate a successful order.
        try:
            new_order = Order(
                user_id=current_user.id,
                order_date=datetime.datetime.now(),
                total_amount=total_amount,
                status='Pending' # Or 'Processing', 'Completed'
            )
            db.session.add(new_order)
            db.session.flush() # Flush to get new_order.id

            for cart_item in cart_items:
                order_item = OrderItem(
                    order_id=new_order.id,
                    item_id=cart_item.item_id,
                    quantity=cart_item.quantity,
                    price=cart_item.item.price # Price at time of order
                )
                db.session.add(order_item)

                # Decrease stock
                cart_item.item.stock -= cart_item.quantity
                db.session.add(cart_item.item)

                db.session.delete(cart_item) # Remove from cart after adding to order

            db.session.delete(user_cart) # Delete the cart itself
            db.session.commit()
            
            flash('Your order has been placed successfully!', 'success')
            return redirect(url_for('app.order_detail', order_id=new_order.id))
        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred during checkout: {str(e)}', 'danger')
            return redirect(url_for('app.checkout'))

    return render_template('checkout.html', cart_items=cart_items, total_amount=total_amount)


@app_bp.route('/orders')
@login_required
def order_history():
    """
    Displays a list of all orders placed by the current user.
    """
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.order_date.desc()).all()
    return render_template('order_history.html', orders=orders)


@app_bp.route('/order/<int:order_id>')
@login_required
def order_detail(order_id):
    """
    Displays the details of a specific order for the current user.
    """
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    order_items = OrderItem.query.filter_by(order_id=order.id).all()
    
    return render_template('order_detail.html', order=order, order_items=order_items)


@app_bp.route('/item/<int:item_id>/add_review', methods=['POST'])
@login_required
def add_review(item_id):
    """
    Allows authenticated users to add a review for a specific item.
    """
    item = Item.query.get_or_404(item_id)

    rating = request.form.get('rating', type=int)
    comment = request.form.get('comment')

    if not rating or not (1 <= rating <= 5):
        flash('Rating must be between 1 and 5.', 'danger')
        return redirect(url_for('app.item_detail', item_id=item.id))

    try:
        new_review = Review(
            item_id=item.id,
            user_id=current_user.id,
            rating=rating,
            comment=comment,
            created_at=datetime.datetime.now()
        )
        db.session.add(new_review)
        db.session.commit()
        flash('Your review has been added!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred while adding your review: {str(e)}', 'danger')
    
    return redirect(url_for('app.item_detail', item_id=item.id))


@app_bp.route('/review/<int:review_id>/delete', methods=['POST'])
@login_required
def delete_review(review_id):
    """
    Allows authenticated users (or admins) to delete their own review.
    """
    review = Review.query.get_or_404(review_id)

    # Only allow the review owner or an admin to delete the review
    if review.user_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to delete this review.', 'danger')
        return redirect(url_for('app.item_detail', item_id=review.item_id))

    item_id = review.item_id # Store before deleting review

    try:
        db.session.delete(review)
        db.session.commit()
        flash('Review deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred while deleting the review: {str(e)}', 'danger')
    
    return redirect(url_for('app.item_detail', item_id=item_id))

# Example Admin Dashboard (simple)
@app_bp.route('/admin_dashboard')
@login_required
def admin_dashboard():
    """
    A simple admin dashboard.
    Only accessible by admin users.
    """
    if not current_user.is_admin:
        flash('Access denied. You are not an administrator.', 'danger')
        return redirect(url_for('app.home'))
    
    # You could fetch various stats here for the admin dashboard
    total_users = User.query.count()
    total_items = Item.query.count()
    pending_orders = Order.query.filter_by(status='Pending').count()

    return render_template('admin_dashboard.html', 
                            total_users=total_users, 
                            total_items=total_items, 
                            pending_orders=pending_orders)