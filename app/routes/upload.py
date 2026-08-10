import os
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
 
from app.database import get_db
from app.models.candidate import Candidate
from app.schemas.candidate import UploadResponse, CandidateResponse
from app.services.parser import extract_text, UnsupportedFileTypeError
from app.services.extractor import extract_profile
from app.utils.helpers import (
    is_allowed_file,
    generate_unique_filename,
    save_upload_file,
    save_extracted_json,
    list_to_json,
)
 
router = APIRouter(prefix="/api/upload", tags=["Upload"])
 
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
EXTRACTED_DIR = os.getenv("EXTRACTED_DIR", "extracted_data")
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))
MAX_BULK_FILES = 25  # sane cap so a huge batch can't tie up a single request for too long
 
 
def _process_resume(filename: str, file_bytes: bytes, db: Session) -> CandidateResponse:
    """
    Shared per-file pipeline: validate -> save raw file -> extract text ->
    extract structured profile -> persist -> return the created profile.
    Raises HTTPException on any failure (caught per-file by the bulk
    endpoint, propagated directly by the single-file endpoint).
    """
    if not is_allowed_file(filename):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Please upload a .pdf or .docx file.",
        )
 
    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > MAX_UPLOAD_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({size_mb:.1f}MB). Max allowed is {MAX_UPLOAD_SIZE_MB}MB.",
        )
 
    unique_name = generate_unique_filename(filename)
    file_path = save_upload_file(UPLOAD_DIR, unique_name, file_bytes)
 
    try:
        raw_text = extract_text(file_path)
    except UnsupportedFileTypeError as e:
        raise HTTPException(status_code=400, detail=str(e))
 
    if not raw_text.strip():
        raise HTTPException(
            status_code=422,
            detail="Could not extract any text from this file. It may be a scanned/image-based document.",
        )
 
    profile = extract_profile(raw_text)
 
    candidate = Candidate(
        name=profile.get("name"),
        email=profile.get("email"),
        phone=profile.get("phone"),
        skills=list_to_json(profile.get("skills", [])),
        education=list_to_json(profile.get("education", [])),
        experience=list_to_json(profile.get("experience", [])),
        total_experience_years=profile.get("total_experience_years"),
        raw_text=raw_text,
        source_filename=filename,
        extraction_accuracy=profile.get("extraction_accuracy"),
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
 
    save_extracted_json(EXTRACTED_DIR, candidate.id, profile)
 
    return CandidateResponse(
        id=candidate.id,
        name=candidate.name,
        email=candidate.email,
        phone=candidate.phone,
        skills=profile.get("skills", []),
        education=profile.get("education", []),
        experience=profile.get("experience", []),
        total_experience_years=candidate.total_experience_years,
        source_filename=candidate.source_filename,
        extraction_accuracy=candidate.extraction_accuracy,
        created_at=candidate.created_at,
    )
 
 
@router.post("/resume", response_model=UploadResponse)
async def upload_resume(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Accepts a single PDF or DOCX resume, parses it, and saves the profile."""
    file_bytes = await file.read()
    candidate = _process_resume(file.filename, file_bytes, db)
    return UploadResponse(
        message="Resume uploaded and parsed successfully.",
        candidate=candidate,
    )
 
 
@router.post("/resumes")
async def upload_resumes_bulk(files: list[UploadFile] = File(...), db: Session = Depends(get_db)):
    """
    Accepts multiple resumes in one request and parses each independently.
    A failure on one file (bad format, unreadable, too large) doesn't stop
    the rest of the batch -- every file gets its own success/error result.
    """
    if len(files) > MAX_BULK_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files at once ({len(files)}). Upload at most {MAX_BULK_FILES} per batch.",
        )
 
    results = []
    succeeded = 0
    failed = 0
 
    for f in files:
        try:
            file_bytes = await f.read()
            candidate = _process_resume(f.filename, file_bytes, db)
            results.append({
                "filename": f.filename,
                "status": "success",
                "candidate": candidate,
            })
            succeeded += 1
        except HTTPException as e:
            # Roll back any partial DB state from this specific file before
            # continuing to the next one in the batch.
            db.rollback()
            results.append({
                "filename": f.filename,
                "status": "error",
                "detail": e.detail,
            })
            failed += 1
        except Exception as e:
            db.rollback()
            results.append({
                "filename": f.filename,
                "status": "error",
                "detail": f"Unexpected error: {e}",
            })
            failed += 1
 
    return {
        "message": f"Processed {len(files)} file(s): {succeeded} succeeded, {failed} failed.",
        "total": len(files),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }
