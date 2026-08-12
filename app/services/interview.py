import os
import json
from typing import Optional
 
from google import genai
from google.genai import types
 
MODEL = "gemini-3.5-flash"
 
 
def _client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set in .env. Get a free key at "
            "https://aistudio.google.com/apikey and add it to .env."
        )
    return genai.Client(api_key=api_key)
 
 
def _skills_to_str(required_skills: list) -> str:
    if not required_skills:
        return "general role requirements"
    names = [s.get("skill", s) if isinstance(s, dict) else s for s in required_skills]
    return ", ".join(names)
 
 
def generate_questions(
    job_title: str,
    required_skills: list,
    question_type: str = "Technical Skills",
    num_questions: int = 3,
) -> list:
    client = _client()
    skills_str = _skills_to_str(required_skills)
 
    prompt = f"""You are an expert technical interviewer. Generate {num_questions} \
{question_type} interview questions for a "{job_title}" role.
Relevant skills for this role: {skills_str}.
 
Return ONLY a JSON array (no markdown code fences, no extra commentary) where \
each item has exactly these keys:
- "question": the interview question text
- "category": a short 2-4 word tag, e.g. "Technical - Scenario-based" or "Behavioral - Communication"
- "estimated_time": a short string like "3-5 min response"
"""
    response = client.models.generate_content(model=MODEL, contents=prompt)
    text = (response.text or "").strip()
 
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
 
    try:
        questions = json.loads(text)
        if isinstance(questions, list):
            return questions
    except json.JSONDecodeError:
        pass
 
    return [{"question": text, "category": question_type, "estimated_time": "3-5 min response"}]
 
 
def simulate_interview_turn(
    transcript: list,
    job_title: str,
    candidate_name: Optional[str],
    candidate_message: Optional[str] = None,
) -> str:
    client = _client()
    who = candidate_name or "the candidate"
 
    system_instruction = (
        f"You are an AI interviewer conducting a professional job interview for "
        f"the role of '{job_title}' with a candidate named {who}. Ask one "
        f"thoughtful question at a time, follow up naturally based on their "
        f"answers, and keep responses concise (2-4 sentences). Stay focused on "
        f"skills and experience relevant to the role. Be warm but professional."
    )
 
    contents = [
        types.Content(role=turn["role"], parts=[types.Part(text=turn["text"])])
        for turn in transcript
    ]
 
    if candidate_message is not None:
        contents.append(types.Content(role="user", parts=[types.Part(text=candidate_message)]))
 
    if not contents:
        contents.append(types.Content(
            role="user",
            parts=[types.Part(text="Please begin the interview with a brief warm greeting and your first question.")],
        ))
 
    response = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(system_instruction=system_instruction),
    )
    return (response.text or "").strip()
 
 
def assess_voice_screening(
    audio_bytes: bytes,
    mime_type: str,
    job_title: str,
    candidate_name: Optional[str],
    question: Optional[str] = None,
) -> str:
    """
    Milestone 4: sends a candidate's recorded voice-screening audio directly
    to Gemini (audio understanding -- no separate speech-to-text step needed)
    and asks for a short preliminary assessment. If the specific question
    the candidate was asked is known, it's included so Gemini can judge how
    well the answer actually addresses it, not just general communication.
    """
    client = _client()
    who = candidate_name or "the candidate"
 
    if question:
        prompt = (
            f"You are reviewing a voice screening recording for {who}, who is being "
            f"considered for the role of '{job_title}'. They were asked the following "
            f"question: \"{question}\"\n\n"
            f"Listen to their spoken answer and write a short preliminary assessment "
            f"(2-4 sentences) covering how well they addressed the question, their "
            f"communication skills, and, if audible, their technical knowledge relevant "
            f"to the role. End with a one-line recommendation "
            f"(e.g. 'Recommended for technical interview round.')."
        )
    else:
        prompt = (
            f"You are reviewing a voice screening recording for {who}, who is being "
            f"considered for the role of '{job_title}'. Listen to the audio and write "
            f"a short preliminary assessment (2-4 sentences) covering their communication "
            f"skills and, if audible, their technical knowledge relevant to the role. "
            f"End with a one-line recommendation (e.g. 'Recommended for technical interview round.')."
        )
 
    response = client.models.generate_content(
        model=MODEL,
        contents=[
            prompt,
            types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
        ],
    )
    return (response.text or "").strip()
 
 
_VOICE_INTERVIEWER_PERSONA = (
    "You are an AI interviewer conducting a live VOICE screening interview for "
    "the role of '{job_title}' with a candidate named {who}. You will hear the "
    "candidate's actual spoken answers as audio. After each answer, ask ONE "
    "natural follow-up or cross-question that digs into something specific they "
    "just said -- don't just move to a generic next topic. Keep your questions "
    "concise (1-3 sentences), warm but professional, and focused on skills and "
    "experience relevant to the role."
)
 
 
def start_voice_interview(job_title: str, candidate_name: Optional[str]) -> str:
    """Generates the opening question for a new multi-turn voice interview."""
    client = _client()
    who = candidate_name or "the candidate"
 
    response = client.models.generate_content(
        model=MODEL,
        contents=[types.Content(
            role="user",
            parts=[types.Part(text="Please begin the voice screening with a brief warm greeting and your first question.")],
        )],
        config=types.GenerateContentConfig(
            system_instruction=_VOICE_INTERVIEWER_PERSONA.format(job_title=job_title, who=who)
        ),
    )
    return (response.text or "").strip()
 
 
def _turns_to_contents(turns: list) -> list:
    """
    Converts resolved turns into Gemini Content objects.
    turns: [{"role": "model", "text": "..."}, {"role": "user", "audio_bytes": b"...", "mime_type": "..."}]
    """
    contents = []
    for turn in turns:
        if turn["role"] == "model":
            contents.append(types.Content(role="model", parts=[types.Part(text=turn["text"])]))
        else:
            contents.append(types.Content(
                role="user",
                parts=[types.Part.from_bytes(data=turn["audio_bytes"], mime_type=turn["mime_type"])],
            ))
    return contents
 
 
def continue_voice_interview(
    turns: list,
    job_title: str,
    candidate_name: Optional[str],
    new_audio_bytes: bytes,
    new_mime_type: str,
) -> str:
    """
    Advances the voice interview by one turn: hears the candidate's latest
    spoken answer (plus the full prior audio history, so Gemini has real
    context) and returns a natural follow-up/cross-question as text.
    """
    client = _client()
    who = candidate_name or "the candidate"
 
    contents = _turns_to_contents(turns)
    contents.append(types.Content(
        role="user",
        parts=[types.Part.from_bytes(data=new_audio_bytes, mime_type=new_mime_type)],
    ))
 
    response = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=_VOICE_INTERVIEWER_PERSONA.format(job_title=job_title, who=who)
        ),
    )
    return (response.text or "").strip()
 
 
def summarize_voice_interview(
    turns: list,
    job_title: str,
    candidate_name: Optional[str],
) -> str:
    """
    Called when the candidate/recruiter clicks "End Interview": listens back
    through the whole conversation (all questions + all spoken answers) and
    produces one overall preliminary assessment.
    """
    client = _client()
    who = candidate_name or "the candidate"
 
    contents = _turns_to_contents(turns)
    contents.append(types.Content(
        role="user",
        parts=[types.Part(text=(
            "The voice screening has ended. Based on the entire conversation above, "
            "write a short overall preliminary assessment (3-5 sentences) covering "
            "communication skills and, where audible, technical knowledge relevant "
            "to the role, referencing specific things they said. End with a one-line "
            "recommendation (e.g. 'Recommended for technical interview round.')."
        ))],
    ))
 
    response = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=_VOICE_INTERVIEWER_PERSONA.format(job_title=job_title, who=who)
        ),
    )
    return (response.text or "").strip()
 