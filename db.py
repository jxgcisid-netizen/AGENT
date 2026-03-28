import sqlite3
import json
import os

DB_PATH = "/data/bot.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            user_id TEXT PRIMARY KEY,
            history TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id TEXT PRIMARY KEY,
            preferred_model TEXT,
            preferred_provider TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ 数据库初始化完成")

def save_history(user_id: str, history: list):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO conversations (user_id, history, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
    ''', (user_id, json.dumps(history, ensure_ascii=False)))
    conn.commit()
    conn.close()

def load_history(user_id: str) -> list:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT history FROM conversations WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row['history']:
        return json.loads(row['history'])
    return []

def save_user_preference(user_id: str, model: str, provider: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO user_settings (user_id, preferred_model, preferred_provider, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
    ''', (user_id, model, provider))
    conn.commit()
    conn.close()

def load_user_preference(user_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT preferred_model, preferred_provider FROM user_settings WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row['preferred_model'], row['preferred_provider']
    return None, None
