from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
 
from app.database import Base
 
 
class VoiceScreening(Base):
    __tablename__ = "voice_screenings"
 
    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("job_postings.id"), nullable=True)
 
    audio_filename = Column(String(255), nullable=True)
    assessment_text = Column(Text, nullable=True)
 
    created_at = Column(DateTime(timezone=True), server_default=func.now())