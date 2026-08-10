from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
 
from app.database import init_db
from app.routes import upload, candidate, job, match, interview, analytics, voice
 
app = FastAPI(
    title="AI Recruitment & Talent Management Copilot",
    description="Milestone 1: Resume Parsing. Milestone 2: Matching & Skill Analysis. Milestone 3: Interview Assistance & ATS Integration. Milestone 4: Dashboard & Deployment.",
    version="0.4.0",
)
 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
 
app.include_router(upload.router)
app.include_router(candidate.router)
app.include_router(job.router)
app.include_router(match.router)
app.include_router(interview.router)
app.include_router(analytics.router)
app.include_router(voice.router)
 
app.mount("/dashboard", StaticFiles(directory="app/static", html=True), name="dashboard")
 
 
@app.on_event("startup")
def on_startup():
    init_db()
 
 
@app.get("/")
def root():
    return {
        "message": "AI Recruitment & Talent Management Copilot API is running.",
        "docs": "/docs",
    }
 
 
@app.get("/health")
def health_check():
    return {"status": "ok"}