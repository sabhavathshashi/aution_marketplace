from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from datetime import datetime

app = Flask(__name__)
app.secret_key = "auction_secret_key"

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="shashi", # Change if your password is different
        database="auction_db"
    )

@app.route('/')
def index():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM vw_ActiveAuctions")
    auctions = cursor.fetchall()
    db.close()
    return render_template('index.html', auctions=auctions)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        # Using raw password matching for simplicity in this minimal project
        cursor.execute("SELECT * FROM Users WHERE email = %s AND password_hash = %s", (email, password))
        user = cursor.fetchone()
        db.close()
        
        if user:
            session['user_id'] = user['user_id']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            return redirect(url_for('index'))
        else:
            flash("Invalid credentials!")
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        full_name = request.form['full_name']
        role = request.form['role']
        
        db = get_db_connection()
        cursor = db.cursor()
        try:
            cursor.execute("INSERT INTO Users (email, password_hash, full_name, role) VALUES (%s, %s, %s, %s)",
                           (email, password, full_name, role))
            db.commit()
            flash("Registration successful. Please log in.")
            return redirect(url_for('login'))
        except Exception as e:
            flash(f"Error: {e}")
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
        flash("Only sellers can add auctions.")
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        start_price = float(request.form['start_price'])
        reserve_price = request.form['reserve_price']
        reserve_price = float(reserve_price) if reserve_price else None
        end_time = request.form['end_time'] # Format: YYYY-MM-DDTHH:MM
        
        db = get_db_connection()
        cursor = db.cursor()
        
        # Ensure a default category exists for simplicity
        cursor.execute("INSERT IGNORE INTO Categories (category_id, name) VALUES (1, 'General')")
        
        try:
            # Insert Item
            cursor.execute("INSERT INTO Items (title, description, seller_id, category_id) VALUES (%s, %s, %s, 1)",
                           (title, description, session['user_id']))
            item_id = cursor.lastrowid
            
            # Insert Auction
            start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("""
                INSERT INTO Auctions (item_id, start_time, end_time, start_price, reserve_price, status, current_price)
                VALUES (%s, %s, %s, %s, %s, 'ACTIVE', %s)
            """, (item_id, start_time, end_time, start_price, reserve_price, start_price))
            
            db.commit()
            flash("Auction added successfully!")
            return redirect(url_for('index'))
        except Exception as e:
            db.rollback()
            flash(f"Error adding auction: {e}")
        finally:
            db.close()
            
    return render_template('add_auction.html')

@app.route('/auction/<int:auction_id>', methods=['GET', 'POST'])
def auction(auction_id):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    
    if request.method == 'POST':
        if 'user_id' not in session:
            flash("Please log in to place a bid.")
            return redirect(url_for('login'))
            
        bid_amount = float(request.form['bid_amount'])
        try:
            # Call Stored Procedure for placing a bid
            cursor.callproc('sp_PlaceBid', (auction_id, session['user_id'], bid_amount))
            db.commit()
            flash("Bid placed successfully!")
        except mysql.connector.Error as err:
            db.rollback()
            flash(f"Error placing bid: {err.msg}")
            
    cursor.execute("""
        SELECT a.*, i.title, i.description, u.full_name as seller_name
        FROM Auctions a
        JOIN Items i ON a.item_id = i.item_id
        JOIN Users u ON i.seller_id = u.user_id
        WHERE a.auction_id = %s
    """, (auction_id,))
    auction_details = cursor.fetchone()
    
    # Fetch bids
    cursor.execute("""
        SELECT b.*, u.full_name 
        FROM Bids b 
        JOIN Users u ON b.bidder_id = u.user_id 
        WHERE b.auction_id = %s 
        ORDER BY b.bid_amount DESC
    """, (auction_id,))
    bids = cursor.fetchall()
    
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
    
    cursor.execute("""
        SELECT a.*, i.title
        FROM Auctions a
        JOIN Items i ON a.item_id = i.item_id
        WHERE a.winner_id = %s OR i.seller_id = %s
    """, (session['user_id'], session['user_id']))
    user_auctions = cursor.fetchall()
    db.close()
    
    return render_template('dashboard.html', data=dashboard_data, auctions=user_auctions)

if __name__ == '__main__':
    app.run(debug=True)