from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.rag_service import (
    ask,
    ALLOWED_REPOSITORIES
)


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="ArchLens API",
    description=(
        "AI-powered software architecture "
        "and knowledge explorer"
    ),
    version="1.0.0"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# REQUEST MODEL
# ============================================================

class QuestionRequest(BaseModel):

    question: str

    repository: str


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "project": "ArchLens",
        "status": "running",
        "service": "repository-aware RAG API"
    }


# ============================================================
# LIST AVAILABLE REPOSITORIES
# ============================================================

@app.get("/repositories")
def repositories():

    return {
        "repositories": sorted(
            ALLOWED_REPOSITORIES
        )
    }


# ============================================================
# ASK ARCHLENS
# ============================================================

@app.post("/ask")
def ask_question(
    request: QuestionRequest
):

    try:

        result = ask(
            request.question,
            request.repository
        )

        return result

    except ValueError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
