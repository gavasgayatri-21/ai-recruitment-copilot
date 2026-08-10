# AI Recruitment & Talent Management Copilot

**Milestone 1 (Weeks 1-2): Resume Parsing & Candidate Profiling**

This milestone implements:
- Resume upload (PDF/DOCX), including bulk upload of multiple resumes at once
- Text extraction (pdfplumber, PyPDF2, python-docx)
- NLP-based candidate field extraction (spaCy + regex): name, email, phone,
  skills, education, experience, total years of experience
- Structured candidate profiles saved to MySQL
- CSV export of all candidates (pandas)

**Milestone 2 (Weeks 3-4): Matching & Skill Analysis**

This milestone adds:
- Job posting management (title, required skills + level, minimum experience)
- Candidate-job matching engine with a 0-100 hiring/match score
- Skill-gap analysis per candidate per job, with a templated recommendation
- Dashboard sidebar with Job Postings and Matching & Skill Analysis views

**Milestone 3 (Weeks 5-6): Interview Assistance & ATS Integration**

This milestone adds:
- AI-generated, role-specific interview questions (Google Gemini API)
- Live AI-powered interview simulation (a real conversational back-and-forth,
  not scripted) via Gemini, with an "End Interview" action
- A mock ATS status view per candidate (not scheduled / scheduled / in
  progress / completed), driven by interview session state
- Dashboard sidebar "Interview Assistant" tab with question generator, live
  chat simulation, and the ATS overview

**Milestone 4 (Weeks 7-8): Dashboard & Deployment**

This milestone adds:
- Recruitment analytics dashboard with real, computed KPIs (total candidates,
  interviews scheduled, hiring success rate, average time to hire)
- A recruitment pipeline funnel (Applied -> Screened -> Interviewed ->
  Offered -> Hired), computed from actual candidate and interview-session data
- Voice-based screening: real microphone recording in the browser, analyzed
  directly by Gemini's audio understanding (no separate speech-to-text step)
- Dark mode, with the preference saved across sessions

## Project Structure

```
AI-Recruitment-Copilot/
|
|-- app/
|   |-- main.py                 # FastAPI entry point
|   |-- routes/
|   |   |-- upload.py           # POST /api/upload/resume and /resumes (bulk)
|   |   |-- candidate.py        # GET/DELETE candidates, CSV export
|   |   |-- job.py              # Job posting CRUD
|   |   |-- match.py            # Candidate-job matching + skill gap
|   |   |-- interview.py        # Question generation, live simulation, mock ATS
|   |   |-- analytics.py        # Dashboard KPI + pipeline funnel
|   |   `-- voice.py            # Voice screening (audio upload + Gemini analysis)
|   |-- services/
|   |   |-- parser.py           # File -> raw text
|   |   |-- extractor.py        # Raw text -> structured fields
|   |   |-- matching.py         # Match scoring + skill-gap analysis
|   |   |-- interview.py        # Gemini-backed question gen, simulation, voice assessment
|   |   `-- analytics.py        # KPI + funnel computation
|   |-- models/
|   |   |-- candidate.py        # SQLAlchemy ORM model
|   |   |-- job.py              # SQLAlchemy ORM model for job postings
|   |   |-- interview.py        # SQLAlchemy ORM model for interview sessions
|   |   `-- voice_screening.py  # SQLAlchemy ORM model for voice screenings
|   |-- schemas/
|   |   |-- candidate.py        # Pydantic request/response models
|   |   |-- job.py              # Pydantic request/response models for jobs
|   |   `-- interview.py        # Pydantic request/response models for interviews
|   |-- static/
|   |   `-- index.html          # Frontend dashboard (served at /dashboard)
|   |-- database.py             # MySQL connection (SQLAlchemy + pymysql)
|   `-- utils/
|       `-- helpers.py          # File validation, JSON helpers
|
|-- uploads/                    # Uploaded resumes land here
|-- extracted_data/             # JSON copy of each parsed profile
|-- requirements.txt
|-- .env.example
`-- README.md
```

## Setup

### 1. Create a virtual environment and install dependencies

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Note: use Python 3.12, not 3.13 -- some of spaCy's dependencies (e.g. `blis`)
don't yet have prebuilt wheels for 3.13 and will fail to compile from source.

### 2. Download the spaCy language model (used for name detection)

```bash
python -m spacy download en_core_web_sm
```

### 3. Set up MySQL

Create a database:

```sql
CREATE DATABASE recruitment_copilot;
```

Copy `.env.example` to `.env` and fill in your MySQL credentials:

```bash
cp .env.example .env
```

```
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=recruitment_copilot
```

Tables are auto-created on startup - no manual migration needed for any milestone.

### 4. Get a free Gemini API key (used for Milestones 3-4)

Go to **https://aistudio.google.com/apikey**, sign in with a Google account,
and click "Create API key" - it's free, no credit card required.

Add it to your `.env`:

```
GEMINI_API_KEY=your_gemini_api_key
```

(Skip this if you only need Milestones 1-2 - the interview assistant and
voice screening will just show a clear error if this key is missing,
everything else works fine without it.)

### 5. Run the server

```bash
uvicorn app.main:app --reload
```

Visit **http://localhost:8000/docs** for interactive Swagger API docs, or
**http://localhost:8000/dashboard/** for the visual dashboard.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/upload/resume` | Upload a single resume (PDF/DOCX), parse it, save profile |
| POST | `/api/upload/resumes` | Upload multiple resumes at once; each parsed independently |
| GET | `/api/candidates/` | List all candidate profiles (paginated) |
| GET | `/api/candidates/{id}` | Get one candidate profile |
| DELETE | `/api/candidates/{id}` | Delete a candidate profile |
| GET | `/api/candidates/export/csv` | Export all candidates as CSV |
| POST | `/api/jobs/` | Create a job posting (title, required skills + level, min. experience) |
| GET | `/api/jobs/` | List all job postings |
| GET | `/api/jobs/{id}` | Get one job posting |
| DELETE | `/api/jobs/{id}` | Delete a job posting |
| GET | `/api/match/{job_id}` | Ranked candidate matches for a job (match %) |
| GET | `/api/match/{job_id}/candidate/{candidate_id}` | Per-skill gap breakdown + recommendation |
| POST | `/api/interview/questions` | Generate role-specific interview questions (Gemini) |
| POST | `/api/interview/sessions` | Start a live AI interview simulation for a candidate |
| POST | `/api/interview/sessions/{id}/message` | Candidate sends a reply; returns the AI's next turn |
| GET | `/api/interview/sessions/{id}` | Full transcript of one interview session |
| PATCH | `/api/interview/sessions/{id}` | Mock ATS action: mark scheduled/active/completed/offered/hired |
| GET | `/api/interview/ats` | Mock ATS overview - every candidate's interview status + match % |
| GET | `/api/analytics/overview` | Dashboard KPI stats + recruitment pipeline funnel |
| POST | `/api/voice/screen` | Upload a voice-screening recording, get a Gemini-generated assessment |
| GET | `/api/voice/screen/{candidate_id}` | Past voice screenings for a candidate |

## Frontend Dashboard

A single static file (`app/static/index.html`) - plain HTML/CSS/JavaScript,
no framework or build step required. FastAPI serves it via a `StaticFiles`
mount, so it runs off the same server as the API.

**Access it at:** http://localhost:8000/dashboard/

Five tabs in the sidebar:

- **Dashboard** (Milestone 4) - KPI stat cards, recruitment pipeline funnel
  chart, and the voice screening module (real mic recording + Gemini analysis)
- **Resume Upload** (Milestone 1) - upload panel (single or bulk), live
  parsing stats, and the candidate table with CSV export
- **Job Postings** (Milestone 2) - create/list/delete job postings with
  required skills and minimum experience
- **Matching & Skill Analysis** (Milestone 2) - pick a job to see candidates
  ranked by match %, click a candidate to see a per-skill gap breakdown
- **Interview Assistant** (Milestone 3) - generate interview questions, run
  a live AI interview simulation via chat, and see the mock ATS status

A dark mode toggle lives at the bottom of the sidebar; the choice is saved
in the browser and persists across visits.

## Matching & Skill Gap Analysis (`app/services/matching.py`)

**Match score** - a 0-100 score combining 70% skill coverage (with partial
credit for a skill held below the required level) and 30% experience fit
(capped at 100% once the job's minimum years is met).

**Important caveat**: resumes only state whether a candidate has a skill,
not their proficiency at it. A candidate's level per skill is therefore
*approximated* from their overall `total_experience_years` (3+ yrs ->
Advanced, 1-3 -> Intermediate, <1 -> Basic), applied uniformly across all
their skills - a heuristic, not a measured skill level.

## Interview Assistant (`app/services/interview.py`)

Milestones 1-2 are fully rule-based and run offline. Milestone 3 makes real
calls to the **Gemini API** for question generation and a genuinely
conversational live interview simulation - the full transcript is stored as
JSON per session and replayed to Gemini on every turn along with a system
instruction describing the interviewer persona and role context.

If `GEMINI_API_KEY` isn't set, these endpoints return a clear `503` error
rather than a generic 500 or a cryptic SDK traceback.

## Mock ATS (`app/models/interview.py`, `GET /api/interview/ats`)

Rather than integrating a real Applicant Tracking System (which would need
an account and API credentials this project doesn't have), a candidate's
ATS status is *derived* from their most recent `InterviewSession` row:
no session -> "not scheduled"; session status active/completed/offered/hired
maps to the corresponding label. This also avoids a manual database
migration on the existing `candidates` table, since it's a brand new table
picked up automatically by `init_db()`.

## Dashboard Analytics & Pipeline (`app/services/analytics.py`)

All numbers are computed from real data, not hardcoded. The pipeline reuses
`InterviewSession.status`, extended beyond Milestone 3's scheduled/active/
completed to also allow "offered" and "hired" (still just a string column,
no migration needed):

- Applied = every uploaded candidate
- Screened = candidate has at least one interview session
- Interviewed = session status is active/completed/offered/hired
- Offered = session status is offered/hired
- Hired = session status is hired

Moving a candidate to "offered" or "hired" happens via the existing
`PATCH /api/interview/sessions/{id}` endpoint from Milestone 3.

## Voice Screening (`app/routes/voice.py`)

Real browser microphone recording via the `MediaRecorder` API, visualized
with a live waveform (Web Audio API `AnalyserNode`). The recorded clip is
sent directly to Gemini as inline audio data - no separate speech-to-text
service - along with a prompt asking for a short preliminary assessment of
communication skills and technical knowledge relevant to the role.

Note: browsers only allow microphone access on secure contexts.
`localhost` is fine for development; a production deployment would need HTTPS.

## Getting Started (for teammates)

Each person runs their own local copy - `.env` and `venv/` are intentionally
excluded from Git, so nobody shares database passwords or API keys.

```bash
git clone https://github.com/manasvimalhotra/ai-recruitment-copilot.git
cd ai-recruitment-copilot
```

Then follow the Setup steps above.

## Contributing changes (fork workflow)

This project uses a fork-based workflow - each contributor works in their
own fork rather than pushing directly to this repo.

**One-time setup, per contributor:**

1. Click **Fork** on the GitHub repo page to create your own copy.
2. Clone *your fork* (not this repo):
   ```bash
   git clone https://github.com/YOUR_USERNAME/ai-recruitment-copilot.git
   cd ai-recruitment-copilot
   ```
3. Add this repo as `upstream`:
   ```bash
   git remote add upstream https://github.com/manasvimalhotra/ai-recruitment-copilot.git
   ```
4. Follow the Setup steps above to get it running locally.

**Making a change:**

```bash
git checkout -b feature/your-feature-name
git add .
git commit -m "Describe what you changed"
git push origin feature/your-feature-name
```

Then open a Pull Request on GitHub from your fork's branch into this repo's
`main` branch for review.

**Staying up to date with the latest changes:**

```bash
git fetch upstream
git merge upstream/main
```
