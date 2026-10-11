"""
FastAPI entry point.

Run from the project root:
    uvicorn backend.main:app --reload --port 7860
Docs: http://localhost:7860/docs
"""
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.engine.options import options_payload
from backend.engine.recommend import load_engine, recommend

app = FastAPI(title="Matify: AI-based material selection", version="0.2")
app.add_middleware(  # React dev server (Vite) runs on another port
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RecommendRequest(BaseModel):
    part_name: Optional[str] = Field(None, examples=["Gear shaft"])
    function: list[str] = Field(default_factory=lambda: ["not_sure"], examples=[["rotating_or_gear"]])
    loading: str = Field("not_sure", examples=["cyclic"])
    environment: str = Field("not_sure", examples=["dry_indoor"])
    manufacturing: str = Field("not_sure", examples=["machining"])
    weight_priority: str = Field("not_sure", examples=["not_important"])
    cost_priority: str = Field("not_sure", examples=["important"])
    volume_cm3: Optional[float] = Field(None, examples=[120])
    min_limits: dict[str, float] = Field(default_factory=dict, examples=[{"Sy": 400}])
    include: list[str] = Field(default_factory=list, examples=[[]])
    avoid: list[str] = Field(default_factory=list, examples=[[]])
    price_overrides: dict[str, float] = Field(default_factory=dict, examples=[{}])
    top_n: int = Field(10, ge=1, le=50)


@app.on_event("startup")
def _warm_up():
    load_engine()  # load model, data and predictions once


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/options")
def get_options():
    return options_payload(load_engine()["prices"]["categories"])


@app.get("/api/prices")
def get_prices():
    return load_engine()["prices"]


@app.post("/api/recommend")
def post_recommend(req: RecommendRequest):
    try:
        return recommend(req.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
