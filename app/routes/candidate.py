import io
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import pandas as pd
 
from app.database import get_db
from app.models.candidate import Candidate
from app.models.interview import InterviewSession
from app.models.voice_interview import VoiceInterviewSession
from app.models.voice_screening import VoiceScreening
from app.schemas.candidate import CandidateResponse
from app.utils.helpers import json_to_list
 
router = APIRouter(prefix="/api/candidates", tags=["Candidates"])
 
 
def _to_response(candidate: Candidate) -> CandidateResponse:
    return CandidateResponse(
        id=candidate.id,
        name=candidate.name,
        email=candidate.email,
        phone=candidate.phone,
        skills=json_to_list(candidate.skills),
        education=json_to_list(candidate.education),
        experience=json_to_list(candidate.experience),
        total_experience_years=candidate.total_experience_years,
        source_filename=candidate.source_filename,
        extraction_accuracy=candidate.extraction_accuracy,
        created_at=candidate.created_at,
    )
 
 
@router.get("/", response_model=list[CandidateResponse])
def list_candidates(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """Returns a paginated list of all parsed candidate profiles."""
    candidates = db.query(Candidate).offset(skip).limit(limit).all()
    return [_to_response(c) for c in candidates]
 
 
@router.get("/{candidate_id}", response_model=CandidateResponse)
def get_candidate(candidate_id: int, db: Session = Depends(get_db)):
    """Returns a single candidate profile by ID."""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    return _to_response(candidate)
 
 
@router.delete("/{candidate_id}")
def delete_candidate(candidate_id: int, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")
 
    # Interview sessions, voice interview sessions, and voice screenings all
    # reference this candidate's id via a foreign key. Deleting the candidate
    # without clearing these first fails with a database integrity error, so
    # we clean up the candidate's related records before removing the profile.
    db.query(InterviewSession).filter(InterviewSession.candidate_id == candidate_id).delete()
    db.query(VoiceInterviewSession).filter(VoiceInterviewSession.candidate_id == candidate_id).delete()
    db.query(VoiceScreening).filter(VoiceScreening.candidate_id == candidate_id).delete()
 
    db.delete(candidate)
    db.commit()
    return {"message": f"Candidate {candidate_id} deleted."}
 
 
@router.get("/export/csv")
def export_candidates_csv(db: Session = Depends(get_db)):
    """
    Exports all candidate profiles as a CSV using pandas -- handy for
    sharing a quick shortlist with recruiters/mentors.
    """
    candidates = db.query(Candidate).all()
    if not candidates:
        raise HTTPException(status_code=404, detail="No candidates to export.")
 
    rows = []
    for c in candidates:
        rows.append({
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "phone": c.phone,
            "skills": ", ".join(json_to_list(c.skills)),
            "total_experience_years": c.total_experience_years,
            "extraction_accuracy": c.extraction_accuracy,
            "source_filename": c.source_filename,
            "created_at": c.created_at,
        })
 
    df = pd.DataFrame(rows)
    stream = io.StringIO()
    df.to_csv(stream, index=False)
    stream.seek(0)
 
    return StreamingResponse(
        iter([stream.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=candidates_export.csv"},
    )