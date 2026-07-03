from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
from datetime import datetime
from decimal import Decimal

app = Flask(__name__)
app.secret_key = "auction_secret_key"


def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="shashi",
        database="auction_db"
    )


def serialize_for_json(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: serialize_for_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize_for_json(item) for item in value]
    return value


def get_auction_state(cursor, auction_id):
    cursor.execute("""
        SELECT a.*, i.title, i.description, i.seller_id, u.full_name AS seller_name
        FROM Auctions a
        JOIN Items i ON a.item_id = i.item_id
        JOIN Users u ON i.seller_id = u.user_id
        WHERE a.auction_id = %s
    """, (auction_id,))
    auction_details = cursor.fetchone()

    cursor.execute("""
        SELECT b.bid_amount, b.bid_time, u.full_name
        FROM Bids b
        JOIN Users u ON b.bidder_id = u.user_id
        WHERE b.auction_id = %s
        ORDER BY b.bid_amount DESC, b.bid_time DESC
    """, (auction_id,))
    bids = cursor.fetchall()
    return auction_details, bids


def place_bid_fallback(db, auction_id, bidder_id, bid_amount):
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT current_price, status, end_time FROM Auctions WHERE auction_id = %s FOR UPDATE",
            (auction_id,)
        )
        auction = cursor.fetchone()
        if not auction:
            raise ValueError("Auction not found")
        if auction['status'] not in ('ACTIVE', 'EXTENDED'):
            raise ValueError("Auction is not active")
        if bid_amount <= auction['current_price']:
            raise ValueError("Bid amount must be greater than current price")
        if datetime.now() > auction['end_time']:
            raise ValueError("Auction has ended")

        cursor.execute(
            "INSERT INTO Bids (auction_id, bidder_id, bid_amount) VALUES (%s, %s, %s)",
            (auction_id, bidder_id, bid_amount)
        )
        cursor.execute(
            "UPDATE Auctions SET current_price = %s WHERE auction_id = %s",
            (bid_amount, auction_id)
        )
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()


def get_active_marketplace_auctions(cursor):
    cursor.execute("""
        SELECT a.auction_id, a.current_price, a.end_time, a.status, i.title, i.description, u.full_name AS seller_name
        FROM Auctions a
        JOIN Items i ON a.item_id = i.item_id
        JOIN Users u ON i.seller_id = u.user_id
        WHERE a.status IN ('ACTIVE', 'EXTENDED') AND a.end_time > NOW()
        ORDER BY a.end_time ASC
    """)
    return cursor.fetchall()


@app.route('/')
def index():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    auctions = get_active_marketplace_auctions(cursor)
    db.close()
    return render_template('index.html', auctions=auctions)


@app.route('/api/auctions')
def api_auctions():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    auctions = get_active_marketplace_auctions(cursor)
    db.close()
    return jsonify(serialize_for_json(auctions))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Users WHERE email = %s AND password_hash = %s", (email, password))
        user = cursor.fetchone()
        db.close()

        if user:
            session['user_id'] = user['user_id']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            flash(f"Welcome back, {user['full_name']}! You are signed in as {user['role']}.", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials!", "error")

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        full_name = request.form['full_name']
        role = request.form['role']

        db = get_db_connection()
        cursor = db.cursor()
        try:
            cursor.execute(
                "INSERT INTO Users (email, password_hash, full_name, role) VALUES (%s, %s, %s, %s)",
                (email, password, full_name, role)
            )
            db.commit()
            flash("Registration successful. Please log in.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"Error: {e}", "error")
        finally:
            db.close()

    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/add_auction', methods=['GET', 'POST'])
def add_auction():
    if 'user_id' not in session or session.get('role') != 'Seller':
        flash("Only sellers can add auctions.", "error")
        return redirect(url_for('index'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        start_price = float(request.form['start_price'])
        reserve_price = request.form['reserve_price']
        reserve_price = float(reserve_price) if reserve_price else None
        end_time = request.form['end_time']

        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute("INSERT IGNORE INTO Categories (category_id, name) VALUES (1, 'General')")

        try:
            cursor.execute(
                "INSERT INTO Items (title, description, seller_id, category_id) VALUES (%s, %s, %s, 1)",
                (title, description, session['user_id'])
            )
            item_id = cursor.lastrowid

            start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("""
                INSERT INTO Auctions (item_id, start_time, end_time, start_price, reserve_price, status, current_price)
                VALUES (%s, %s, %s, %s, %s, 'ACTIVE', %s)
            """, (item_id, start_time, end_time, start_price, reserve_price, start_price))

            db.commit()
            flash("Auction added successfully!", "success")
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.rollback()
            flash(f"Error adding auction: {e}", "error")
        finally:
            db.close()

    return render_template('add_auction.html')


@app.route('/auction/<int:auction_id>', methods=['GET', 'POST'])
def auction(auction_id):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    if request.method == 'POST':
        if 'user_id' not in session:
            flash("Please log in to place a bid.", "error")
            return redirect(url_for('login'))

        auction_details, _ = get_auction_state(cursor, auction_id)
        if auction_details and auction_details.get('seller_id') == session['user_id']:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify(success=False, message='You cannot bid on your own auction.'), 403
            flash("You cannot bid on your own auction.", "error")
            return redirect(url_for('auction', auction_id=auction_id))

        bid_amount = float(request.form['bid_amount'])
        try:
            try:
                proc_cursor = db.cursor()
                proc_cursor.callproc('sp_PlaceBid', (auction_id, session['user_id'], bid_amount))
                db.commit()
                proc_cursor.close()
            except mysql.connector.Error as err:
                message = str(err).lower()
                if 'procedure' in message or 'doesn\'t exist' in message or 'not found' in message:
                    place_bid_fallback(db, auction_id, session['user_id'], bid_amount)
                else:
                    raise

            refreshed_cursor = db.cursor(dictionary=True)
            auction_details, bids = get_auction_state(refreshed_cursor, auction_id)
            refreshed_cursor.close()

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify(success=True, auction=serialize_for_json(auction_details), bids=serialize_for_json(bids))

            flash("Bid placed successfully!", "success")
            return redirect(url_for('auction', auction_id=auction_id))
        except Exception as err:
            db.rollback()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify(success=False, message=str(err)), 400
            flash(f"Error placing bid: {err}", "error")

    auction_details, bids = get_auction_state(cursor, auction_id)
    cursor.close()
    db.close()
    return render_template('auction.html', auction=auction_details, bids=bids)


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM vw_UserDashboard WHERE user_id = %s", (session['user_id'],))
    dashboard_data = cursor.fetchone()

    marketplace_auctions = get_active_marketplace_auctions(cursor)

    cursor.execute("""
        SELECT a.auction_id, a.status, a.current_price, a.end_time, i.title, i.description, i.seller_id, a.winner_id
        FROM Auctions a
        JOIN Items i ON a.item_id = i.item_id
        WHERE (i.seller_id = %s OR a.winner_id = %s)
        ORDER BY a.end_time DESC
    """, (session['user_id'], session['user_id']))
    user_auctions = cursor.fetchall()

    cursor.execute("""
        SELECT b.bid_id, b.bid_amount, b.bid_time, a.auction_id, i.title
        FROM Bids b
        JOIN Auctions a ON b.auction_id = a.auction_id
        JOIN Items i ON a.item_id = i.item_id
        WHERE b.bidder_id = %s
        ORDER BY b.bid_time DESC
        LIMIT 10
    """, (session['user_id'],))
    bid_history = cursor.fetchall()

    cursor.execute("SELECT user_id, full_name, email, phone_number, address, role FROM Users WHERE user_id = %s", (session['user_id'],))
    profile = cursor.fetchone()
    cursor.close()
    db.close()

    return render_template('dashboard.html', data=dashboard_data, auctions=user_auctions, bid_history=bid_history, profile=profile, marketplace_auctions=marketplace_auctions)


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        phone_number = request.form.get('phone_number', '').strip()
        address = request.form.get('address', '').strip()

        cursor.execute(
            "UPDATE Users SET full_name = %s, phone_number = %s, address = %s WHERE user_id = %s",
            (full_name, phone_number, address, session['user_id'])
        )
        db.commit()
        session['full_name'] = full_name or session['full_name']
        flash("Profile updated successfully.", "success")

    cursor.execute("SELECT user_id, full_name, email, phone_number, address, role FROM Users WHERE user_id = %s", (session['user_id'],))
    profile = cursor.fetchone()
    cursor.close()
    db.close()
    return render_template('profile.html', profile=profile)


if __name__ == '__main__':
    app.run(debug=True)