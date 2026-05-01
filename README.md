# Online Auction Marketplace

A modern, web-based Online Auction Marketplace built with a **Database-Centric Architecture**. This application facilitates real-time auction execution between buyers and sellers, ensuring data integrity, concurrency management, and transactional safety by enforcing core business rules directly at the database layer.

---

## 🏗️ Architecture: Database-Centric Design
Unlike traditional applications where business logic is handled in the backend (e.g., Python/Node.js), this project shifts the core auction mechanics into the **Database Layer**.
- **Stored Procedures:** Used for complex transactions like placing bids (`sp_PlaceBid`) and finalizing auctions (`sp_FinalizeAuction`).
- **Triggers:** Automatically enforce rules, such as extending the auction end time if a bid is placed in the last 5 minutes (`trg_AuctionExtend`).
- **Views:** Aggregate and serve clean data for the UI, such as active auctions (`vw_ActiveAuctions`) and user dashboards (`vw_UserDashboard`).

This approach guarantees full **ACID compliance**, prevents race conditions during highly concurrent bidding, and maintains a strict separation of concerns.

---

## ✨ Features
- **Role-Based Access:** Users can act as both Buyers and Sellers under a single account.
- **Auction Listings:** Sellers can list items with starting prices, optional reserve prices, and specific deadlines.
- **Real-Time Bidding Engine:** Buyers can place bids securely. The database ensures bids are strictly greater than the current price and placed before the deadline.
- **Anti-Snipe Protection:** Bids placed within the final 5 minutes automatically extend the auction by 5 minutes.
- **User Dashboard:** Track your active bids, won auctions, and items you are selling.
- **Premium UI:** A sleek, glassmorphism-inspired dark mode interface that provides a visually stunning user experience with smooth micro-animations.

---

## 🛠️ Technology Stack
- **Backend API:** Python 3, Flask Web Framework
- **Database Engine:** MySQL 8.x
- **Database Driver:** `mysql-connector-python`
- **Frontend / Client-side:** HTML5, CSS3 (Custom Glassmorphism UI), Jinja2 Templating
- **Design Pattern:** Database-Centric Architecture / MVC

---

## 🚀 Setup & Installation Instructions

### 1. Prerequisites
Ensure you have the following installed on your system:
- [Python 3.8+](https://www.python.org/downloads/)
- [MySQL Server](https://dev.mysql.com/downloads/installer/)

### 2. Install Dependencies
Open your terminal and install the required Python packages:
```bash
pip install Flask mysql-connector-python
```

### 3. Database Initialization
This project relies heavily on the database schema.
1. Open your MySQL client (e.g., MySQL Workbench, phpMyAdmin, or CLI).
2. Log in using your root credentials.
3. Import and execute the entire `database.sql` file. This will automatically create the `auction_db` database, tables, triggers, and stored procedures.

### 4. Configuration
Open `app.py` in your code editor and verify your MySQL connection credentials around line 9:
```python
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="your_mysql_password_here", # Update this to your local password
        database="auction_db"
    )
```

### 5. Run the Server
Start the Flask application:
```bash
python app.py
```
Visit **`http://127.0.0.1:5000/`** in your browser to access the marketplace.

---

## 🗂️ Project Structure
```text
/
├── app.py                # Flask application, routing, and session management
├── database.sql          # Complete DB schema, Stored Procedures, and Triggers
├── test_bid.py           # Optional utility script for testing DB connections
├── static/
│   └── style.css         # Premium dark mode & glassmorphism CSS
└── templates/            # HTML Jinja2 templates
    ├── base.html         # Main layout wrapper
    ├── index.html        # Active auctions feed
    ├── login.html        # Authentication UI
    ├── register.html     # Authentication UI
    ├── add_auction.html  # Seller listing form
    ├── auction.html      # Individual auction view and bid form
    └── dashboard.html    # User statistics and history
```

---

## 🌍 Academic Context & SDG Alignment
This project was developed for the Academic Year 2024-25, targeting specific learning outcomes (PO1, PO5, PO9) and directly aligning with the UN Sustainable Development Goals:
- **SDG 8 (Decent Work & Economic Growth):** By empowering small business owners and individual sellers to reach a wider digital market.
- **SDG 9 (Industry, Innovation & Infrastructure):** By demonstrating a resilient, scalable, database-driven technical infrastructure capable of handling high-concurrency transactions.
