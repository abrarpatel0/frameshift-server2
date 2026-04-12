from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, abort
from flask_login import login_required, current_user, login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash

try:
    from .models import User, Item, OTP, CartItem, Order, OrderItem, Review, ShippingAddress
except ImportError:
    # This block should ideally not be hit if models are properly structured
    # For conversion purposes, we assume these models exist for type hinting and usage.
    # If the user's project truly lacks these, they would need to define them.
    class User:
        def __init__(self):
            self.id = None
            self.username = ""
            self.email = ""
            self.password_hash = ""
            self.is_otp_enabled = False
        def set_password(self, password):
            self.password_hash = generate_password_hash(password)
        def check_password(self, password):
            return check_password_hash(self.password_hash, password)
        # Mock methods for Flask-Login
        @property
        def is_authenticated(self): return True
        @property
        def is_active(self): return True
        @property
        def is_anonymous(self): return False
        def get_id(self): return str(self.id)
        
        @classmethod
        def query(cls): return None # Placeholder
        def save(self): pass # Placeholder
        def delete(self): pass # Placeholder
        
    class Item:
        def __init__(self):
            self.id = None
            self.name = ""
            self.description = ""
            self.price = 0.0
            self.stock = 0
        @classmethod
        def query(cls): return None # Placeholder
    class OTP:
        def __init__(self):
            self.id = None
            self.user_id = None
            self.otp_code = ""
            self.created_at = None
        @classmethod
        def query(cls): return None # Placeholder
    class CartItem:
        def __init__(self):
            self.id = None
            self.user_id = None
            self.item_id = None
            self.quantity = 0
        @classmethod
        def query(cls): return None # Placeholder
    class Order:
        def __init__(self):
            self.id = None
            self.user_id = None
            self.total_amount = 0.0
            self.created_at = None
            self.shipping_address_id = None
        @classmethod
        def query(cls): return None # Placeholder
    class OrderItem:
        def __init__(self):
            self.id = None
            self.order_id = None
            self.item_id = None
            self.quantity = 0
            self.price = 0.0
        @classmethod
        def query(cls): return None # Placeholder
    class Review:
        def __init__(self):
            self.id = None
            self.user_id = None
            self.item_id = None
            self.rating = 0
            self.comment = ""
        @classmethod
        def query(cls): return None # Placeholder
    class ShippingAddress:
        def __init__(self):
            self.id = None
            self.user_id = None
            self.address_line1 = ""
            self.city = ""
            self.state = ""
            self.zip_code = ""
            self.country = ""
            self.is_default = False
        @classmethod
        def query(cls): return None # Placeholder


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
    Renders the home page, displaying a list of all items.
    """
    item_list = Item.query.all()
    
    return render_template('home.html', item_list=item_list)

@app_bp.route('/item/<int:item_id>', methods=['GET'])
def item_detail(item_id):
    """
    Displays the details of a specific item and its reviews.
    """
    item = Item.query.get_or_404(item_id)
    reviews = Review.query.filter_by(item_id=item_id).all()
    return render_template('item_detail.html', item=item, reviews=reviews)

@app_bp.route('/add_to_cart/<int:item_id>', methods=['POST'])
@login_required
def add_to_cart(item_id):
    """
    Adds a specified item to the current user's cart.
    If the item is already in the cart, its quantity is incremented.
    """
    item = Item.query.get_or_404(item_id)
    quantity = int(request.form.get('quantity', 1))

    if quantity <= 0:
        flash('Quantity must be at least 1.', 'warning')
        return redirect(url_for('app.item_detail', item_id=item_id))

    cart_item = CartItem.query.filter_by(user_id=current_user.id, item_id=item.id).first()

    if cart_item:
        cart_item.quantity += quantity
    else:
        cart_item = CartItem(user_id=current_user.id, item_id=item.id, quantity=quantity)
        db.session.add(cart_item)
    
    try:
        db.session.commit()
        flash(f'{quantity} x {item.name} added to cart!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding item to cart: {e}', 'danger')
    
    return redirect(url_for('app.view_cart'))

@app_bp.route('/cart', methods=['GET'])
@login_required
def view_cart():
    """
    Displays the current user's shopping cart with all items and total amount.
    """
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    total_amount = sum(ci.item.price * ci.quantity for ci in cart_items) if cart_items else 0
    return render_template('cart.html', cart_items=cart_items, total_amount=total_amount)

@app_bp.route('/remove_from_cart/<int:item_id>', methods=['POST'])
@login_required
def remove_from_cart(item_id):
    """
    Removes a specific item from the current user's cart.
    """
    cart_item = CartItem.query.filter_by(user_id=current_user.id, item_id=item_id).first()
    
    if cart_item:
        try:
            db.session.delete(cart_item)
            db.session.commit()
            flash(f'{cart_item.item.name} removed from cart.', 'info')
        except Exception as e:
            db.session.rollback()
            flash(f'Error removing item from cart: {e}', 'danger')
    else:
        flash('Item not found in your cart.', 'warning')
    
    return redirect(url_for('app.view_cart'))

@app_bp.route('/update_cart_quantity/<int:item_id>', methods=['POST'])
@login_required
def update_cart_quantity(item_id):
    """
    Updates the quantity of a specific item in the current user's cart.
    """
    quantity = int(request.form.get('quantity', 1))
    
    if quantity <= 0:
        flash('Quantity must be at least 1.', 'warning')
        return redirect(url_for('app.view_cart'))

    cart_item = CartItem.query.filter_by(user_id=current_user.id, item_id=item_id).first()

    if cart_item:
        cart_item.quantity = quantity
        try:
            db.session.commit()
            flash(f'Quantity for {cart_item.item.name} updated to {quantity}.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating quantity: {e}', 'danger')
    else:
        flash('Item not found in your cart.', 'warning')
    
    return redirect(url_for('app.view_cart'))

@app_bp.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    """
    Handles the checkout process, displaying cart items and shipping options (GET),
    and creating an order (POST).
    """
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not cart_items:
        flash('Your cart is empty. Please add items before checking out.', 'warning')
        return redirect(url_for('app.home'))

    total_amount = sum(ci.item.price * ci.quantity for ci in cart_items)
    shipping_addresses = ShippingAddress.query.filter_by(user_id=current_user.id).all()

    if request.method == 'POST':
        shipping_address_id = request.form.get('shipping_address')
        if not shipping_address_id:
            flash('Please select a shipping address.', 'danger')
            return render_template('checkout.html', cart_items=cart_items, 
                                   total_amount=total_amount, shipping_addresses=shipping_addresses)
        
        selected_address = ShippingAddress.query.get(shipping_address_id)
        if not selected_address or selected_address.user_id != current_user.id:
            flash('Invalid shipping address selected.', 'danger')
            return render_template('checkout.html', cart_items=cart_items, 
                                   total_amount=total_amount, shipping_addresses=shipping_addresses)

        try:
            # Create a new order
            new_order = Order(
                user_id=current_user.id,
                total_amount=total_amount,
                shipping_address_id=selected_address.id
            )
            db.session.add(new_order)
            db.session.flush() # To get new_order.id before commit

            # Create order items from cart items and clear cart
            for cart_item in cart_items:
                if cart_item.item.stock < cart_item.quantity:
                    db.session.rollback()
                    flash(f'Not enough stock for {cart_item.item.name}. Available: {cart_item.item.stock}', 'danger')
                    return render_template('checkout.html', cart_items=cart_items, 
                                           total_amount=total_amount, shipping_addresses=shipping_addresses)
                
                order_item = OrderItem(
                    order_id=new_order.id,
                    item_id=cart_item.item_id,
                    quantity=cart_item.quantity,
                    price=cart_item.item.price
                )
                db.session.add(order_item)
                
                # Update item stock
                cart_item.item.stock -= cart_item.quantity
                db.session.add(cart_item.item)

                db.session.delete(cart_item) # Remove item from cart

            db.session.commit()
            flash('Your order has been placed successfully!', 'success')
            return redirect(url_for('app.order_confirmation', order_id=new_order.id))

        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred during checkout: {e}', 'danger')
            # Log the error for debugging
            print(f"Checkout error: {e}") 

    return render_template('checkout.html', cart_items=cart_items, 
                           total_amount=total_amount, shipping_addresses=shipping_addresses)

@app_bp.route('/order_confirmation/<int:order_id>', methods=['GET'])
@login_required
def order_confirmation(order_id):
    """
    Displays the details of a confirmed order.
    """
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first_or_404()
    order_items = OrderItem.query.filter_by(order_id=order.id).all()
    shipping_address = ShippingAddress.query.get(order.shipping_address_id)
    return render_template('order_confirmation.html', order=order, order_items=order_items, shipping_address=shipping_address)

@app_bp.route('/my_orders', methods=['GET'])
@login_required
def my_orders():
    """
    Displays a list of all orders placed by the current user.
    """
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('my_orders.html', orders=orders)

@app_bp.route('/add_review/<int:item_id>', methods=['GET', 'POST'])
@login_required
def add_review(item_id):
    """
    Allows the current user to add a review for a specific item.
    """
    item = Item.query.get_or_404(item_id)
    existing_review = Review.query.filter_by(user_id=current_user.id, item_id=item_id).first()

    if request.method == 'POST':
        rating = request.form.get('rating')
        comment = request.form.get('comment')

        if not rating or not (1 <= int(rating) <= 5):
            flash('Please provide a valid rating between 1 and 5.', 'danger')
            return render_template('add_review.html', item=item, existing_review=existing_review)

        if existing_review:
            existing_review.rating = int(rating)
            existing_review.comment = comment
            flash('Your review has been updated.', 'success')
        else:
            new_review = Review(
                user_id=current_user.id,
                item_id=item.id,
                rating=int(rating),
                comment=comment
            )
            db.session.add(new_review)
            flash('Your review has been added.', 'success')
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving review: {e}', 'danger')
        
        return redirect(url_for('app.item_detail', item_id=item.id))
    
    return render_template('add_review.html', item=item, existing_review=existing_review)

@app_bp.route('/profile', methods=['GET'])
@login_required
def user_profile():
    """
    Displays the current user's profile information.
    """
    return render_template('profile.html', user=current_user)

@app_bp.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """
    Allows the current user to edit their profile details.
    """
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        
        # Basic validation
        if not username or not email:
            flash('Username and Email are required fields.', 'danger')
            return render_template('edit_profile.html', user=current_user)

        # Check for uniqueness if changed
        if username != current_user.username and User.query.filter_by(username=username).first():
            flash('This username is already taken.', 'danger')
            return render_template('edit_profile.html', user=current_user)
        
        if email != current_user.email and User.query.filter_by(email=email).first():
            flash('This email is already registered.', 'danger')
            return render_template('edit_profile.html', user=current_user)

        current_user.username = username
        current_user.email = email
        
        try:
            db.session.commit()
            flash('Your profile has been updated.', 'success')
            return redirect(url_for('app.user_profile'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating profile: {e}', 'danger')

    return render_template('edit_profile.html', user=current_user)

@app_bp.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    """
    Allows the current user to change their password.
    """
    if request.method == 'POST':
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not current_user.check_password(old_password):
            flash('Incorrect old password.', 'danger')
        elif new_password != confirm_password:
            flash('New password and confirmation do not match.', 'danger')
        elif len(new_password) < 6: # Basic password length check
            flash('New password must be at least 6 characters long.', 'danger')
        else:
            current_user.set_password(new_password)
            try:
                db.session.commit()
                flash('Your password has been updated.', 'success')
                return redirect(url_for('app.user_profile'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error changing password: {e}', 'danger')

    return render_template('change_password.html')

@app_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Handles user registration, creating a new user account.
    If the user is already logged in, they are redirected to the home page.
    """
    if current_user.is_authenticated:
        return redirect(url_for('app.home'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not username or not email or not password:
            flash('All fields are required.', 'danger')
            return render_template('register.html')

        if User.query.filter_by(username=username).first():
            flash('Username already exists. Please choose a different one.', 'danger')
        elif User.query.filter_by(email=email).first():
            flash('Email already registered. Please use a different email or login.', 'danger')
        else:
            new_user = User(username=username, email=email)
            new_user.set_password(password)
            db.session.add(new_user)
            try:
                db.session.commit()
                flash('Registration successful! Please log in.', 'success')
                return redirect(url_for('app.login'))
            except Exception as e:
                db.session.rollback()
                flash(f'An error occurred during registration: {e}', 'danger')

    return render_template('register.html')

@app_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handles user login, authenticating credentials and logging in the user.
    If the user is already logged in, they are redirected to the home page.
    """
    if current_user.is_authenticated:
        return redirect(url_for('app.home'))

    if request.method == 'POST':
        username_or_email = request.form.get('username_or_email')
        password = request.form.get('password')
        remember = request.form.get('remember_me') == 'on'

        user = User.query.filter((User.username == username_or_email) | (User.email == username_or_email)).first()

        if user and user.check_password(password):
            login_user(user, remember=remember)
            flash('Logged in successfully!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('app.home'))
        else:
            flash('Invalid username/email or password.', 'danger')

    return render_template('login.html')

@app_bp.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    """
    Logs out the current user.
    """
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('app.home'))

@app_bp.route('/search', methods=['GET'])
def search_results():
    """
    Performs a search for items based on a query parameter.
    If Haystack's SearchQuerySet is available, it uses that; otherwise,
    it performs a basic SQLAlchemy LIKE search on item names and descriptions.
    """
    query = request.args.get('q', '')
    results = []

    if query:
        if SearchQuerySet:
            # TODO: Haystack SearchQuerySet is Django-specific.
            # A custom search integration for Flask would be needed here,
            # or a Flask-compatible search library like Flask-WhooshAlchemy or a direct Elasticsearch integration.
            # This is a placeholder for a Flask-specific search implementation.
            # For now, we'll fall back to SQLAlchemy LIKE for demonstration.
            flash("SearchQuerySet (Haystack) detected but not fully supported in this Flask conversion context. Falling back to basic search.", "info")
            search_query = f'%{query}%'
            results = Item.query.filter(
                (Item.name.ilike(search_query)) | (Item.description.ilike(search_query))
            ).all()
        else:
            search_query = f'%{query}%'
            results = Item.query.filter(
                (Item.name.ilike(search_query)) | (Item.description.ilike(search_query))
            ).all()
    
    return render_template('search_results.html', query=query, results=results)

@app_bp.route('/otp_setup', methods=['GET', 'POST'])
@login_required
def otp_setup():
    """
    Initiates the OTP setup process for the current user.
    Generates and sends an OTP to the user's email.
    """
    if not (otp_generator and send_otp_email and validate_otp):
        flash('OTP functionality is not configured.', 'danger')
        return redirect(url_for('app.user_profile'))

    if request.method == 'POST':
        try:
            otp_code = otp_generator()
            # In a real app, you'd save a hash of the OTP or a timed token, not plain OTP.
            # For this example, assuming OTP model handles temporary storage.
            
            # Delete any existing OTPs for the user
            OTP.query.filter_by(user_id=current_user.id).delete()
            db.session.flush()

            new_otp = OTP(user_id=current_user.id, otp_code=otp_code)
            db.session.add(new_otp)
            db.session.commit()
            
            send_otp_email(current_user.email, otp_code)
            flash('An OTP has been sent to your email. Please verify.', 'info')
            return redirect(url_for('app.otp_verify'))
        except Exception as e:
            db.session.rollback()
            flash(f'Failed to setup OTP: {e}', 'danger')
            print(f"OTP Setup Error: {e}")
            
    return render_template('otp_setup.html')

@app_bp.route('/otp_verify', methods=['GET', 'POST'])
@login_required
def otp_verify():
    """
    Verifies the OTP entered by the user.
    If valid, enables OTP for the user's account.
    """
    if not (otp_generator and send_otp_email and validate_otp):
        flash('OTP functionality is not configured.', 'danger')
        return redirect(url_for('app.user_profile'))

    # Check if user already has OTP enabled, in which case this page isn't relevant for setup.
    if current_user.is_otp_enabled:
        flash('OTP is already enabled for your account.', 'info')
        return redirect(url_for('app.user_profile'))

    if request.method == 'POST':
        user_otp_code = request.form.get('otp_code')
        
        if not user_otp_code:
            flash('Please enter the OTP.', 'danger')
            return render_template('otp_verify.html')

        otp_record = OTP.query.filter_by(user_id=current_user.id).first()

        if otp_record and validate_otp(otp_record.otp_code, user_otp_code):
            current_user.is_otp_enabled = True
            try:
                db.session.delete(otp_record) # OTP used, so delete it
                db.session.commit()
                flash('OTP enabled successfully!', 'success')
                return redirect(url_for('app.user_profile'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error enabling OTP: {e}', 'danger')
        else:
            flash('Invalid or expired OTP. Please try again.', 'danger')

    return render_template('otp_verify.html')

@app_bp.route('/otp_disable', methods=['POST'])
@login_required
def otp_disable():
    """
    Disables OTP for the current user's account.
    """
    if not (otp_generator and send_otp_email and validate_otp):
        flash('OTP functionality is not configured.', 'danger')
        return redirect(url_for('app.user_profile'))

    if not current_user.is_otp_enabled:
        flash('OTP is not enabled for your account.', 'info')
        return redirect(url_for('app.user_profile'))

    try:
        current_user.is_otp_enabled = False
        # Also remove any pending OTP records
        OTP.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        flash('OTP has been disabled for your account.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to disable OTP: {e}', 'danger')
    
    return redirect(url_for('app.user_profile'))

@app_bp.route('/resend_otp', methods=['POST'])
@login_required
def resend_otp():
    """
    Resends an OTP to the current user's email.
    """
    if not (otp_generator and send_otp_email and validate_otp):
        flash('OTP functionality is not configured.', 'danger')
        return redirect(url_for('app.user_profile'))

    if current_user.is_otp_enabled:
        flash('OTP is already enabled. If you need a new code, disable and re-enable OTP.', 'info')
        return redirect(url_for('app.user_profile'))

    try:
        otp_code = otp_generator()
        otp_record = OTP.query.filter_by(user_id=current_user.id).first()
        
        if otp_record:
            otp_record.otp_code = otp_code # Update existing
        else:
            otp_record = OTP(user_id=current_user.id, otp_code=otp_code)
            db.session.add(otp_record)
        
        db.session.commit()
        send_otp_email(current_user.email, otp_code)
        flash('A new OTP has been sent to your email.', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to resend OTP: {e}', 'danger')
        print(f"Resend OTP Error: {e}")

    return redirect(url_for('app.otp_verify'))

@app_bp.route('/manage_shipping_address', methods=['GET'])
@login_required
def manage_shipping_address():
    """
    Displays a list of shipping addresses for the current user.
    """
    addresses = ShippingAddress.query.filter_by(user_id=current_user.id).all()
    return render_template('manage_shipping_address.html', addresses=addresses)

@app_bp.route('/add_shipping_address', methods=['GET', 'POST'])
@login_required
def add_shipping_address():
    """
    Allows the current user to add a new shipping address.
    """
    if request.method == 'POST':
        address_line1 = request.form.get('address_line1')
        address_line2 = request.form.get('address_line2', '') # Optional
        city = request.form.get('city')
        state = request.form.get('state')
        zip_code = request.form.get('zip_code')
        country = request.form.get('country')
        is_default = request.form.get('is_default') == 'on'

        if not all([address_line1, city, state, zip_code, country]):
            flash('All required fields must be filled.', 'danger')
            return render_template('add_shipping_address.html')

        try:
            # If new address is set as default, unset others
            if is_default:
                ShippingAddress.query.filter_by(user_id=current_user.id, is_default=True).update({'is_default': False})
                db.session.flush()

            new_address = ShippingAddress(
                user_id=current_user.id,
                address_line1=address_line1,
                address_line2=address_line2,
                city=city,
                state=state,
                zip_code=zip_code,
                country=country,
                is_default=is_default
            )
            db.session.add(new_address)
            db.session.commit()
            flash('Shipping address added successfully!', 'success')
            return redirect(url_for('app.manage_shipping_address'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding shipping address: {e}', 'danger')

    return render_template('add_shipping_address.html')

@app_bp.route('/edit_shipping_address/<int:address_id>', methods=['GET', 'POST'])
@login_required
def edit_shipping_address(address_id):
    """
    Allows the current user to edit an existing shipping address.
    """
    address = ShippingAddress.query.filter_by(id=address_id, user_id=current_user.id).first_or_404()

    if request.method == 'POST':
        address.address_line1 = request.form.get('address_line1')
        address.address_line2 = request.form.get('address_line2', '')
        address.city = request.form.get('city')
        address.state = request.form.get('state')
        address.zip_code = request.form.get('zip_code')
        address.country = request.form.get('country')
        is_default = request.form.get('is_default') == 'on'

        if not all([address.address_line1, address.city, address.state, address.zip_code, address.country]):
            flash('All required fields must be filled.', 'danger')
            return render_template('edit_shipping_address.html', address=address)
        
        try:
            # If this address is set as default, unset others.
            # If this address was default and is_default is now false, one might need to pick a new default or leave none.
            # For simplicity, if is_default is true, make it the only default.
            if is_default and not address.is_default:
                ShippingAddress.query.filter_by(user_id=current_user.id, is_default=True).update({'is_default': False})
                db.session.flush() # Ensure update is processed before this address's default state is set
            address.is_default = is_default

            db.session.commit()
            flash('Shipping address updated successfully!', 'success')
            return redirect(url_for('app.manage_shipping_address'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating shipping address: {e}', 'danger')
    
    return render_template('edit_shipping_address.html', address=address)

@app_bp.route('/delete_shipping_address/<int:address_id>', methods=['POST'])
@login_required
def delete_shipping_address(address_id):
    """
    Deletes a specific shipping address for the current user.
    """
    address = ShippingAddress.query.filter_by(id=address_id, user_id=current_user.id).first_or_404()

    try:
        db.session.delete(address)
        db.session.commit()
        flash('Shipping address deleted successfully!', 'info')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting shipping address: {e}', 'danger')
    
    return redirect(url_for('app.manage_shipping_address'))
