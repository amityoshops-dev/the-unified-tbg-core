import pathlib

content = pathlib.Path("app.py").read_text(encoding="utf-8")

inflow_code = """
@app.post("/api/v1/escrow/inflow-webhook", tags=["1. Digital Escrow"])
async def nodal_deposit_webhook(req: DepositSchema):
    try:
        updated = escrow_engine.deposit_inflow(req.virtual_account_no, req.amount)
        # Sync directly with SQLite
        import sqlite3
        conn = sqlite3.connect("tbg_enterprise_ledger.db")
        c = conn.cursor()
        c.execute("UPDATE escrow_contracts SET current_balance = ?, status = ? WHERE nodal_virtual_account = ?", 
                  (updated.current_balance, updated.status, req.virtual_account_no))
        conn.commit()
        conn.close()
        return {"message": "Funds locked in nodal vault", "contract": updated}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
"""

if "/api/v1/escrow/inflow-webhook" not in content:
    target = "@app.post(\"/api/v1/escrow/create\", tags=[\"1. Digital Escrow\"])"
    # Insert right before create or disburse
    content = content.replace(target, inflow_code + "\n" + target)
    pathlib.Path("app.py").write_text(content, encoding="utf-8")
    print("SUCCESS: Inflow webhook added to app.py")
else:
    print("Endpoint already exists.")
