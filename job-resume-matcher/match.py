#!/usr/bin/env python3
"""
Job-Resume Matcher — standalone CLI script
Usage:
  python match.py --resume resume.pdf --jd job.txt
  python match.py --resume resume.txt --jd job.txt
  python match.py  # interactive mode (paste text)
"""

import sys
import json
import argparse
import textwrap
from pathlib import Path


def get_api_key():
    import os
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / "server" / ".env")
    load_dotenv()  # also check cwd
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        print("ERROR: ANTHROPIC_API_KEY not set.")
        print("Either:")
        print("  export ANTHROPIC_API_KEY=sk-ant-...")
        print("  or create a .env file in this directory with ANTHROPIC_API_KEY=...")
        sys.exit(1)
    return key


def extract_pdf(path: str) -> str:
    try:
        import pypdf
    except ImportError:
        print("ERROR: pypdf not installed. Run: pip install pypdf")
        sys.exit(1)
    import io
    reader = pypdf.PdfReader(path)
    pages = [p.extract_text() or "" for p in reader.pages]
    text = "\n\n".join(p for p in pages if p.strip())
    if not text.strip():
        print("ERROR: Could not extract text from PDF (may be image-based).")
        sys.exit(1)
    return text


def read_resume(path: str) -> str:
    p = Path(path)
    if not p.exists():
        print(f"ERROR: File not found: {path}")
        sys.exit(1)
    if p.suffix.lower() == ".pdf":
        return extract_pdf(path)
    return p.read_text(encoding="utf-8")


def paste_multiline(prompt: str) -> str:
    print(prompt)
    print("(Paste your text, then press Enter + Ctrl-D on Mac/Linux, or Enter + Ctrl-Z + Enter on Windows)")
    lines = []
    try:
        for line in sys.stdin:
            lines.append(line)
    except EOFError:
        pass
    return "".join(lines).strip()


PROMPT = """You are an expert technical recruiter and career coach. Analyze the job description and resume below.

## Job Description
{jd}

## Resume
{resume}

Respond in JSON only — no prose outside the JSON:
{{
  "overall_score": <integer 0-100>,
  "summary": "<2-3 sentence overall assessment>",
  "recommendation": "strong-match|good-match|partial-match|poor-match",
  "matched_skills": [
    {{"skill": "...", "evidence": "..."}}
  ],
  "missing_skills": [
    {{"skill": "...", "importance": "critical|important|nice-to-have", "suggestion": "..."}}
  ],
  "strengths": ["..."],
  "concerns": ["..."],
  "interview_questions": [
    {{"question": "...", "category": "technical|behavioral|situational|gap-probe", "rationale": "..."}}
  ]
}}"""


def analyze(resume_text: str, jd_text: str, api_key: str) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    print("\nAnalyzing with Claude AI", end="", flush=True)

    accumulated = ""
    with client.messages.stream(
        model="claude-opus-4-8",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": PROMPT.format(jd=jd_text.strip(), resume=resume_text.strip())}],
    ) as stream:
        for text in stream.text_stream:
            accumulated += text
            print(".", end="", flush=True)

    print(" done.\n")

    # Strip markdown code fences if present
    clean = accumulated.strip()
    if clean.startswith("```"):
        clean = clean.split("```", 2)[1]
        if clean.startswith("json"):
            clean = clean[4:]
        clean = clean.rsplit("```", 1)[0]

    return json.loads(clean.strip())


# ── pretty printers ──────────────────────────────────────────────────────────

COLORS = {
    "green":  "\033[92m",
    "yellow": "\033[93m",
    "red":    "\033[91m",
    "blue":   "\033[94m",
    "cyan":   "\033[96m",
    "bold":   "\033[1m",
    "reset":  "\033[0m",
}

def c(color, text):
    return f"{COLORS[color]}{text}{COLORS['reset']}"

def hr(char="─", width=70):
    print(char * width)

def score_color(score):
    if score >= 70: return "green"
    if score >= 50: return "yellow"
    return "red"

def importance_color(imp):
    return {"critical": "red", "important": "yellow", "nice-to-have": "cyan"}.get(imp, "cyan")

def recommendation_label(rec):
    labels = {
        "strong-match": c("green", "STRONG MATCH"),
        "good-match":   c("blue",  "GOOD MATCH"),
        "partial-match":c("yellow","PARTIAL MATCH"),
        "poor-match":   c("red",   "POOR MATCH"),
    }
    return labels.get(rec, rec.upper())

def wrap(text, width=66, indent="  "):
    return textwrap.fill(text, width=width, initial_indent=indent, subsequent_indent=indent)

def print_report(r: dict):
    score = r.get("overall_score", 0)
    hr("═")
    print(c("bold", "  JOB-RESUME MATCH REPORT"))
    hr("═")

    print(f"\n  Score:          {c(score_color(score), f'{score}/100')}")
    print(f"  Recommendation: {recommendation_label(r.get('recommendation',''))}")
    print(f"\n  Summary:")
    print(wrap(r.get("summary", ""), indent="    "))

    # Matched skills
    matched = r.get("matched_skills", [])
    if matched:
        print(f"\n{c('bold','  MATCHED SKILLS')}  ({len(matched)})")
        hr()
        for m in matched:
            print(f"  {c('green', '✓')} {c('bold', m['skill'])}")
            print(f"      {m.get('evidence','')}")

    # Missing skills
    missing = r.get("missing_skills", [])
    if missing:
        print(f"\n{c('bold','  MISSING SKILLS')}  ({len(missing)})")
        hr()
        for m in missing:
            imp = m.get("importance", "")
            print(f"  {c('red','✗')} {c('bold', m['skill'])}  [{c(importance_color(imp), imp)}]")
            print(wrap(m.get("suggestion",""), indent="      "))

    # Strengths
    strengths = r.get("strengths", [])
    if strengths:
        print(f"\n{c('bold','  STRENGTHS')}")
        hr()
        for s in strengths:
            print(wrap(f"+ {s}", indent="  "))

    # Concerns
    concerns = r.get("concerns", [])
    if concerns:
        print(f"\n{c('bold','  CONCERNS')}")
        hr()
        for con in concerns:
            print(wrap(f"! {con}", indent="  "))

    # Interview questions
    questions = r.get("interview_questions", [])
    if questions:
        print(f"\n{c('bold','  INTERVIEW QUESTIONS')}  ({len(questions)})")
        hr()
        for i, q in enumerate(questions, 1):
            cat = q.get("category","")
            cat_color = {"technical":"blue","behavioral":"cyan","situational":"cyan","gap-probe":"yellow"}.get(cat,"cyan")
            print(f"\n  {c('bold',f'Q{i}.')} [{c(cat_color, cat)}]")
            print(wrap(q.get("question",""), indent="      "))
            print(wrap(f"Why: {q.get('rationale','')}", indent="      "))

    hr("═")


def main():
    parser = argparse.ArgumentParser(description="Match a resume against a job description using Claude AI.")
    parser.add_argument("--resume", help="Path to resume file (.pdf or .txt)")
    parser.add_argument("--jd",     help="Path to job description file (.txt)")
    parser.add_argument("--output", help="Save JSON result to this file (optional)")
    args = parser.parse_args()

    api_key = get_api_key()

    # Resume
    if args.resume:
        print(f"Reading resume: {args.resume}")
        resume_text = read_resume(args.resume)
    else:
        resume_text = paste_multiline("\nPaste your RESUME text below:")

    # JD
    if args.jd:
        print(f"Reading job description: {args.jd}")
        jd_text = Path(args.jd).read_text(encoding="utf-8")
    else:
        jd_text = paste_multiline("\nPaste the JOB DESCRIPTION below:")

    result = analyze(resume_text, jd_text, api_key)

    print_report(result)

    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2))
        print(f"\n  JSON saved to: {args.output}")


if __name__ == "__main__":
    main()
