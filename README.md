# RecallProof (MVP)

RecallProof is an experimental memory reliability testing service for AI agents. This repository contains a simple Python FastAPI backend that integrates with HydraDB to store memories and run a recall/evaluation flow.

**Repository**: https://github.com/Nitish-1303/Recallops-Nitish

## Architecture

- Frontend: `frontend/` — Next.js app scaffold (not implemented yet).
- Backend: `backend/` — FastAPI service that uses `hydra_db` SDK to ingest memories and query recall.
- Data: HydraDB tenant/collection configured via environment variables.

Flow:

- `POST /api/memories` — ingest a memory into HydraDB (memory bucket).
- `POST /api/recall` — query memories and return ranked chunks with evidence and latency.
- `POST /api/evaluate` — ingest both an old and a new memory, then run recall against the query and return pass/fail, evidence and latency.

The backend uses HydraDB's `context.ingest` (type=memory) to store memories and `query` with `mode=memory` to retrieve them.

## Quickstart (backend)

1. Create a Python venv and install requirements:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Create a local `.env` (do NOT commit):

```text
HYDRA_DB_API_KEY=your_key
HYDRADB_DATABASE=recallproof
```

3. Run the API:

```powershell
uvicorn backend.main:app --reload --port 8000
```

4. Endpoints:

- `GET /api/health` — health check
- `POST /api/memories` — body: `{ "subject": "role preference", "content": "Nitish prefers onsite engineering roles." }`
- `POST /api/recall` — body: `{ "query": "Which roles should be recommended?" }`
- `POST /api/evaluate` — body: `{ "old_memory": {...}, "new_memory": {...}, "query": "Which roles should be recommended?" }`

## Example evaluate request

```json
POST /api/evaluate
{
  "old_memory": {"subject":"role","content":"Nitish prefers onsite engineering roles.","timestamp":1680000000},
  "new_memory": {"subject":"role","content":"Nitish now prefers global remote engineering roles.","timestamp":1680001000},
  "query": "Which roles should be recommended?"
}
```

Expected: the response should recommend global remote roles, include evidence (top retrieved chunk), latency in ms, and `passed: true` when the new memory contains the remote preference.

## Notes

- Do not commit real API keys. `.env` is listed in `.gitignore`.
- The current MVP uses a simple heuristic to determine pass/fail. This can be replaced with a more robust comparator.

If you'd like, I can now run a commit that adds these changes and push everything to the GitHub repository, and then run a quick local smoke test (if you provide the HYDRA DB API key locally).
