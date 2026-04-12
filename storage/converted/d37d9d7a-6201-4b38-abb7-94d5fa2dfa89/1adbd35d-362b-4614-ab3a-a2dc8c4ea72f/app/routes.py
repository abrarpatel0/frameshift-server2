from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, abort
from flask_login import login_required, current_user, login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
import datetime

try:
    from .models import User, Item, CartItem, Order, OrderItem # Assuming these are defined in .models
except ImportError:
    # If models cannot be imported, provide placeholder for IDEs but actual code
    # should have them defined or this will break at runtime.
    class User:
        def __init__(self, username, email, password_hash):
            self.id = None
            self.username = username
            self.email = email
            self.password_hash = password_hash
            self.is_active = True
        def set_password(self, password):
            self.password_hash = generate_password_hash(password)
        def check_password(self, password):
            return check_password_hash(self.password_hash, password)
        def get_id(self):
            return str(self.id)
        @property
        def is_authenticated(self):
            return True
        @property
        def is_anonymous(self):
            return False
        
        @staticmethod
        def query_get(id):
            return None # Placeholder
        @staticmethod
        def query_filter_by(username=None, email=None):
            return MockQuery()

    class Item:
        def __init__(self, name, description, price, stock, seller_id):
            self.id = None
            self.name = name
            self.description = description
            self.price = price
            self.stock = stock
            self.seller_id = seller_id
            self.seller = None # Placeholder for relationship
        @staticmethod
        def query_all(): return []
        @staticmethod
        def query_get(id): return None
        @staticmethod
        def query_filter(condition): return MockQuery()

    class CartItem:
        def __init__(self, user_id, item_id, quantity):
            self.id = None
            self.user_id = user_id
            self.item_id = item_id
            self.quantity = quantity
            self.item = Item(name='Placeholder', description='', price=0, stock=0, seller_id=0) # Placeholder
        @staticmethod
        def query_filter_by(user_id=None, item_id=None): return MockQuery()

    class Order:
        def __init__(self, user_id, total_amount, order_date, status='Pending'):
            self.id = None
            self.user_id = user_id
            self.total_amount = total_amount
            self.order_date = order_date
            self.status = status
            self.items = [] # Placeholder for relationship
        @staticmethod
        def query_filter_by(user_id=None): return MockQuery()
        @staticmethod
        def query_get(id): return None

    class OrderItem:
        def __init__(self, order_id, item_id, quantity, price_at_order):
            self.id = None
            self.order_id = order_id
            self.item_id = item_id
            self.quantity = quantity
            self.price_at_order = price_at_order
            self.item = Item(name='Placeholder', description='', price=0, stock=0, seller_id=0) # Placeholder

    class MockQuery:
        def all(self): return []
        def first(self): return None
        def delete(self): pass
        def update(self, **kwargs): pass
        def get(self, id): return None
        def filter(self, condition): return self
        def filter_by(self, **kwargs): return self

    User.query = MockQuery()
    Item.query = MockQuery()
    CartItem.query = MockQuery()
    Order.query = MockQuery()
    OrderItem.query = MockQuery()


try:
    from .util import otp_generator, send_otp_email, validate_otp
except ImportError:
    # These will remain None if not found, and logic will check for them
    otp_generator = None
    send_otp_email = None
    validate_otp = None

try:
    from haystack.query import SearchQuerySet
except ImportError:
    SearchQuerySet = None # This will remain None if not found, and logic will check for it

try:
    from extensions import db
except ImportError:
    from flask_sqlalchemy import SQLAlchemy
    db = SQLAlchemy()

app_bp = Blueprint('app', __name__)

@app_bp.route('/', methods=['GET'])
def home():
    """
    Renders the home page displaying all available items.
    """
    item_list = Item.query.all()
    
    return render_template('home.html', item_list=item_list)

@app_bp.route('/item/<int:item_id>', methods=['GET'])
def item_detail(item_id):
    """
    Renders the detail page for a specific item.
    """
    item = Item.query.get(item_id)
    if item is None:
        abort(404)
    return render_template('item_detail.html', item=item)

@app_bp.route('/add_item', methods=['GET', 'POST'])
@login_required
def add_item():
    """
    Allows a logged-in user to add a new item for sale.
    """
    if request.method == 'POST':
        try:
            name = request.form['name']
            description = request.form['description']
            price = float(request.form['price'])
            stock = int(request.form['stock'])

            if price <= 0 or stock <= 0:
                flash('Price and stock must be positive values.', 'danger')
                return render_template('add_item.html')

            new_item = Item(
                name=name,
                description=description,
                price=price,
                stock=stock,
                seller_id=current_user.id
            )
            db.session.add(new_item)
            db.session.commit()
            flash(f'Item "{new_item.name}" added successfully!', 'success')
            return redirect(url_for('app.item_detail', item_id=new_item.id))
        except ValueError:
            flash('Invalid price or stock format.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding item: {e}', 'danger')
    return render_template('add_item.html')

@app_bp.route('/update_item/<int:item_id>', methods=['GET', 'POST'])
@login_required
def update_item(item_id):
    """
    Allows the seller to update details of their item.
    """
    item = Item.query.get(item_id)
    if item is None:
        abort(404)

    if item.seller_id != current_user.id:
        flash('You are not authorized to update this item.', 'danger')
        return redirect(url_for('app.item_detail', item_id=item_id))

    if request.method == 'POST':
        try:
            item.name = request.form['name']
            item.description = request.form['description']
            item.price = float(request.form['price'])
            item.stock = int(request.form['stock'])

            if item.price <= 0 or item.stock < 0:
                flash('Price must be positive and stock non-negative.', 'danger')
                return render_template('update_item.html', item=item)
            
            db.session.commit()
            flash(f'Item "{item.name}" updated successfully!', 'success')
            return redirect(url_for('app.item_detail', item_id=item.id))
        except ValueError:
            flash('Invalid price or stock format.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating item: {e}', 'danger')
    return render_template('update_item.html', item=item)

@app_bp.route('/delete_item/<int:item_id>', methods=['POST'])
@login_required
def delete_item(item_id):
    """
    Allows the seller to delete their item.
    """
    item = Item.query.get(item_id)
    if item is None:
        abort(404)

    if item.seller_id != current_user.id:
        flash('You are not authorized to delete this item.', 'danger')
        return redirect(url_for('app.item_detail', item_id=item_id))

    try:
        db.session.delete(item)
        db.session.commit()
        flash(f'Item "{item.name}" deleted successfully!', 'success')
        return redirect(url_for('app.home'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting item: {e}', 'danger')
    return redirect(url_for('app.item_detail', item_id=item_id)) # Fallback redirect

@app_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Handles user registration.
    """
    if current_user.is_authenticated:
        return redirect(url_for('app.home'))

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html', username=username, email=email)

        if User.query.filter_by(username=username).first():
            flash('Username already exists. Please choose a different one.', 'danger')
            return render_template('register.html', username=username, email=email)
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered. Please use a different one or log in.', 'danger')
            return render_template('register.html', username=username, email=email)

        try:
            new_user = User(username=username, email=email, password_hash=generate_password_hash(password))
            # Assuming User model has a set_password method for hashing
            # new_user.set_password(password) # If set_password handles hashing internally
            db.session.add(new_user)
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
    Handles user login.
    """
    if current_user.is_authenticated:
        return redirect(url_for('app.home'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password): # Assuming User model has a check_password method
            login_user(user)
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

@app_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """
    Displays and allows updating of the current user's profile.
    """
    if request.method == 'POST':
        try:
            current_user.email = request.form['email']
            # Add other profile fields if your User model has them, e.g.,
            # current_user.address = request.form.get('address')
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('app.profile'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating profile: {e}', 'danger')
    return render_template('profile.html', user=current_user)

@app_bp.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    """
    Allows a logged-in user to change their password.
    """
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_new_password = request.form['confirm_new_password']

        if not current_user.check_password(current_password):
            flash('Incorrect current password.', 'danger')
            return render_template('change_password.html')

        if new_password != confirm_new_password:
            flash('New passwords do not match.', 'danger')
            return render_template('change_password.html')
        
        if len(new_password) < 6: # Example password policy
            flash('New password must be at least 6 characters long.', 'danger')
            return render_template('change_password.html')

        try:
            current_user.set_password(new_password) # Assuming User model has a set_password method
            db.session.commit()
            flash('Password changed successfully!', 'success')
            return redirect(url_for('app.profile'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error changing password: {e}', 'danger')
    return render_template('change_password.html')

@app_bp.route('/request_otp', methods=['GET', 'POST'])
@login_required
def request_otp():
    """
    Generates and sends an OTP to the user's email for verification.
    """
    if otp_generator and send_otp_email:
        try:
            otp = otp_generator()
            session['otp'] = otp
            session['otp_user_id'] = current_user.id
            session['otp_timestamp'] = datetime.datetime.now().timestamp() # Store timestamp for expiration
            
            send_otp_email(current_user.email, otp)
            flash('An OTP has been sent to your email address.', 'info')
            return redirect(url_for('app.verify_otp'))
        except Exception as e:
            flash(f'Error sending OTP: {e}', 'danger')
    else:
        flash('OTP functionality is not configured.', 'warning')
    return render_template('request_otp.html') # Or redirect to profile if no specific page

@app_bp.route('/verify_otp', methods=['GET', 'POST'])
@login_required
def verify_otp():
    """
    Verifies the OTP entered by the user.
    """
    if not ('otp' in session and 'otp_user_id' in session and session['otp_user_id'] == current_user.id):
        flash('No OTP request found or session expired. Please request a new one.', 'warning')
        return redirect(url_for('app.request_otp'))

    if request.method == 'POST':
        user_otp = request.form['otp']
        stored_otp = session.get('otp')
        otp_timestamp = session.get('otp_timestamp')

        # Basic OTP expiration check (e.g., 5 minutes)
        if otp_timestamp and (datetime.datetime.now().timestamp() - otp_timestamp > 300): # 300 seconds = 5 minutes
            session.pop('otp', None)
            session.pop('otp_user_id', None)
            session.pop('otp_timestamp', None)
            flash('OTP has expired. Please request a new one.', 'danger')
            return redirect(url_for('app.request_otp'))

        if validate_otp and validate_otp(stored_otp, user_otp): # Assuming validate_otp handles comparison
            session.pop('otp', None)
            session.pop('otp_user_id', None)
            session.pop('otp_timestamp', None)
            flash('OTP verified successfully!', 'success')
            # Here you might set a session flag, update user status, etc.
            return redirect(url_for('app.profile'))
        else:
            flash('Invalid OTP. Please try again.', 'danger')
    return render_template('verify_otp.html')

@app_bp.route('/search', methods=['GET'])
def search():
    """
    Performs a search for items based on a query parameter.
    """
    query = request.args.get('q', '').strip()
    items = []

    if query:
        try:
            if SearchQuerySet: # If Haystack or similar search engine is integrated
                # This is a highly simplified example. Haystack integration would be more complex.
                sqs = SearchQuerySet().auto_query(query)
                # Assuming SearchResult objects have a 'object' attribute that is an Item model
                item_ids = [result.object.id for result in sqs if result.object is not None]
                items = Item.query.filter(Item.id.in_(item_ids)).all() if item_ids else []
            else:
                # Fallback to basic LIKE query
                search_pattern = f"%{query}%"
                items = Item.query.filter(
                    (Item.name.ilike(search_pattern)) | 
                    (Item.description.ilike(search_pattern))
                ).all()
            
            if not items and SearchQuerySet: # If Haystack was used but found nothing, try basic search as fallback
                search_pattern = f"%{query}%"
                items = Item.query.filter(
                    (Item.name.ilike(search_pattern)) | 
                    (Item.description.ilike(search_pattern))
                ).all()

        except Exception as e:
            flash(f'An error occurred during search: {e}', 'danger')
            items = []
    
    return render_template('search_results.html', query=query, item_list=items)


@app_bp.route('/add_to_cart/<int:item_id>', methods=['POST'])
@login_required
def add_to_cart(item_id):
    """
    Adds an item to the current user's shopping cart.
    """
    item = Item.query.get(item_id)
    if item is None:
        abort(404)

    if item.stock < 1:
        flash(f'Sorry, {item.name} is out of stock.', 'danger')
        return redirect(url_for('app.item_detail', item_id=item_id))

    try:
        cart_item = CartItem.query.filter_by(user_id=current_user.id, item_id=item_id).first()
        if cart_item:
            if cart_item.quantity + 1 > item.stock:
                flash(f'Cannot add more {item.name}. Only {item.stock} available.', 'warning')
            else:
                cart_item.quantity += 1
                flash(f'Increased quantity of "{item.name}" in your cart.', 'success')
        else:
            new_cart_item = CartItem(user_id=current_user.id, item_id=item_id, quantity=1)
            db.session.add(new_cart_item)
            flash(f'"{item.name}" added to your cart.', 'success')
        
        db.session.commit()
        return redirect(url_for('app.view_cart'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding item to cart: {e}', 'danger')
    return redirect(url_for('app.item_detail', item_id=item_id))

@app_bp.route('/cart', methods=['GET'])
@login_required
def view_cart():
    """
    Displays the current user's shopping cart.
    """
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    total_price = sum(ci.quantity * ci.item.price for ci in cart_items if ci.item)
    return render_template('cart.html', cart_items=cart_items, total_price=total_price)

@app_bp.route('/remove_from_cart/<int:item_id>', methods=['POST'])
@login_required
def remove_from_cart(item_id):
    """
    Removes an item from the current user's shopping cart.
    """
    cart_item = CartItem.query.filter_by(user_id=current_user.id, item_id=item_id).first()
    if cart_item is None:
        flash('Item not found in your cart.', 'danger')
        return redirect(url_for('app.view_cart'))

    try:
        db.session.delete(cart_item)
        db.session.commit()
        flash(f'"{cart_item.item.name}" removed from your cart.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error removing item from cart: {e}', 'danger')
    return redirect(url_for('app.view_cart'))

@app_bp.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    """
    Handles the checkout process, creating an order from the cart.
    """
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not cart_items:
        flash('Your cart is empty. Please add items before checking out.', 'warning')
        return redirect(url_for('app.home'))

    total_amount = sum(ci.quantity * ci.item.price for ci in cart_items if ci.item)

    if request.method == 'POST':
        try:
            # Check stock again before finalizing order
            for ci in cart_items:
                if ci.item.stock < ci.quantity:
                    flash(f'Not enough stock for "{ci.item.name}". Only {ci.item.stock} available.', 'danger')
                    return redirect(url_for('app.view_cart'))

            new_order = Order(
                user_id=current_user.id,
                total_amount=total_amount,
                order_date=datetime.datetime.now(),
                status='Pending' # Or 'Processing', etc.
            )
            db.session.add(new_order)
            db.session.flush() # To get order_id before committing

            for ci in cart_items:
                order_item = OrderItem(
                    order_id=new_order.id,
                    item_id=ci.item_id,
                    quantity=ci.quantity,
                    price_at_order=ci.item.price
                )
                db.session.add(order_item)
                
                # Decrease item stock
                ci.item.stock -= ci.quantity
                db.session.add(ci.item) # Ensure item update is staged

                db.session.delete(ci) # Clear item from cart
            
            db.session.commit()
            flash('Your order has been placed successfully!', 'success')
            return redirect(url_for('app.order_history'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error during checkout: {e}', 'danger')
            return redirect(url_for('app.view_cart'))

    return render_template('checkout.html', cart_items=cart_items, total_amount=total_amount)

@app_bp.route('/order_history', methods=['GET'])
@login_required
def order_history():
    """
    Displays the current user's order history.
    """
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.order_date.desc()).all()
    return render_template('order_history.html', orders=orders)

@app_bp.route('/order/<int:order_id>', methods=['GET'])
@login_required
def view_order(order_id):
    """
    Displays the details of a specific order for the current user.
    """
    order = Order.query.filter_by(id=order_id, user_id=current_user.id).first()
    if order is None:
        abort(404)
    # Assuming Order model has a relationship 'items' that fetches OrderItem objects
    return render_template('order_detail.html', order=order)

@app_bp.route('/webhook_receiver', methods=['POST'])
def webhook_receiver():
    """
    Receives and processes webhook notifications (e.g., from payment gateways).
    This route should be secured by external means (e.g., secret keys, IP whitelisting).
    """
    if not request.is_json:
        return jsonify({'error': 'Request must be JSON'}), 400

    data = request.get_json()
    # Log the incoming webhook data for debugging
    # app.logger.info(f"Received webhook: {data}") # Requires a logger setup

    # Example: Process payment status update for an order
    payment_status = data.get('status')
    order_id = data.get('order_id') # This needs to be consistent with webhook payload

    if not order_id:
        return jsonify({'error': 'Missing order_id in webhook payload'}), 400

    try:
        order = Order.query.get(order_id)
        if order:
            # Update order status based on webhook data
            if payment_status == 'completed':
                order.status = 'Paid'
                flash(f'Order {order_id} status updated to Paid via webhook.', 'info')
            elif payment_status == 'failed':
                order.status = 'Payment Failed'
                flash(f'Order {order_id} status updated to Payment Failed via webhook.', 'warning')
            
            db.session.commit()
            return jsonify({'message': f'Order {order_id} updated successfully'}), 200
        else:
            return jsonify({'message': f'Order {order_id} not found'}), 404
    except Exception as e:
        db.session.rollback()
        # app.logger.error(f"Error processing webhook for order {order_id}: {e}")
        return jsonify({'error': f'Failed to process webhook: {e}'}), 500

@app_bp.route('/api/items', methods=['GET', 'POST'])
def api_items():
    """
    API endpoint for listing all items (GET) or creating a new item (POST).
    """
    if request.method == 'GET':
        items = Item.query.all()
        # Serialize items to a list of dictionaries
        items_data = [{'id': item.id, 'name': item.name, 'description': item.description,
                       'price': str(item.price), 'stock': item.stock, 'seller_id': item.seller_id}
                      for item in items]
        return jsonify(items_data)

    elif request.method == 'POST':
        if not current_user.is_authenticated:
            return jsonify({'message': 'Authentication required'}), 401
        
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400

        data = request.get_json()
        name = data.get('name')
        description = data.get('description')
        price = data.get('price')
        stock = data.get('stock')

        if not all([name, price, stock]):
            return jsonify({'error': 'Missing required fields: name, price, stock'}), 400
        
        try:
            price = float(price)
            stock = int(stock)
            if price <= 0 or stock <= 0:
                return jsonify({'error': 'Price and stock must be positive values'}), 400

            new_item = Item(name=name, description=description, price=price, stock=stock, seller_id=current_user.id)
            db.session.add(new_item)
            db.session.commit()
            return jsonify({'message': 'Item created successfully', 'item': {
                'id': new_item.id, 'name': new_item.name, 'description': new_item.description,
                'price': str(new_item.price), 'stock': new_item.stock, 'seller_id': new_item.seller_id
            }}), 201
        except ValueError:
            db.session.rollback()
            return jsonify({'error': 'Invalid price or stock format'}), 400
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Failed to create item: {e}'}), 500

@app_bp.route('/api/items/<int:item_id>', methods=['GET', 'PUT', 'DELETE'])
def api_item_detail(item_id):
    """
    API endpoint for retrieving, updating, or deleting a specific item.
    """
    item = Item.query.get(item_id)
    if item is None:
        return jsonify({'message': 'Item not found'}), 404

    if request.method == 'GET':
        return jsonify({
            'id': item.id, 'name': item.name, 'description': item.description,
            'price': str(item.price), 'stock': item.stock, 'seller_id': item.seller_id
        })

    # For PUT and DELETE, require authentication and ownership
    if not current_user.is_authenticated:
        return jsonify({'message': 'Authentication required'}), 401
    
    if item.seller_id != current_user.id:
        return jsonify({'message': 'You are not authorized to modify this item'}), 403

    if request.method == 'PUT':
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
        data = request.get_json()
        try:
            if 'name' in data:
                item.name = data['name']
            if 'description' in data:
                item.description = data['description']
            if 'price' in data:
                price = float(data['price'])
                if price <= 0:
                    return jsonify({'error': 'Price must be positive'}), 400
                item.price = price
            if 'stock' in data:
                stock = int(data['stock'])
                if stock < 0:
                    return jsonify({'error': 'Stock cannot be negative'}), 400
                item.stock = stock
            
            db.session.commit()
            return jsonify({'message': 'Item updated successfully', 'item': {
                'id': item.id, 'name': item.name, 'description': item.description,
                'price': str(item.price), 'stock': item.stock, 'seller_id': item.seller_id
            }}), 200
        except ValueError:
            db.session.rollback()
            return jsonify({'error': 'Invalid price or stock format'}), 400
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Failed to update item: {e}'}), 500

    elif request.method == 'DELETE':
        try:
            db.session.delete(item)
            db.session.commit()
            return jsonify({'message': 'Item deleted successfully'}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Failed to delete item: {e}'}), 500