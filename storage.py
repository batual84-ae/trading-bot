import sqlite3
from pathlib import Path
from typing import Any, Dict, List

DB_PATH = Path(__file__).resolve().parent / 'bot.db'


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS positions (
            symbol TEXT PRIMARY KEY,
            entry_price REAL NOT NULL,
            quantity REAL NOT NULL,
            take_profit REAL NOT NULL,
            stop_loss REAL NOT NULL,
            mode TEXT NOT NULL,
            opened_at TEXT NOT NULL
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            price REAL NOT NULL,
            quantity REAL NOT NULL,
            notional REAL NOT NULL,
            pnl REAL,
            mode TEXT NOT NULL,
            created_at TEXT NOT NULL,
            note TEXT
        )
    ''')
    conn.commit()
    conn.close()


def add_log(created_at: str, level: str, message: str):
    conn = get_conn()
    conn.execute(
        'INSERT INTO logs(created_at, level, message) VALUES (?, ?, ?)',
        (created_at, level, message),
    )
    conn.commit()
    conn.close()


def get_logs(limit: int = 200) -> List[Dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        'SELECT created_at, level, message FROM logs ORDER BY id DESC LIMIT ?',
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def upsert_position(symbol: str, entry_price: float, quantity: float, take_profit: float, stop_loss: float, mode: str, opened_at: str):
    conn = get_conn()
    conn.execute(
        '''
        INSERT INTO positions(symbol, entry_price, quantity, take_profit, stop_loss, mode, opened_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol) DO UPDATE SET
            entry_price=excluded.entry_price,
            quantity=excluded.quantity,
            take_profit=excluded.take_profit,
            stop_loss=excluded.stop_loss,
            mode=excluded.mode,
            opened_at=excluded.opened_at
        ''',
        (symbol, entry_price, quantity, take_profit, stop_loss, mode, opened_at),
    )
    conn.commit()
    conn.close()


def delete_position(symbol: str):
    conn = get_conn()
    conn.execute('DELETE FROM positions WHERE symbol=?', (symbol,))
    conn.commit()
    conn.close()


def get_positions() -> List[Dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute('SELECT * FROM positions ORDER BY symbol').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_trade(symbol: str, side: str, price: float, quantity: float, notional: float, pnl: float | None, mode: str, created_at: str, note: str = ''):
    conn = get_conn()
    conn.execute(
        '''
        INSERT INTO trades(symbol, side, price, quantity, notional, pnl, mode, created_at, note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (symbol, side, price, quantity, notional, pnl, mode, created_at, note),
    )
    conn.commit()
    conn.close()


def get_trades(limit: int = 200) -> List[Dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        'SELECT * FROM trades ORDER BY id DESC LIMIT ?',
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
