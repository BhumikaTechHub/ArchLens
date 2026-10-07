import json
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.rag_service import ask


BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)


app = FastAPI(
    title="ArchLens API",
    description="AI-powered software architecture and knowledge explorer"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    question: str


@app.get("/")
def root():
    return {
        "project": "ArchLens",
        "status": "running"
    }


@app.post("/ask")
def ask_question(request: QuestionRequest):
    return ask(request.question)


@app.get("/architecture")
def architecture():

    graph_path = os.path.join(
        BASE_DIR,
        "architecture_graph.json"
    )

    with open(graph_path, "r") as f:
        return json.load(f)


@app.get("/dependencies")
def dependencies():

    analysis_path = os.path.join(
        BASE_DIR,
        "analysis.json"
    )

    with open(analysis_path, "r") as f:
        analysis = json.load(f)

    result = {}

    for file_info in analysis:

        file_path = file_info["file"]

        result[file_path] = file_info.get(
            "imports",
            []
        )

    return result
