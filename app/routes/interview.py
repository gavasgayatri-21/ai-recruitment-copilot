import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
 
from app.database import get_db
from app.models.candidate import Candidate
from app.models.job import JobPosting
from app.models.interview import InterviewSession
from app.schemas.interview import (
    QuestionRequest, StartSessionRequest, SendMessageRequest,
    SessionResponse, UpdateSessionRequest,
)
from app.services import interview as interview_service
from app.services import matching as matching_service
from app.utils.helpers import json_to_list
 
router = APIRouter(prefix="/api/interview", tags=["Interview Assistant"])
 
 
def _session_to_response(s: InterviewSession) -> SessionResponse:
    return SessionResponse(
        id=s.id,
        candidate_id=s.candidate_id,
        job_id=s.job_id,
        status=s.status,
        transcript=json_to_list(s.transcript) or [],
        scheduled_at=s.scheduled_at,
        created_at=s.created_at,
    )
 
 
@router.post("/questions")
def generate_questions(payload: QuestionRequest, db: Session = Depends(get_db)):
    """Generates role-specific interview questions for a given job posting."""
    job = db.query(JobPosting).filter(JobPosting.id == payload.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job posting not found.")
 
    try:
        questions = interview_service.generate_questions(
            job_title=job.title,
            required_skills=json_to_list(job.required_skills),
            question_type=payload.question_type,
            num_questions=payload.num_questions,
        )
    except RuntimeError as e:
        # Missing/invalid API key -- surface a clear message instead of a 500.
        raise HTTPException(status_code=503, detail=str(e))
 
    return {"job": job.title, "question_type": payload.question_type, "questions": questions}
 
 
@router.post("/sessions", response_model=SessionResponse)
def start_session(payload: StartSessionRequest, db: Session = Depends(get_db)):
    """Starts a new live AI interview simulation for a candidate (+ optional job context)."""
    candidate = db.query(Candidate).filter(Candidate.id == payload.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")
 
    job_title = "the role"
    if payload.job_id:
        job = db.query(JobPosting).filter(JobPosting.id == payload.job_id).first()
        if job:
            job_title = job.title
 
    try:
        opening_message = interview_service.simulate_interview_turn(
            transcript=[], job_title=job_title, candidate_name=candidate.name,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
 
    transcript = [{"role": "model", "text": opening_message}]
    session = InterviewSession(
        candidate_id=payload.candidate_id,
        job_id=payload.job_id,
        status="active",
        transcript=json.dumps(transcript),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _session_to_response(session)
 
 
@router.post("/sessions/{session_id}/message", response_model=SessionResponse)
def send_message(session_id: int, payload: SendMessageRequest, db: Session = Depends(get_db)):
    """Candidate sends a reply; returns the updated transcript including the AI's next turn."""
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found.")
    if session.status == "completed":
        raise HTTPException(status_code=400, detail="This interview session has already ended.")
 
    candidate = db.query(Candidate).filter(Candidate.id == session.candidate_id).first()
    job_title = "the role"
    if session.job_id:
        job = db.query(JobPosting).filter(JobPosting.id == session.job_id).first()
        if job:
            job_title = job.title
 
    transcript = json_to_list(session.transcript) or []
 
    try:
        ai_reply = interview_service.simulate_interview_turn(
            transcript=transcript,
            job_title=job_title,
            candidate_name=candidate.name if candidate else None,
            candidate_message=payload.message,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
 
    transcript.append({"role": "user", "text": payload.message})
    transcript.append({"role": "model", "text": ai_reply})
    session.transcript = json.dumps(transcript)
    db.commit()
    db.refresh(session)
    return _session_to_response(session)
 
 
@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: int, db: Session = Depends(get_db)):
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found.")
    return _session_to_response(session)
 
 
@router.patch("/sessions/{session_id}", response_model=SessionResponse)
def update_session(session_id: int, payload: UpdateSessionRequest, db: Session = Depends(get_db)):
    """Mock ATS action: mark a session as scheduled (with a time) or completed."""
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found.")
 
    if payload.status:
        session.status = payload.status
    if payload.scheduled_at:
        session.scheduled_at = payload.scheduled_at
 
    db.commit()
    db.refresh(session)
    return _session_to_response(session)
 
 
@router.get("/ats")
def ats_overview(db: Session = Depends(get_db)):
    """
    Mock ATS view: every candidate with their most recent interview
    session status, plus their match % against that session's job (reusing
    Milestone 2's matching engine), for the "ATS Integration" panel.
    """
    candidates = db.query(Candidate).all()
    results = []
    for c in candidates:
        latest = (
            db.query(InterviewSession)
            .filter(InterviewSession.candidate_id == c.id)
            .order_by(InterviewSession.id.desc())
            .first()
        )
 
        match_percent = None
        job_title = None
        if latest and latest.job_id:
            job = db.query(JobPosting).filter(JobPosting.id == latest.job_id).first()
            if job:
                job_title = job.title
                candidate_data = {
                    "skills": json_to_list(c.skills),
                    "total_experience_years": c.total_experience_years,
                }
                job_data = {
                    "required_skills": json_to_list(job.required_skills),
                    "min_experience_years": job.min_experience_years,
                }
                match_percent = matching_service.calculate_match(candidate_data, job_data)["match_percent"]
 
        results.append({
            "candidate_id": c.id,
            "name": c.name,
            "status": latest.status if latest else "not_scheduled",
            "scheduled_at": latest.scheduled_at if latest else None,
            "session_id": latest.id if latest else None,
            "job_title": job_title,
            "match_percent": match_percent,
        })
    return {"candidates": results}