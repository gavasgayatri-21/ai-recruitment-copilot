from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
 
from app.database import get_db
from app.services import analytics as analytics_service
 
router = APIRouter(prefix="/api/analytics", tags=["Analytics"])
 
 
@router.get("/overview")
def get_overview(db: Session = Depends(get_db)):
    return analytics_service.get_overview(db)