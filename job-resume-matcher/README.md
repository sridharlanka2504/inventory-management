# Job-Resume Matcher

Compares a job description against a resume and produces a detailed match analysis with interview questions, powered by Claude AI.

## Resume input formats
- PDF upload
- Paste plain text
- Google Docs URL (must be set to "Anyone with link can view")

## Quick Start

### Backend
```bash
cd server
cp .env.example .env        # add your ANTHROPIC_API_KEY
uv sync
uv run python main.py       # runs on port 8002
```

### Frontend
```bash
cd client
npm install
npm run dev                 # runs on port 5173
```

Open http://localhost:5173
