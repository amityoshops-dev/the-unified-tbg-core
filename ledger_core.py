import uuid
from decimal import Decimal
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Numeric, DateTime, Integer, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class Account(Base):
    __tablename__ = "tbg_accounts"
    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    account_type = Column(String(32), nullable=False) # ASSET, LIABILITY, EQUITY
    balance = Column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)

class JournalEntry(Base):
    __tablename__ = "tbg_journal_entries"
    id = Column(String(64), primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    reference_utr = Column(String(64), unique=True, nullable=False)
    narration = Column(String(255), nullable=False)

class LedgerPosting(Base):
    __tablename__ = "tbg_ledger_postings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_id = Column(String(64), ForeignKey("tbg_journal_entries.id"))
    account_id = Column(String(64), ForeignKey("tbg_accounts.id"))
    debit = Column(Numeric(18, 2), default=Decimal("0.00"))
    credit = Column(Numeric(18, 2), default=Decimal("0.00"))

class DoubleEntryEngine:
    def __init__(self, db_session):
        self.session = db_session

    def post_balanced_transaction(self, utr: str, narration: str, debit_acc_id: str, credit_acc_id: str, amount: Decimal):
        if amount <= Decimal("0.00"):
            raise ValueError("Transaction amount must be strictly positive.")

        entry_id = str(uuid.uuid4())
        journal_entry = JournalEntry(
            id=entry_id,
            reference_utr=utr,
            narration=narration,
            timestamp=datetime.utcnow()
        )
        self.session.add(journal_entry)

        # Debit Posting
        dr_post = LedgerPosting(entry_id=entry_id, account_id=debit_acc_id, debit=amount, credit=Decimal("0.00"))
        # Credit Posting
        cr_post = LedgerPosting(entry_id=entry_id, account_id=credit_acc_id, debit=Decimal("0.00"), credit=amount)
        self.session.add_all([dr_post, cr_post])

        # Adjust Balances
        debit_acc = self.session.query(Account).filter_by(id=debit_acc_id).with_for_update().one()
        credit_acc = self.session.query(Account).filter_by(id=credit_acc_id).with_for_update().one()

        if debit_acc.account_type == "ASSET":
            debit_acc.balance += amount
        else:
            debit_acc.balance -= amount

        if credit_acc.account_type == "LIABILITY":
            credit_acc.balance += amount
        else:
            credit_acc.balance -= amount

        self.session.commit()
        return entry_id