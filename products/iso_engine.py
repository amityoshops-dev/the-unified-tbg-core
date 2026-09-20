import uuid
from datetime import datetime

class ISO20022Engine:
    @staticmethod
    def generate_pain001_xml(msg_id: str, debtor_iban: str, bene_iban: str, amount: float, currency: str = "INR") -> str:
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03">
  <CstmrCdtTrfInitn>
    <GrpHdr>
      <MsgId>{msg_id}</MsgId>
      <CreDtTm>{timestamp}</CreDtTm>
      <NbOfTxs>1</NbOfTxs>
      <InitgPty><Nm>TBG_CORE_ENGINE</Nm></InitgPty>
    </GrpHdr>
    <PmtInf>
      <PmtInfId>PMT_{uuid.uuid4().hex[:8].upper()}</PmtInfId>
      <PmtMtd>TRF</PmtMtd>
      <Dbtr><Nm>TBG_NODAL_POOL</Nm></Dbtr>
      <DbtrAcct><Id><Othr><Id>{debtor_iban}</Id></Othr></Id></DbtrAcct>
      <CdtTrfTxInf>
        <Amt><InstdAmt Ccy="{currency}">{amount:.2f}</InstdAmt></Amt>
        <CdtrAcct><Id><Othr><Id>{bene_iban}</Id></Othr></Id></CdtrAcct>
      </CdtTrfTxInf>
    </PmtInf>
  </CstmrCdtTrfInitn>
</Document>"""
        return xml
