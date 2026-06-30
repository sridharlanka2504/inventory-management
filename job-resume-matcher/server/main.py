import os
import io
import httpx
import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import pypdf
import anthropic
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    print("WARNING: ANTHROPIC_API_KEY not set. Set it in server/.env")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

ANALYSIS_PROMPT = """You are an expert technical recruiter and career coach. Analyze the provided job description and resume, then produce a structured evaluation.

## Job Description
{job_description}

## Resume
{resume_text}

Respond in the following JSON format exactly:
{{
  "overall_score": <integer 0-100>,
  "summary": "<2-3 sentence overall assessment>",
  "matched_skills": [
    {{"skill": "<skill name>", "evidence": "<where it appears in resume>"}}
  ],
  "missing_skills": [
    {{"skill": "<skill name>", "importance": "critical|important|nice-to-have", "suggestion": "<how to address this gap>"}}
  ],
  "strengths": ["<strength 1>", "<strength 2>"],
  "concerns": ["<concern 1>", "<concern 2>"],
  "interview_questions": [
    {{
      "question": "<interview question>",
      "rationale": "<why this question matters for this role/candidate>",
      "category": "technical|behavioral|situational|gap-probe"
    }}
  ],
  "recommendation": "strong-match|good-match|partial-match|poor-match"
}}

Be specific and concrete. Interview questions should directly probe gaps or validate claimed skills."""


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(title="Job-Resume Matcher API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TextAnalysisRequest(BaseModel):
    resume_text: str
    job_description: str


class DocsAnalysisRequest(BaseModel):
    docs_url: str
    job_description: str


def extract_pdf_text(file_bytes: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(p for p in pages if p.strip())
    if not text.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from PDF. The file may be image-based.")
    return text


async def fetch_google_docs_text(url: str) -> str:
    # Convert share/view URL to plain-text export URL
    export_url = url
    if "docs.google.com/document" in url:
        if "/export" not in url:
            # Strip query params and add export=txt
            base = url.split("?")[0].rstrip("/")
            if base.endswith("/edit") or base.endswith("/view"):
                base = base.rsplit("/", 1)[0]
            export_url = f"{base}/export?format=txt"

    async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as hc:
        try:
            resp = await hc.get(export_url)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=422,
                detail=f"Could not fetch Google Doc (HTTP {e.response.status_code}). Make sure the doc is publicly accessible (Anyone with link can view)."
            )
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Failed to fetch Google Doc: {str(e)}")

    text = resp.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="Google Doc appears to be empty or inaccessible.")
    return text


def stream_analysis(resume_text: str, job_description: str):
    prompt = ANALYSIS_PROMPT.format(
        job_description=job_description.strip(),
        resume_text=resume_text.strip(),
    )

    with client.messages.stream(
        model="claude-opus-4-8",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            yield text


@app.post("/api/analyze/text")
async def analyze_text(body: TextAnalysisRequest):
    if not body.resume_text.strip():
        raise HTTPException(status_code=422, detail="Resume text is empty.")
    if not body.job_description.strip():
        raise HTTPException(status_code=422, detail="Job description is empty.")

    return StreamingResponse(
        stream_analysis(body.resume_text, body.job_description),
        media_type="text/plain",
    )


@app.post("/api/analyze/pdf")
async def analyze_pdf(
    file: UploadFile = File(...),
    job_description: str = Form(...),
):
    if not job_description.strip():
        raise HTTPException(status_code=422, detail="Job description is empty.")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Only PDF files are accepted.")

    file_bytes = await file.read()
    resume_text = extract_pdf_text(file_bytes)

    return StreamingResponse(
        stream_analysis(resume_text, job_description),
        media_type="text/plain",
    )


@app.post("/api/analyze/docs")
async def analyze_docs(body: DocsAnalysisRequest):
    if not body.docs_url.strip():
        raise HTTPException(status_code=422, detail="Google Docs URL is empty.")
    if not body.job_description.strip():
        raise HTTPException(status_code=422, detail="Job description is empty.")
    if "docs.google.com" not in body.docs_url:
        raise HTTPException(status_code=422, detail="Please provide a valid Google Docs URL.")

    resume_text = await fetch_google_docs_text(body.docs_url)

    return StreamingResponse(
        stream_analysis(resume_text, body.job_description),
        media_type="text/plain",
    )


@app.get("/api/health")
async def health():
    return {"status": "ok", "model": "claude-opus-4-8"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
