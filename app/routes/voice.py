import os
import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.orm import Session
 
from app.database import get_db
from app.models.candidate import Candidate
from app.models.job import JobPosting
from app.models.voice_screening import VoiceScreening
from app.services import interview as interview_service
 
router = APIRouter(prefix="/api/voice", tags=["Voice Screening"])
 
VOICE_DIR = os.path.join(os.getenv("UPLOAD_DIR", "uploads"), "voice")
MAX_AUDIO_SIZE_MB = 15
 
ALLOWED_MIME_TYPES = {
    "audio/webm", "audio/ogg", "audio/wav", "audio/mp3", "audio/mpeg", "audio/mp4",
}
 
 
@router.post("/screen")
async def screen_candidate(
    candidate_id: int = Form(...),
    job_id: int = Form(None),
    question: str = Form(None),
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")
 
    job_title = "the role"
    if job_id:
        job = db.query(JobPosting).filter(JobPosting.id == job_id).first()
        if job:
            job_title = job.title
 
    mime_type = audio.content_type or "audio/webm"
    base_mime_type = mime_type.split(";")[0].strip()
    if base_mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio type '{mime_type}'. Try recording again.",
        )
 
    audio_bytes = await audio.read()
    size_mb = len(audio_bytes) / (1024 * 1024)
    if size_mb > MAX_AUDIO_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"Recording too large ({size_mb:.1f}MB). Keep clips under {MAX_AUDIO_SIZE_MB}MB.",
        )
    if size_mb == 0:
        raise HTTPException(status_code=400, detail="No audio was recorded.")
 
    os.makedirs(VOICE_DIR, exist_ok=True)
    ext = base_mime_type.split("/")[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    with open(os.path.join(VOICE_DIR, filename), "wb") as f:
        f.write(audio_bytes)
 
    try:
        assessment = interview_service.assess_voice_screening(
            audio_bytes=audio_bytes,
            mime_type=base_mime_type,
            job_title=job_title,
            candidate_name=candidate.name,
            question=question,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
 
    screening = VoiceScreening(
        candidate_id=candidate_id,
        job_id=job_id,
        audio_filename=filename,
        assessment_text=assessment,
    )
    db.add(screening)
    db.commit()
    db.refresh(screening)
 
    return {
        "id": screening.id,
        "candidate_id": candidate_id,
        "job_id": job_id,
        "assessment": assessment,
        "created_at": screening.created_at,
    }
 
 
@router.get("/screen/{candidate_id}")
def get_screenings(candidate_id: int, db: Session = Depends(get_db)):
    screenings = (
        db.query(VoiceScreening)
        .filter(VoiceScreening.candidate_id == candidate_id)
        .order_by(VoiceScreening.id.desc())
        .all()
    )
    return [
        {
            "id": s.id,
            "job_id": s.job_id,
            "assessment": s.assessment_text,
            "created_at": s.created_at,
        }
        for s in screenings
    ]
