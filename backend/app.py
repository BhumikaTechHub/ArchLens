from fastapi import FastAPI
from pydantic import BaseModel

from backend.rag_service import ask
import json

app = FastAPI(
    title="ArchLens API",
    description="AI-powered software architecture and knowledge explorer"
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

    with open("architecture_graph.json", "r") as f:
        graph = json.load(f)

    return graph


@app.get("/dependencies")
def dependencies():

    with open("analysis.json", "r") as f:
        analysis = json.load(f)

    result = {}

    for file_info in analysis:

        file_path = file_info["file"]

        result[file_path] = file_info.get(
            "imports",
            []
        )

    return result
