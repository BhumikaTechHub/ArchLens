# ArchLens

## AI-Powered Software Architecture & Knowledge Explorer

ArchLens is an AI-powered tool that analyzes a software repository
and helps developers understand its architecture, dependencies,
functions, modules, and relationships.

## Features

- Python repository analysis
- AST-based code analysis
- Function and class extraction
- Import analysis
- Function-call analysis
- Architecture graph generation
- Code-aware chunking
- Semantic code search
- ChromaDB vector storage
- RAG-based question answering
- Ollama LLM integration
- Architecture-aware answers
- FastAPI backend
- Interactive web frontend

## Architecture

```text
Software Repository
        ↓
Python AST Analyzer
        ↓
Analysis + Architecture Graph
        ↓
Code Chunking
        ↓
Embeddings
        ↓
ChromaDB
        ↓
Semantic Retrieval
        ↓
Architecture Context
        ↓
Ollama LLM
        ↓
FastAPI
        ↓
ArchLens Frontend


Technologies
- Python
- FastAPI
- Python AST
- ChromaDB
- Ollama
- nomic-embed-text
- Qwen 2.5 1.5B
- HTML
- CSS
- JavaScript


Example
Question: What functions are called when an order is created?

ArchLens can identify:

create_order()
    ↓
save_order()
process_payment()
send_notification()


Project Structure

ArchLens/
├── analyzer/
├── backend/
├── frontend/
├── tests/
├── evaluation/
├── knowledge_base/
├── vector_db/
├── analysis.json
├── architecture_graph.json
├── requirements.txt
├── Dockerfile
└── docker-compose.yml


Running the Backend

cd ~/ArchLens
source venv/bin/activate
uvicorn backend.app:app --reload

Running the Frontend

cd ~/ArchLens/frontend
python3 -m http.server 5500

