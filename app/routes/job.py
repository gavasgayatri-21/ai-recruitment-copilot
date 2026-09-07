from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.job import JobPosting
from app.models.interview import InterviewSession
from app.models.voice_interview import VoiceInterviewSession
from app.models.voice_screening import VoiceScreening
from app.schemas.job import JobPostingCreate, JobPostingResponse
from app.utils.helpers import list_to_json, json_to_list

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


def _to_response(job: JobPosting) -> JobPostingResponse:
    return JobPostingResponse(
        id=job.id,
        title=job.title,
        description=job.description,
        required_skills=json_to_list(job.required_skills),
        min_experience_years=job.min_experience_years,
        created_at=job.created_at,
    )


@router.post("/", response_model=JobPostingResponse)
def create_job(payload: JobPostingCreate, db: Session = Depends(get_db)):
    """Creates a new job posting to match candidates against."""
    job = JobPosting(
        title=payload.title,
        description=payload.description,
        required_skills=list_to_json([s.model_dump() for s in payload.required_skills]),
        min_experience_years=payload.min_experience_years,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return _to_response(job)


@router.get("/", response_model=list[JobPostingResponse])
def list_jobs(db: Session = Depends(get_db)):
    """Returns all job postings, most recent first."""
    jobs = db.query(JobPosting).order_by(JobPosting.id.desc()).all()
    return [_to_response(j) for j in jobs]


@router.get("/{job_id}", response_model=JobPostingResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(JobPosting).filter(JobPosting.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job posting not found.")
    return _to_response(job)


@router.delete("/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(JobPosting).filter(JobPosting.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job posting not found.")

    # Interview/voice sessions may reference this job via a nullable foreign
    # key. Detach them (keep the candidate history, just drop the job link)
    # instead of leaving a dangling reference that would fail the delete.
    db.query(InterviewSession).filter(InterviewSession.job_id == job_id).update({"job_id": None})
    db.query(VoiceInterviewSession).filter(VoiceInterviewSession.job_id == job_id).update({"job_id": None})
    db.query(VoiceScreening).filter(VoiceScreening.job_id == job_id).update({"job_id": None})

    db.delete(job)
    db.commit()
    return {"message": f"Job posting {job_id} deleted."}