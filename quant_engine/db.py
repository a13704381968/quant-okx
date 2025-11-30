import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.getcwd(), 'quant.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create strategy_status table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS strategy_status (
        name TEXT PRIMARY KEY,
        symbol TEXT,
        leverage INTEGER,
        interval TEXT DEFAULT '1H',
        status TEXT DEFAULT 'STOPPED',
        last_heartbeat DATETIME,
        error_message TEXT
    )
    ''')

    # Add interval column if not exists (migration for existing databases)
    try:
        cursor.execute('ALTER TABLE strategy_status ADD COLUMN interval TEXT DEFAULT "1H"')
    except:
        pass  # Column already exists
    
    # Create strategy_logs table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS strategy_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        strategy_name TEXT NOT NULL,
        timestamp DATETIME NOT NULL,
        level TEXT NOT NULL,
        event_type TEXT NOT NULL,
        message TEXT NOT NULL,
        data TEXT
    )
    ''')
    
    # Create strategy_trades table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS strategy_trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        strategy_name TEXT NOT NULL,
        timestamp DATETIME NOT NULL,
        symbol TEXT NOT NULL,
        side TEXT NOT NULL,
        order_type TEXT,
        price REAL,
        quantity REAL,
        order_id TEXT,
        status TEXT,
        pnl REAL
    )
    ''')
    
    # Create strategy_metrics table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS strategy_metrics (
        strategy_name TEXT PRIMARY KEY,
        total_trades INTEGER DEFAULT 0,
        winning_trades INTEGER DEFAULT 0,
        losing_trades INTEGER DEFAULT 0,
        total_pnl REAL DEFAULT 0,
        win_rate REAL DEFAULT 0,
        last_updated DATETIME
    )
    ''')
    
    # Create market_klines table for historical data
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS market_klines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        bar TEXT NOT NULL,
        ts INTEGER NOT NULL,
        open REAL NOT NULL,
        high REAL NOT NULL,
        low REAL NOT NULL,
        close REAL NOT NULL,
        vol REAL,
        vol_ccy REAL,
        vol_ccy_quote REAL,
        UNIQUE(symbol, bar, ts)
    )
    ''')

    # Create indexes for better query performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_strategy ON strategy_logs(strategy_name, timestamp DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_strategy ON strategy_trades(strategy_name, timestamp DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_klines_symbol_bar_ts ON market_klines(symbol, bar, ts)')

    conn.commit()
    conn.close()

def reset_database():
    """
    Clear all data from the database while preserving table structures.
    Returns a dict with the number of rows deleted from each table.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    tables = ['strategy_status', 'strategy_logs', 'strategy_trades', 'strategy_metrics', 'market_klines']
    deleted_counts = {}

    try:
        for table in tables:
            # Get count before delete
            cursor.execute(f'SELECT COUNT(*) FROM {table}')
            count = cursor.fetchone()[0]

            # Delete all data
            cursor.execute(f'DELETE FROM {table}')
            deleted_counts[table] = count

        # Reset autoincrement counters
        cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('strategy_logs', 'strategy_trades', 'market_klines')")

        conn.commit()
        return {'status': 'success', 'deleted': deleted_counts}
    except Exception as e:
        conn.rollback()
        return {'status': 'error', 'msg': str(e)}
    finally:
        conn.close()

def update_strategy_status(name, status, error_message=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if error_message:
        cursor.execute('''
        UPDATE strategy_status 
        SET status = ?, error_message = ?, last_heartbeat = ?
        WHERE name = ?
        ''', (status, error_message, datetime.now(), name))
    else:
        cursor.execute('''
        UPDATE strategy_status 
        SET status = ?, last_heartbeat = ?
        WHERE name = ?
        ''', (status, datetime.now(), name))
        
    conn.commit()
    conn.close()

def get_active_strategies():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM strategy_status WHERE status = 'RUNNING'")
    strategies = cursor.fetchall()
    conn.close()
    return strategies

def get_all_strategies_status():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM strategy_status")
    rows = cursor.fetchall()
    conn.close()
    return {row['name']: dict(row) for row in rows}

# Strategy Logging Functions
def log_strategy_event(strategy_name, level, event_type, message, data=None):
    """
    Log a strategy event
    
    Args:
        strategy_name: Name of the strategy
        level: Log level (INFO, WARNING, ERROR)
        event_type: Type of event (SIGNAL, ORDER, POSITION, HEARTBEAT, ERROR, START, STOP)
        message: Log message
        data: Optional dict with additional data
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    data_json = json.dumps(data) if data else None
    
    cursor.execute('''
    INSERT INTO strategy_logs (strategy_name, timestamp, level, event_type, message, data)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (strategy_name, datetime.now(), level, event_type, message, data_json))
    
    conn.commit()
    conn.close()

def get_strategy_logs(strategy_name, limit=100, level=None):
    """Get recent logs for a strategy"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if level:
        cursor.execute('''
        SELECT * FROM strategy_logs 
        WHERE strategy_name = ? AND level = ?
        ORDER BY timestamp DESC 
        LIMIT ?
        ''', (strategy_name, level, limit))
    else:
        cursor.execute('''
        SELECT * FROM strategy_logs 
        WHERE strategy_name = ?
        ORDER BY timestamp DESC 
        LIMIT ?
        ''', (strategy_name, limit))
    
    rows = cursor.fetchall()
    conn.close()
    
    logs = []
    for row in rows:
        log = dict(row)
        if log['data']:
            log['data'] = json.loads(log['data'])
        logs.append(log)
    
    return logs

# Trade Recording Functions
def log_trade(strategy_name, symbol, side, order_type, price, quantity, order_id=None, status='PENDING', pnl=None):
    """Record a trade"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO strategy_trades (strategy_name, timestamp, symbol, side, order_type, price, quantity, order_id, status, pnl)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (strategy_name, datetime.now(), symbol, side, order_type, price, quantity, order_id, status, pnl))
    
    conn.commit()
    conn.close()

def update_trade_status(order_id, status, pnl=None):
    """Update trade status"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if pnl is not None:
        cursor.execute('''
        UPDATE strategy_trades 
        SET status = ?, pnl = ?
        WHERE order_id = ?
        ''', (status, pnl, order_id))
    else:
        cursor.execute('''
        UPDATE strategy_trades 
        SET status = ?
        WHERE order_id = ?
        ''', (status, order_id))
    
    conn.commit()
    conn.close()

def get_strategy_trades(strategy_name, limit=50):
    """Get recent trades for a strategy"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT * FROM strategy_trades 
    WHERE strategy_name = ?
    ORDER BY timestamp DESC 
    LIMIT ?
    ''', (strategy_name, limit))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

# Metrics Functions
def update_strategy_metrics(strategy_name):
    """Calculate and update strategy performance metrics"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all completed trades
    cursor.execute('''
    SELECT * FROM strategy_trades 
    WHERE strategy_name = ? AND status = 'FILLED' AND pnl IS NOT NULL
    ''', (strategy_name,))
    
    trades = cursor.fetchall()
    
    total_trades = len(trades)
    winning_trades = sum(1 for t in trades if t['pnl'] > 0)
    losing_trades = sum(1 for t in trades if t['pnl'] < 0)
    total_pnl = sum(t['pnl'] for t in trades if t['pnl'])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    # Insert or update metrics
    cursor.execute('''
    INSERT OR REPLACE INTO strategy_metrics 
    (strategy_name, total_trades, winning_trades, losing_trades, total_pnl, win_rate, last_updated)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (strategy_name, total_trades, winning_trades, losing_trades, total_pnl, win_rate, datetime.now()))
    
    conn.commit()
    conn.close()

def get_strategy_metrics(strategy_name):
    """Get performance metrics for a strategy"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT * FROM strategy_metrics 
    WHERE strategy_name = ?
    ''', (strategy_name,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    else:
        # Return default metrics if none exist
        return {
            'strategy_name': strategy_name,
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0,
            'win_rate': 0,
            'last_updated': None
        }
