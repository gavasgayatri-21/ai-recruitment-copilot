import os
import json
import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.orm import Session
 
from app.database import get_db
from app.models.candidate import Candidate
from app.models.job import JobPosting
from app.models.voice_screening import VoiceScreening
from app.models.voice_interview import VoiceInterviewSession
from app.services import interview as interview_service
 
router = APIRouter(prefix="/api/voice", tags=["Voice Screening"])
 
VOICE_DIR = os.path.join(os.getenv("UPLOAD_DIR", "uploads"), "voice")
MAX_AUDIO_SIZE_MB = 15
 
ALLOWED_MIME_TYPES = {
    "audio/webm", "audio/ogg", "audio/wav", "audio/mp3", "audio/mpeg", "audio/mp4",
}
 
 
def _validate_and_save_audio(audio: UploadFile, audio_bytes: bytes) -> tuple:
    """Shared validation + disk save for an uploaded audio clip. Returns (filename, base_mime_type)."""
    mime_type = audio.content_type or "audio/webm"
    base_mime_type = mime_type.split(";")[0].strip()
    if base_mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio type '{mime_type}'. Try recording again.",
        )
 
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
 
    return filename, base_mime_type
 
 
def _resolve_turns_for_gemini(transcript: list) -> list:
    """
    Reads audio bytes back off disk for every user turn in a stored
    transcript, so the full conversation (with real audio) can be replayed
    to Gemini for a follow-up question or final summary.
    """
    resolved = []
    for turn in transcript:
        if turn["role"] == "model":
            resolved.append({"role": "model", "text": turn["text"]})
        else:
            path = os.path.join(VOICE_DIR, turn["audio_filename"])
            with open(path, "rb") as f:
                audio_bytes = f.read()
            resolved.append({
                "role": "user",
                "audio_bytes": audio_bytes,
                "mime_type": turn["mime_type"],
            })
    return resolved
 
 
def _session_to_response(s: VoiceInterviewSession) -> dict:
    transcript = json.loads(s.transcript) if s.transcript else []
    # Don't leak raw filenames/mime types to the client -- just flag that a turn was a voice answer.
    display_transcript = [
        {"role": t["role"], "text": t.get("text", "(voice answer)")}
        for t in transcript
    ]
    return {
        "id": s.id,
        "candidate_id": s.candidate_id,
        "job_id": s.job_id,
        "status": s.status,
        "transcript": display_transcript,
        "final_assessment": s.final_assessment,
        "created_at": s.created_at,
    }
 
 
@router.post("/sessions")
def start_voice_session(
    candidate_id: int = Form(...),
    job_id: int = Form(None),
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
 
    try:
        opening_question = interview_service.start_voice_interview(job_title, candidate.name)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
 
    transcript = [{"role": "model", "text": opening_question}]
    session = VoiceInterviewSession(
        candidate_id=candidate_id,
        job_id=job_id,
        status="active",
        transcript=json.dumps(transcript),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
 
    return _session_to_response(session)
 
 
@router.post("/sessions/{session_id}/answer")
async def submit_voice_answer(
    session_id: int,
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    session = db.query(VoiceInterviewSession).filter(VoiceInterviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Voice interview session not found.")
    if session.status == "completed":
        raise HTTPException(status_code=400, detail="This interview has already ended.")
 
    candidate = db.query(Candidate).filter(Candidate.id == session.candidate_id).first()
    job_title = "the role"
    if session.job_id:
        job = db.query(JobPosting).filter(JobPosting.id == session.job_id).first()
        if job:
            job_title = job.title
 
    audio_bytes = await audio.read()
    filename, base_mime_type = _validate_and_save_audio(audio, audio_bytes)
 
    transcript = json.loads(session.transcript) if session.transcript else []
    prior_turns = _resolve_turns_for_gemini(transcript)
 
    try:
        next_question = interview_service.continue_voice_interview(
            turns=prior_turns,
            job_title=job_title,
            candidate_name=candidate.name if candidate else None,
            new_audio_bytes=audio_bytes,
            new_mime_type=base_mime_type,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
 
    transcript.append({"role": "user", "audio_filename": filename, "mime_type": base_mime_type})
    transcript.append({"role": "model", "text": next_question})
    session.transcript = json.dumps(transcript)
    db.commit()
    db.refresh(session)
 
    return _session_to_response(session)
 
 
@router.patch("/sessions/{session_id}")
def end_voice_session(session_id: int, db: Session = Depends(get_db)):
    session = db.query(VoiceInterviewSession).filter(VoiceInterviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Voice interview session not found.")
    if session.status == "completed":
        return _session_to_response(session)
 
    candidate = db.query(Candidate).filter(Candidate.id == session.candidate_id).first()
    job_title = "the role"
    if session.job_id:
        job = db.query(JobPosting).filter(JobPosting.id == session.job_id).first()
        if job:
            job_title = job.title
 
    transcript = json.loads(session.transcript) if session.transcript else []
    all_turns = _resolve_turns_for_gemini(transcript)
 
    try:
        final_assessment = interview_service.summarize_voice_interview(
            turns=all_turns,
            job_title=job_title,
            candidate_name=candidate.name if candidate else None,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
 
    session.status = "completed"
    session.final_assessment = final_assessment
    db.commit()
    db.refresh(session)
 
    return _session_to_response(session)
 
 
@router.get("/sessions/{session_id}")
def get_voice_session(session_id: int, db: Session = Depends(get_db)):
    session = db.query(VoiceInterviewSession).filter(VoiceInterviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Voice interview session not found.")
    return _session_to_response(session)
 
 
@router.post("/screen")
async def screen_candidate(
    candidate_id: int = Form(...),
    job_id: int = Form(None),
    question: str = Form(None),
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Legacy single-shot screening endpoint, kept for API completeness."""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")
 
    job_title = "the role"
    if job_id:
        job = db.query(JobPosting).filter(JobPosting.id == job_id).first()
        if job:
            job_title = job.title
 
    audio_bytes = await audio.read()
    filename, base_mime_type = _validate_and_save_audio(audio, audio_bytes)
 
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
 