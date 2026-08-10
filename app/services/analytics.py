from datetime import datetime, timezone
from sqlalchemy.orm import Session
 
from app.models.candidate import Candidate
from app.models.interview import InterviewSession
 
INTERVIEWED_STATUSES = {"active", "completed", "offered", "hired"}
OFFERED_STATUSES = {"offered", "hired"}
 
 
def _latest_session_by_candidate(db: Session) -> dict:
    sessions = db.query(InterviewSession).order_by(InterviewSession.id.asc()).all()
    latest = {}
    for s in sessions:
        latest[s.candidate_id] = s
    return latest
 
 
def get_overview(db: Session) -> dict:
    candidates = db.query(Candidate).all()
    latest_by_candidate = _latest_session_by_candidate(db)
 
    total_candidates = len(candidates)
    total_sessions = db.query(InterviewSession).count()
 
    screened = sum(1 for c in candidates if c.id in latest_by_candidate)
    interviewed = sum(
        1 for c in candidates
        if c.id in latest_by_candidate and latest_by_candidate[c.id].status in INTERVIEWED_STATUSES
    )
    offered = sum(
        1 for c in candidates
        if c.id in latest_by_candidate and latest_by_candidate[c.id].status in OFFERED_STATUSES
    )
    hired = sum(
        1 for c in candidates
        if c.id in latest_by_candidate and latest_by_candidate[c.id].status == "hired"
    )
 
    hiring_success_rate = round((hired / interviewed) * 100, 1) if interviewed else None
 
    hire_days = []
    for c in candidates:
        s = latest_by_candidate.get(c.id)
        if s and s.status == "hired" and c.created_at and s.updated_at:
            created = c.created_at
            updated = s.updated_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            hire_days.append((updated - created).days)
    avg_time_to_hire = round(sum(hire_days) / len(hire_days), 1) if hire_days else None
 
    return {
        "stats": {
            "total_candidates": total_candidates,
            "interviews_scheduled": total_sessions,
            "hiring_success_rate_percent": hiring_success_rate,
            "avg_time_to_hire_days": avg_time_to_hire,
        },
        "pipeline": [
            {"stage": "Applied", "count": total_candidates},
            {"stage": "Screened", "count": screened},
            {"stage": "Interviewed", "count": interviewed},
            {"stage": "Offered", "count": offered},
            {"stage": "Hired", "count": hired},
        ],
    }
