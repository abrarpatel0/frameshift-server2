from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user, login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash # For password handling
import datetime # For timestamps and auction closing logic

# Attempt to import models and utilities.
# If these imports fail, it means the application context for these objects
# is not set up, and a TODO comment will indicate where logic might be affected.
try:
    from .models import User, Item, Category, Bid, Watchlist # Assuming these are defined in .models
except ImportError:
    # TODO: Model classes (User, Item, Category, Bid, Watchlist) are not found.
    # The application will fail where these models are used.
    # Ensure models.py is correctly structured and discoverable.
    User, Item, Category, Bid, Watchlist = None, None, None, None, None
    print("WARNING: Could not import models. Please ensure models.py exists and defines User, Item, Category, Bid, Watchlist.")


try:
    from .util import otp_generator, send_otp_email, validate_otp
except ImportError:
    # TODO: OTP utility functions (otp_generator, send_otp_email, validate_otp) are not found.
    # OTP-related functionality will be disabled or fail.
    otp_generator = None
    send_otp_email = None
    validate_otp = None
    print("WARNING: Could not import OTP utilities. OTP functionality will be unavailable.")

try:
    from haystack.query import SearchQuerySet
except ImportError:
    # TODO: Haystack SearchQuerySet is a Django-specific component.
    # Flask applications typically use a different search solution (e.g., ElasticSearch, Whoosh).
    # The search route will implement basic SQLAlchemy filtering instead.
    SearchQuerySet = None
    print("WARNING: Haystack SearchQuerySet is a Django-specific import and will not be used in Flask search.")

try:
    from extensions import db # Preferred way to get db from common extensions
except ImportError:
    from flask_sqlalchemy import SQLAlchemy
    db = SQLAlchemy() # Fallback, but in a real app, `db` should be initialized and bound to the app.
                      # For a Blueprint, `db` usually comes from the main app instance.
                      # Assuming `db` is correctly initialized in the main app and available.
    print("WARNING: Could not import 'db' from extensions. Using fallback SQLAlchemy instance. Ensure 'db' is properly initialized and passed to the app.")

app_bp = Blueprint('app', __name__)

@app_bp.route('/', methods=['GET'])
def home():
    """Displays a list of all active items on the homepage."""
    if Item:
        item_list = Item.query.filter_by(is_active=True).order_by(Item.created_at.desc()).all()
    else:
        item_list = [] # Fallback if Item model is not available
    return render_template('home.html', item_list=item_list)


@app_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Handles user registration."""
    if current_user.is_authenticated:
        return redirect(url_for('app.home'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirmation = request.form.get('confirmation')

        if not all([username, email, password, confirmation]):
            flash("All fields must be filled out.", 'danger')
            return render_template('register.html')

        if password != confirmation:
            flash("Passwords do not match.", 'danger')
            return render_template('register.html')

        if User:
            if User.query.filter_by(username=username).first():
                flash("Username already taken.", 'danger')
                return render_template('register.html')
            if User.query.filter_by(email=email).first():
                flash("Email already registered.", 'danger')
                return render_template('register.html')

            hashed_password = generate_password_hash(password)
            new_user = User(username=username, email=email, password_hash=hashed_password)
            try:
                db.session.add(new_user)
                db.session.commit()
                flash("Registration successful! You can now log in.", 'success')
                return redirect(url_for('app.login'))
            except Exception as e:
                db.session.rollback()
                flash(f"An error occurred during registration: {e}", 'danger')
                return render_template('register.html')
        else:
            flash("User model not available for registration.", 'danger')
            return render_template('register.html')

    return render_template('register.html')

@app_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if current_user.is_authenticated:
        return redirect(url_for('app.home'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember') == 'on' # Checkbox value

        if not all([username, password]):
            flash("Username and password are required.", 'danger')
            return render_template('login.html')
        
        if User:
            user = User.query.filter_by(username=username).first()

            if user and check_password_hash(user.password_hash, password):
                login_user(user, remember=remember)
                flash(f"Welcome back, {user.username}!", 'success')
                next_page = request.args.get('next')
                return redirect(next_page or url_for('app.home'))
            else:
                flash("Invalid username or password.", 'danger')
                return render_template('login.html')
        else:
            flash("User model not available for login.", 'danger')
            return render_template('login.html')

    return render_template('login.html')

@app_bp.route('/logout')
@login_required
def logout():
    """Handles user logout."""
    logout_user()
    flash("You have been logged out.", 'info')
    return redirect(url_for('app.home'))

@app_bp.route('/create_listing', methods=['GET', 'POST'])
@login_required
def create_listing():
    """Allows authenticated users to create a new auction listing."""
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        start_bid = request.form.get('start_bid')
        image_url = request.form.get('image_url')
        category_id = request.form.get('category')

        if not all([title, description, start_bid, category_id]):
            flash("All fields (except image URL) are required.", 'danger')
            return render_template('create_listing.html', categories=Category.query.all() if Category else [])

        try:
            start_bid = float(start_bid)
            if start_bid <= 0:
                raise ValueError("Starting bid must be positive.")
        except ValueError:
            flash("Starting bid must be a valid positive number.", 'danger')
            return render_template('create_listing.html', categories=Category.query.all() if Category else [])

        if not (Item and Category):
            flash("Item or Category model not available.", 'danger')
            return render_template('create_listing.html', categories=Category.query.all() if Category else [])

        category = Category.query.get(category_id)
        if not category:
            flash("Selected category does not exist.", 'danger')
            return render_template('create_listing.html', categories=Category.query.all() if Category else [])

        new_item = Item(
            title=title,
            description=description,
            start_bid=start_bid,
            current_bid=start_bid, # Initial current bid is the start bid
            image_url=image_url if image_url else None,
            category_id=category.id,
            seller_id=current_user.id,
            is_active=True,
            created_at=datetime.datetime.now()
        )

        try:
            db.session.add(new_item)
            db.session.commit()
            flash(f"Listing '{new_item.title}' created successfully!", 'success')
            return redirect(url_for('app.item_detail', item_id=new_item.id))
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred while creating your listing: {e}", 'danger')
            return render_template('create_listing.html', categories=Category.query.all() if Category else [])

    categories = Category.query.all() if Category else []
    return render_template('create_listing.html', categories=categories)


@app_bp.route('/item/<int:item_id>', methods=['GET', 'POST'])
def item_detail(item_id):
    """Displays details of a specific item, handles bids, and allows closing auction."""
    if not (Item and Bid and Watchlist):
        flash("Required models are not available.", 'danger')
        return redirect(url_for('app.home'))

    item = Item.query.get(item_id)
    if not item:
        flash("Item not found.", 'danger')
        return redirect(url_for('app.home'))

    bids = Bid.query.filter_by(item_id=item.id).order_by(Bid.amount.desc()).all()
    highest_bid = bids[0] if bids else None
    
    is_on_watchlist = False
    if current_user.is_authenticated:
        is_on_watchlist = Watchlist.query.filter_by(user_id=current_user.id, item_id=item.id).first() is not None

    if request.method == 'POST':
        if not current_user.is_authenticated:
            flash("You must be logged in to bid.", 'danger')
            return redirect(url_for('app.login'))

        # Check if auction is active
        if not item.is_active:
            flash("This auction has already closed.", 'danger')
            return redirect(url_for('app.item_detail', item_id=item.id))

        # Check if current user is the seller
        if item.seller_id == current_user.id:
            flash("You cannot bid on your own item.", 'danger')
            return redirect(url_for('app.item_detail', item_id=item.id))

        bid_amount = request.form.get('bid_amount')
        try:
            bid_amount = float(bid_amount)
            if bid_amount <= item.current_bid:
                flash(f"Your bid must be higher than the current bid of ${item.current_bid:.2f}.", 'danger')
                return redirect(url_for('app.item_detail', item_id=item.id))
        except ValueError:
            flash("Invalid bid amount.", 'danger')
            return redirect(url_for('app.item_detail', item_id=item.id))

        # Check if the user is already the highest bidder (and trying to bid less than their current highest)
        if highest_bid and highest_bid.bidder_id == current_user.id and bid_amount <= highest_bid.amount:
             flash("Your new bid must be higher than your current highest bid.", 'danger')
             return redirect(url_for('app.item_detail', item_id=item.id))

        new_bid = Bid(item_id=item.id, bidder_id=current_user.id, amount=bid_amount, timestamp=datetime.datetime.now())
        item.current_bid = bid_amount
        item.bid_count = item.bid_count + 1 if item.bid_count is not None else 1

        try:
            db.session.add(new_bid)
            db.session.commit()
            flash(f"Your bid of ${bid_amount:.2f} has been placed!", 'success')
            return redirect(url_for('app.item_detail', item_id=item.id))
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred while placing your bid: {e}", 'danger')
            return redirect(url_for('app.item_detail', item_id=item.id))

    return render_template('item_detail.html',
                           item=item,
                           bids=bids,
                           highest_bid=highest_bid,
                           is_on_watchlist=is_on_watchlist)

@app_bp.route('/close_auction/<int:item_id>', methods=['POST'])
@login_required
def close_auction(item_id):
    """Allows the seller to close their own auction."""
    if not Item:
        flash("Item model not available.", 'danger')
        return redirect(url_for('app.home'))

    item = Item.query.get(item_id)
    if not item:
        flash("Item not found.", 'danger')
        return redirect(url_for('app.home'))

    if item.seller_id != current_user.id:
        flash("You are not authorized to close this auction.", 'danger')
        return redirect(url_for('app.item_detail', item_id=item.id))

    if not item.is_active:
        flash("This auction is already closed.", 'info')
        return redirect(url_for('app.item_detail', item_id=item.id))

    item.is_active = False
    item.closed_at = datetime.datetime.now()

    highest_bid = Bid.query.filter_by(item_id=item.id).order_by(Bid.amount.desc()).first()
    if highest_bid:
        item.winner_id = highest_bid.bidder_id
        flash(f"Auction for '{item.title}' closed. Winner: {highest_bid.bidder.username} with ${highest_bid.amount:.2f}.", 'success')
    else:
        item.winner_id = None
        flash(f"Auction for '{item.title}' closed with no bids.", 'info')

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred while closing the auction: {e}", 'danger')
        return redirect(url_for('app.item_detail', item_id=item.id))

    return redirect(url_for('app.item_detail', item_id=item.id))


@app_bp.route('/watchlist/<int:item_id>', methods=['POST'])
@login_required
def toggle_watchlist(item_id):
    """Adds or removes an item from the current user's watchlist."""
    if not (Item and Watchlist):
        return jsonify({"success": False, "message": "Required models not available."}), 500

    item = Item.query.get(item_id)
    if not item:
        return jsonify({"success": False, "message": "Item not found."}), 404

    watchlist_entry = Watchlist.query.filter_by(user_id=current_user.id, item_id=item.id).first()

    try:
        if watchlist_entry:
            db.session.delete(watchlist_entry)
            db.session.commit()
            flash(f"'{item.title}' removed from watchlist.", 'info')
            is_added = False
        else:
            new_watchlist_entry = Watchlist(user_id=current_user.id, item_id=item.id)
            db.session.add(new_watchlist_entry)
            db.session.commit()
            flash(f"'{item.title}' added to watchlist.", 'success')
            is_added = True
        return jsonify({"success": True, "is_added": is_added, "message": "Watchlist updated."})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Error updating watchlist: {e}"}), 500

@app_bp.route('/watchlist', methods=['GET'])
@login_required
def view_watchlist():
    """Displays all items in the current user's watchlist."""
    if not Watchlist:
        flash("Watchlist model not available.", 'danger')
        return redirect(url_for('app.home'))

    watchlist_items = Watchlist.query.filter_by(user_id=current_user.id).all()
    items = [entry.item for entry in watchlist_items if entry.item] # Ensure item is not None if relationship fails
    return render_template('watchlist.html', items=items)

@app_bp.route('/categories', methods=['GET'])
def categories():
    """Displays a list of all available categories."""
    if Category:
        category_list = Category.query.all()
    else:
        category_list = [] # Fallback if Category model is not available
    return render_template('categories.html', categories=category_list)

@app_bp.route('/category/<int:category_id>', methods=['GET'])
def category_listing(category_id):
    """Displays items within a specific category."""
    if not (Category and Item):
        flash("Category or Item model not available.", 'danger')
        return redirect(url_for('app.home'))

    category = Category.query.get(category_id)
    if not category:
        flash("Category not found.", 'danger')
        return redirect(url_for('app.categories'))

    items = Item.query.filter_by(category_id=category.id, is_active=True).all()
    return render_template('category_listing.html', category=category, items=items)

@app_bp.route('/search', methods=['GET'])
def search():
    """Handles search queries for items based on title or description."""
    query = request.args.get('q', '').strip()
    results = []

    if not Item:
        flash("Item model not available for search.", 'danger')
        return render_template('search_results.html', query=query, results=results)

    if query:
        # Basic SQLAlchemy text search (case-insensitive)
        # For more advanced search, integrate a dedicated search engine (e.g., Elasticsearch, Whoosh)
        results = Item.query.filter(
            (Item.title.ilike(f'%{query}%')) |
            (Item.description.ilike(f'%{query}%'))
        ).filter_by(is_active=True).all()
    else:
        flash("Please enter a search query.", 'info')

    return render_template('search_results.html', query=query, results=results)


@app_bp.route('/my_listings', methods=['GET'])
@login_required
def my_listings():
    """Displays items currently listed by the logged-in user."""
    if not Item:
        flash("Item model not available.", 'danger')
        return redirect(url_for('app.home'))

    active_listings = Item.query.filter_by(seller_id=current_user.id, is_active=True).order_by(Item.created_at.desc()).all()
    closed_listings = Item.query.filter_by(seller_id=current_user.id, is_active=False).order_by(Item.closed_at.desc()).all()

    return render_template('my_listings.html',
                           active_listings=active_listings,
                           closed_listings=closed_listings)

@app_bp.route('/verify_otp', methods=['GET', 'POST'])
@login_required
def verify_otp():
    """Handles OTP verification for a user."""
    if not (otp_generator and send_otp_email and validate_otp):
        flash("OTP functionality is not enabled.", 'danger')
        return redirect(url_for('app.home'))

    if 'otp_sent_to' not in session or session['otp_sent_to'] != current_user.email:
        # If no OTP sent or for a different user, send one
        otp_code = otp_generator() # Assume it generates a code
        current_user.otp_secret = otp_code # Store OTP temporarily
        db.session.commit()
        send_otp_email(current_user.email, otp_code)
        session['otp_sent_to'] = current_user.email
        flash("An OTP has been sent to your email.", 'info')
        return render_template('verify_otp.html')

    if request.method == 'POST':
        user_otp = request.form.get('otp')
        if not user_otp:
            flash("Please enter the OTP.", 'danger')
            return render_template('verify_otp.html')

        if validate_otp(current_user, user_otp): # Assume validate_otp checks against user.otp_secret
            current_user.is_otp_verified = True # Assume a flag on User model
            current_user.otp_secret = None # Clear OTP after verification
            db.session.commit()
            session.pop('otp_sent_to', None)
            flash("OTP verified successfully!", 'success')
            return redirect(url_for('app.home'))
        else:
            flash("Invalid OTP.", 'danger')
            return render_template('verify_otp.html')

    return render_template('verify_otp.html')