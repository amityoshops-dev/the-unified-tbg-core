import uuid
from decimal import Decimal
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Numeric, DateTime, Integer, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class TBGAccount(Base):
    __tablename__ = "tbg_accounts"
    account_number = Column(String(32), primary_key=True)
    title = Column(String(128), nullable=False)
    account_type = Column(String(16), nullable=False)  # ASSET, LIABILITY, EQUITY
    balance = Column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)

class TBGJournalEntry(Base):
    __tablename__ = "tbg_journal_entries"
    entry_id = Column(String(64), primary_key=True)
    reference_utr = Column(String(64), unique=True, nullable=False, index=True)
    narration = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class TBGLedgerPosting(Base):
    __tablename__ = "tbg_ledger_postings"
    posting_id = Column(Integer, primary_key=True, autoincrement=True)
    entry_id = Column(String(64), ForeignKey("tbg_journal_entries.entry_id"), nullable=False)
    account_number = Column(String(32), ForeignKey("tbg_accounts.account_number"), nullable=False)
    debit_amount = Column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    credit_amount = Column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)

class DoubleEntryLedgerService:
    def __init__(self, db_session):
        self.session = db_session

    def post_balanced_transaction(self, utr: str, narration: str, dr_account: str, cr_account: str, amount: Decimal) -> str:
        if amount <= Decimal("0.00"):
            raise ValueError("ERR_LEDGER_AMOUNT_MUST_BE_POSITIVE")

        entry_id = f"JRN_{uuid.uuid4().hex[:12].upper()}"
        journal_record = TBGJournalEntry(
            entry_id=entry_id,
            reference_utr=utr,
            narration=narration,
            created_at=datetime.utcnow()
        )
        self.session.add(journal_record)

        # Debit Posting
        dr_post = TBGLedgerPosting(entry_id=entry_id, account_number=dr_account, debit_amount=amount, credit_amount=Decimal("0.00"))
        # Credit Posting
        cr_post = TBGLedgerPosting(entry_id=entry_id, account_number=cr_account, debit_amount=Decimal("0.00"), credit_amount=amount)
        self.session.add_all([dr_post, cr_post])

        # Pessimistic Locking on Accounts
        account_dr = self.session.query(TBGAccount).filter_by(account_number=dr_account).with_for_update().one()
        account_cr = self.session.query(TBGAccount).filter_by(account_number=cr_account).with_for_update().one()

        # Balance Updates based on Accounting Normal Balances
        if account_dr.account_type == "ASSET":
            account_dr.balance += amount
        else:
            account_dr.balance -= amount

        if account_cr.account_type == "LIABILITY":
            account_cr.balance += amount
        else:
            account_cr.balance -= amount

        self.session.commit()
        return entry_id