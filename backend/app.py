from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from backend.rag_service import ask


app = FastAPI(
    title="ArchLens API",
    description="AI-powered software architecture and knowledge explorer",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------
# Request model
# ---------------------------------------------------------

class QuestionRequest(BaseModel):
    question: str
    repository: str


# ---------------------------------------------------------
# Root endpoint
# ---------------------------------------------------------

@app.get("/")
def root():
    return {
        "project": "ArchLens",
        "status": "running",
        "service": "repository-aware RAG API"
    }


# ---------------------------------------------------------
# Repository list
# ---------------------------------------------------------

@app.get("/repositories")
def get_repositories():
    repositories = []

    for file in BASE_DIR.glob("architecture_graph_*.json"):
        name = file.stem.replace(
            "architecture_graph_",
            ""
        )
        repositories.append(name)

    repositories.sort()

    return {
        "repositories": repositories
    }


# ---------------------------------------------------------
# Architecture graph endpoint
# ---------------------------------------------------------

@app.get("/architecture/{repository}")
def get_architecture(repository: str):

    # Basic validation to prevent invalid file paths
    if "/" in repository or "\\" in repository or ".." in repository:
        raise HTTPException(
            status_code=400,
            detail="Invalid repository name"
        )

    graph_file = BASE_DIR / f"architecture_graph_{repository}.json"

    if not graph_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Architecture graph not found for repository: {repository}"
        )

    try:
        import json

        with open(graph_file, "r", encoding="utf-8") as file:
            graph = json.load(file)

        return {
            "repository": repository,
            "graph": graph
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not load architecture graph: {str(e)}"
        )


# ---------------------------------------------------------
# Ask ArchLens
# ---------------------------------------------------------

@app.post("/ask")
def ask_question(request: QuestionRequest):

    if not request.question.strip():
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty"
        )

    if not request.repository.strip():
        raise HTTPException(
            status_code=400,
            detail="Repository must be specified"
        )

    try:
        result = ask(
            request.question,
            request.repository
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
