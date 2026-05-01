-- Online Auction Marketplace Database Schema

-- Create Database
CREATE DATABASE IF NOT EXISTS auction_db;
USE auction_db;

-- 1. Users Table
CREATE TABLE Users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    phone_number VARCHAR(20),
    address TEXT,
    role ENUM('Buyer', 'Seller', 'Admin') DEFAULT 'Buyer',
    rating DECIMAL(3,2) DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- 2. Categories Table
CREATE TABLE Categories (
    category_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    parent_category_id INT,
    description TEXT,
    FOREIGN KEY (parent_category_id) REFERENCES Categories(category_id)
);

-- 3. Items Table
CREATE TABLE Items (
    item_id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    seller_id INT,
    category_id INT,
    images JSON,
    FOREIGN KEY (seller_id) REFERENCES Users(user_id),
    FOREIGN KEY (category_id) REFERENCES Categories(category_id)
);

-- 4. Auctions Table
CREATE TABLE Auctions (
    auction_id INT AUTO_INCREMENT PRIMARY KEY,
    item_id INT,
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,
    start_price DECIMAL(10,2) NOT NULL,
    reserve_price DECIMAL(10,2),
    status ENUM('PENDING', 'ACTIVE', 'EXTENDED', 'COMPLETED', 'CANCELLED', 'UNSOLD') DEFAULT 'PENDING',
    current_price DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    winner_id INT,
    FOREIGN KEY (item_id) REFERENCES Items(item_id),
    FOREIGN KEY (winner_id) REFERENCES Users(user_id)
);

-- 5. Bids Table
CREATE TABLE Bids (
    bid_id INT AUTO_INCREMENT PRIMARY KEY,
    auction_id INT,
    bidder_id INT,
    bid_amount DECIMAL(10,2) NOT NULL,
    bid_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_auto_bid BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (auction_id) REFERENCES Auctions(auction_id),
    FOREIGN KEY (bidder_id) REFERENCES Users(user_id)
);

-- 6. Payments Table
CREATE TABLE Payments (
    payment_id INT AUTO_INCREMENT PRIMARY KEY,
    auction_id INT,
    payer_id INT,
    amount DECIMAL(10,2) NOT NULL,
    method VARCHAR(50),
    status ENUM('PENDING', 'COMPLETED', 'FAILED', 'ESCROW') DEFAULT 'PENDING',
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (auction_id) REFERENCES Auctions(auction_id),
    FOREIGN KEY (payer_id) REFERENCES Users(user_id)
);

-- 7. Notifications Table
CREATE TABLE Notifications (
    notif_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    type VARCHAR(50),
    message TEXT,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES Users(user_id)
);

-- 8. Watchlist Table
CREATE TABLE Watchlist (
    watch_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    auction_id INT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES Users(user_id),
    FOREIGN KEY (auction_id) REFERENCES Auctions(auction_id)
);

-- 9. AuditLog Table
CREATE TABLE AuditLog (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    table_name VARCHAR(50),
    operation VARCHAR(10),
    old_value TEXT,
    new_value TEXT,
    changed_by INT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================
-- Stored Procedures, Functions, and Triggers
-- ==========================================

-- Function: fn_GetCurrentBid
DELIMITER //
CREATE FUNCTION fn_GetCurrentBid(p_auction_id INT) RETURNS DECIMAL(10,2)
DETERMINISTIC
BEGIN
    DECLARE v_max_bid DECIMAL(10,2);
    SELECT MAX(bid_amount) INTO v_max_bid FROM Bids WHERE auction_id = p_auction_id;
    RETURN IFNULL(v_max_bid, 0);
END //
DELIMITER ;

-- Stored Procedure: sp_PlaceBid
DELIMITER //
CREATE PROCEDURE sp_PlaceBid(
    IN p_auction_id INT,
    IN p_bidder_id INT,
    IN p_bid_amount DECIMAL(10,2)
)
BEGIN
    DECLARE v_current_price DECIMAL(10,2);
    DECLARE v_status VARCHAR(20);
    DECLARE v_end_time DATETIME;
    
    -- Start Transaction
    START TRANSACTION;
    
    -- Check auction status and current price (with row lock)
    SELECT current_price, status, end_time INTO v_current_price, v_status, v_end_time
    FROM Auctions WHERE auction_id = p_auction_id FOR UPDATE;
    
    IF v_status NOT IN ('ACTIVE', 'EXTENDED') THEN
        ROLLBACK;
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Auction is not active';
    END IF;
    
    IF p_bid_amount <= v_current_price THEN
        ROLLBACK;
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Bid amount must be greater than current price';
    END IF;
    
    IF NOW() > v_end_time THEN
        ROLLBACK;
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Auction has ended';
    END IF;
    
    -- Insert bid
    INSERT INTO Bids (auction_id, bidder_id, bid_amount) VALUES (p_auction_id, p_bidder_id, p_bid_amount);
    
    -- Update auction current price
    UPDATE Auctions SET current_price = p_bid_amount WHERE auction_id = p_auction_id;
    
    COMMIT;
END //
DELIMITER ;

-- Stored Procedure: sp_FinalizeAuction
DELIMITER //
CREATE PROCEDURE sp_FinalizeAuction(
    IN p_auction_id INT
)
BEGIN
    DECLARE v_max_bid DECIMAL(10,2);
    DECLARE v_winner_id INT;
    DECLARE v_reserve_price DECIMAL(10,2);
    
    -- Lock row
    SELECT reserve_price INTO v_reserve_price FROM Auctions WHERE auction_id = p_auction_id FOR UPDATE;
    
    SELECT MAX(bid_amount) INTO v_max_bid FROM Bids WHERE auction_id = p_auction_id;
    
    IF v_max_bid IS NULL OR (v_reserve_price IS NOT NULL AND v_max_bid < v_reserve_price) THEN
        -- Unsold
        UPDATE Auctions SET status = 'UNSOLD' WHERE auction_id = p_auction_id;
    ELSE
        -- Completed, find winner
        SELECT bidder_id INTO v_winner_id FROM Bids WHERE auction_id = p_auction_id AND bid_amount = v_max_bid LIMIT 1;
        UPDATE Auctions SET status = 'COMPLETED', winner_id = v_winner_id WHERE auction_id = p_auction_id;
        
        -- Insert pending payment
        INSERT INTO Payments (auction_id, payer_id, amount, status) VALUES (p_auction_id, v_winner_id, v_max_bid, 'PENDING');
    END IF;
END //
DELIMITER ;

-- Trigger: trg_AuctionExtend
DELIMITER //
CREATE TRIGGER trg_AuctionExtend
AFTER INSERT ON Bids
FOR EACH ROW
BEGIN
    DECLARE v_end_time DATETIME;
    SELECT end_time INTO v_end_time FROM Auctions WHERE auction_id = NEW.auction_id;
    
    -- If bid is within last 5 minutes, extend by 5 minutes
    IF TIMESTAMPDIFF(MINUTE, NOW(), v_end_time) <= 5 THEN
        UPDATE Auctions SET end_time = DATE_ADD(end_time, INTERVAL 5 MINUTE), status = 'EXTENDED'
        WHERE auction_id = NEW.auction_id;
    END IF;
END //
DELIMITER ;

-- Views
CREATE VIEW vw_ActiveAuctions AS
SELECT a.auction_id, i.title, i.description, a.start_price, a.current_price, a.end_time, u.full_name AS seller_name
FROM Auctions a
JOIN Items i ON a.item_id = i.item_id
JOIN Users u ON i.seller_id = u.user_id
WHERE a.status IN ('ACTIVE', 'EXTENDED');

CREATE VIEW vw_UserDashboard AS
SELECT u.user_id, COUNT(b.bid_id) as total_bids, COUNT(w.watch_id) as watchlist_count
FROM Users u
LEFT JOIN Bids b ON u.user_id = b.bidder_id
LEFT JOIN Watchlist w ON u.user_id = w.user_id
GROUP BY u.user_id;
