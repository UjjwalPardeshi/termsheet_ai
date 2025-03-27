from sqlalchemy import Column, Integer, String, DateTime, Float
from datetime import datetime
from database import Base

class TermSheet(Base):
    __tablename__ = "termsheets"

    id = Column(Integer, primary_key=True, index=True)
    document_name = Column(String, index=True)
    document_type = Column(String)
    extracted_text = Column(String)
    ocr_confidence = Column(Float)  # Added this field
    validation_status = Column(String, default="Pending")
    created_at = Column(DateTime, default=datetime.utcnow)
