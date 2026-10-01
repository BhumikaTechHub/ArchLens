from fastapi import FastAPI
from pydantic import BaseModel

from backend.rag_service import ask


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
