import sqlite3
import json
from datetime import datetime

DB_FILE = "tbg_enterprise_ledger.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Contracts Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS escrow_contracts (
            contract_id TEXT PRIMARY KEY,
            depositor TEXT,
            beneficiary TEXT,
            trustee TEXT,
            nodal_virtual_account TEXT,
            total_amount REAL,
            current_balance REAL,
            status TEXT,
            milestones TEXT,
            created_at TEXT
        )
    ''')
    # Double-entry Journal Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS journal_entries (
            entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
            txn_ref TEXT UNIQUE,
            debit_account TEXT,
            credit_account TEXT,
            amount REAL,
            product_rail TEXT,
            status TEXT,
            timestamp TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_contract(contract_dict):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO escrow_contracts 
        (contract_id, depositor, beneficiary, trustee, nodal_virtual_account, total_amount, current_balance, status, milestones, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        contract_dict["contract_id"],
        contract_dict["depositor"],
        contract_dict["beneficiary"],
        contract_dict["trustee"],
        contract_dict["nodal_virtual_account"],
        contract_dict["total_amount"],
        contract_dict["current_balance"],
        contract_dict["status"],
        json.dumps(contract_dict["milestones"]),
        datetime.utcnow().isoformat()
    ))
    conn.commit()
    conn.close()

def record_journal(txn_ref, debit_acc, credit_acc, amount, product):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO journal_entries (txn_ref, debit_account, credit_account, amount, product_rail, status, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (txn_ref, debit_acc, credit_acc, amount, product, "SETTLED", datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

init_db()
