---
title: HEIC to JPG Converter
emoji: 🖼️
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
---

# HEIC → JPG Converter

Upload HEIC/HEIF files and convert them to JPG — all client-side upload, server-side conversion.

## Stack

- **Backend:** FastAPI (Python)
- **Frontend:** HTML + Tailwind CSS (CDN) + vanilla JS
- **Conversion:** Pillow + pillow-heif
- **Hosting:** Hugging Face Spaces (Docker SDK)

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Serves the web UI |
| POST | `/api/convert` | Upload HEIC files + quality, returns session ID |
| GET | `/api/download/{session_id}/{filename}` | Download individual JPG |
| GET | `/api/download/{session_id}/zip` | Download all as ZIP |
| GET | `/api/history` | Get conversion history |
| POST | `/api/history/undo` | Undo last session |
| POST | `/api/history/clear` | Clear history |

## Development

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 7860
```

## Auto-deploy

Push to `main` → GitHub Action syncs to `huggingface.co/spaces/noorj29/heic-jpg`.
