from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
 
from app.database import Base
 
 
class InterviewSession(Base):
    __tablename__ = "interview_sessions"
 
    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("job_postings.id"), nullable=True)
 
    # scheduled | active | completed
    status = Column(String(30), default="scheduled", nullable=False)
 
    # JSON-encoded list of {"role": "user"|"model", "text": "..."} turns
    transcript = Column(Text, nullable=True)
 
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
 













