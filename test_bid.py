import mysql.connector

try:
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="shashi",
        database="auction_db"
    )
    cursor = db.cursor()
    cursor.execute("SELECT current_price FROM Auctions WHERE auction_id = 1")
    current_price = cursor.fetchone()[0]
    print(f"Current price is: {current_price}")
    
    new_bid = current_price + 100
    print(f"Attempting to bid: {new_bid}")
    
    cursor.callproc('sp_PlaceBid', (1, 1, new_bid))
    db.commit()
    print("Bid placed successfully.")
except Exception as e:
    print(f"Error: {e}")
finally:
    if 'db' in locals():
        db.close()
