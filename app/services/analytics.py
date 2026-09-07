from datetime import datetime, timezone
from sqlalchemy.orm import Session
 
from app.models.candidate import Candidate
from app.models.job import JobPosting
from app.models.interview import InterviewSession
from app.utils.helpers import json_to_list
from app.services.matching import calculate_match
 
# scheduled | active | completed | offered | hired | rejected
INTERVIEWED_STATUSES = {"active", "completed", "offered", "hired", "rejected"}
PENDING_STATUSES = {"scheduled", "active"}
TOP_MATCHES_LIMIT = 8
 
 
def _latest_session_by_candidate(db: Session) -> dict:
    sessions = db.query(InterviewSession).order_by(InterviewSession.id.asc()).all()
    latest = {}
    for s in sessions:
        latest[s.candidate_id] = s
    return latest
 
 
def _percent(count: int, total: int) -> float:
    return round((count / total) * 100, 1) if total else 0.0
 
 
def _build_top_matches(candidates: list, jobs: list, latest_by_candidate: dict) -> list:
    """
    Cross-matches every candidate against every open job posting (reusing the
    Milestone 2 matching engine) and keeps each candidate's single best-scoring
    match, so the "Top Candidate Matches" table represents a spread of
    different people rather than the same candidate's several job pairings.
    """
    best_by_candidate = {}
    for c in candidates:
        candidate_skills = json_to_list(c.skills)
        candidate_data = {"skills": candidate_skills, "total_experience_years": c.total_experience_years}
        session = latest_by_candidate.get(c.id)
        row_status = "Shortlisted" if session else "Pending"
 
        for j in jobs:
            required_skills = json_to_list(j.required_skills)
            job_data = {"required_skills": required_skills, "min_experience_years": j.min_experience_years}
            match = calculate_match(candidate_data, job_data)
 
            required_names = [r.get("skill", "") for r in required_skills]
            matched_skills = [
                s for s in candidate_skills
                if s.lower() in [r.lower() for r in required_names]
            ]
 
            row = {
                "candidate_id": c.id,
                "candidate_name": c.name or "Unknown",
                "job_position": j.title,
                "match_percent": match["match_percent"],
                "matched_skills": matched_skills[:4],
                "status": row_status,
            }
            existing = best_by_candidate.get(c.id)
            if existing is None or row["match_percent"] > existing["match_percent"]:
                best_by_candidate[c.id] = row
 
    rows = list(best_by_candidate.values())
    rows.sort(key=lambda r: r["match_percent"], reverse=True)
    return rows[:TOP_MATCHES_LIMIT]
 
 
def get_overview(db: Session) -> dict:
    candidates = db.query(Candidate).all()
    jobs = db.query(JobPosting).all()
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
        if c.id in latest_by_candidate and latest_by_candidate[c.id].status == "offered"
    )
    hired = sum(
        1 for c in candidates
        if c.id in latest_by_candidate and latest_by_candidate[c.id].status == "hired"
    )
    rejected = sum(
        1 for c in candidates
        if c.id in latest_by_candidate and latest_by_candidate[c.id].status == "rejected"
    )
    pending_interviews = sum(
        1 for c in candidates
        if c.id in latest_by_candidate and latest_by_candidate[c.id].status in PENDING_STATUSES
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
 
    interview_status_counts = {
        "scheduled": sum(1 for s in latest_by_candidate.values() if s.status == "scheduled"),
        "in_progress": sum(1 for s in latest_by_candidate.values() if s.status == "active"),
        "completed": sum(
            1 for s in latest_by_candidate.values()
            if s.status in {"completed", "offered", "hired", "rejected"}
        ),
        "pending": total_candidates - screened,
    }
 
    return {
        "stats": {
            "total_candidates": total_candidates,
            "active_job_positions": len(jobs),
            "shortlisted_candidates": screened,
            "pending_interviews": pending_interviews,
            "interviews_scheduled": total_sessions,
            "hiring_success_rate_percent": hiring_success_rate,
            "avg_time_to_hire_days": avg_time_to_hire,
        },
        "pipeline": [
            {"stage": "Applied", "count": total_candidates, "percent": 100.0 if total_candidates else 0.0},
            {"stage": "Shortlisted", "count": screened, "percent": _percent(screened, total_candidates)},
            {"stage": "Interview", "count": interviewed, "percent": _percent(interviewed, total_candidates)},
            {"stage": "Offered", "count": offered, "percent": _percent(offered, total_candidates)},
            {"stage": "Hired", "count": hired, "percent": _percent(hired, total_candidates)},
            {"stage": "Rejected", "count": rejected, "percent": _percent(rejected, total_candidates)},
        ],
        "top_matches": _build_top_matches(candidates, jobs, latest_by_candidate),
        "interview_status": interview_status_counts,
    }