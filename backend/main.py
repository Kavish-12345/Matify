"""FastAPI entry point. Endpoints are added in Step 2 (engine) and Step 4 (chat)."""
from fastapi import FastAPI

app = FastAPI(title="Matify: AI-based material selection")


@app.get("/api/health")
def health():
    return {"status": "ok"}
