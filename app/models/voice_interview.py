from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
 
from app.database import Base
 
 
class VoiceInterviewSession(Base):
    """
    A multi-turn voice interview: the AI asks a question, the candidate
    records a spoken answer, the AI asks a follow-up based on that answer,
    and so on until the session is explicitly marked completed (via the
    "End Interview" action) -- at which point a final overall assessment
    is generated from the whole conversation.
    """
    __tablename__ = "voice_interview_sessions"
 
    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("job_postings.id"), nullable=True)
 
    # active | completed
    status = Column(String(30), default="active", nullable=False)
 
    # JSON-encoded list of turns:
    #   {"role": "model", "text": "..."}                                  (AI question)
    #   {"role": "user", "audio_filename": "...", "mime_type": "..."}     (candidate's spoken answer)
    transcript = Column(Text, nullable=True)
 
    final_assessment = Column(Text, nullable=True)
 
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())