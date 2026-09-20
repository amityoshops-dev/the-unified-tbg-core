import pathlib

content = pathlib.Path("app.py").read_text(encoding="utf-8")

# Fix: If contract not in memory, fetch directly from SQLite ledger
old_lookup = """    contract = escrow_engine.contracts.get(req.contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")"""

new_lookup = """    contract = escrow_engine.contracts.get(req.contract_id)
    if not contract:
        import sqlite3, json
        conn = sqlite3.connect("tbg_enterprise_ledger.db")
        c = conn.cursor()
        c.execute("SELECT contract_id, depositor, beneficiary, trustee, nodal_virtual_account, total_amount, current_balance, status, milestones FROM escrow_contracts WHERE contract_id = ?", (req.contract_id,))
        row = c.fetchone()
        conn.close()
        if row:
            from products.escrow_engine import EscrowContract, MilestoneItem
            m_list = [MilestoneItem(**m) for m in json.loads(row[8])]
            contract = EscrowContract(
                contract_id=row[0], depositor=row[1], beneficiary=row[2], trustee=row[3],
                nodal_virtual_account=row[4], total_amount=row[5], current_balance=row[6],
                status=row[7], milestones=m_list
            )
            escrow_engine.contracts[contract.contract_id] = contract
        else:
            raise HTTPException(status_code=404, detail="Contract not found in Memory or SQLite Ledger")"""

if old_lookup in content:
    content = content.replace(old_lookup, new_lookup)
    pathlib.Path("app.py").write_text(content, encoding="utf-8")
    print("SUCCESS: SQLite fallback lookup patched into app.py")
else:
    print("Already patched or pattern not found.")
