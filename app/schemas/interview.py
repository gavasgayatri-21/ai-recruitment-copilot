from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
 
 
class QuestionRequest(BaseModel):
    job_id: int
    question_type: str = "Technical Skills"
    num_questions: int = 3
 
 
class GeneratedQuestion(BaseModel):
    question: str
    category: Optional[str] = None
    estimated_time: Optional[str] = None
 
 
class StartSessionRequest(BaseModel):
    candidate_id: int
    job_id: Optional[int] = None
 
 
class SendMessageRequest(BaseModel):
    message: str
 
 
class TranscriptTurn(BaseModel):
    role: str  # "user" (candidate) | "model" (AI interviewer)
    text: str
 
 
class SessionResponse(BaseModel):
    id: int
    candidate_id: int
    job_id: Optional[int] = None
    status: str
    transcript: List[TranscriptTurn] = []
    scheduled_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
 
 
class UpdateSessionRequest(BaseModel):
    status: Optional[str] = None       # scheduled | active | completed
    scheduled_at: Optional[datetime] = None
 













