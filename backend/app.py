
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from backend.rag_service import ask
from backend.repository_manager import import_repository
from analyzer.repository_analyzer import analyze_repository
from analyzer.build_graph import build_graph
from analyzer.create_code_chunks import create_chunks
from analyzer.index_code import index_repository
from backend.change_impact import analyze_change_impact
import re
import json 
import shutil

from analyzer.architecture_metrics import (
    calculate_architecture_metrics,
)

from analyzer.architecture_rules import (
    analyze_architecture_rules,
)
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

IMPORTED_GRAPH_DIR = (
    BASE_DIR / "imported_repositories" / "generated"
)


def load_repository_graph(repository: str):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", repository):
        raise HTTPException(
            status_code=400,
            detail="Invalid repository name."
        )

    if repository in {".", ".."}:
        raise HTTPException(
            status_code=400,
            detail="Invalid repository name."
        )

    # First check the original sample repository location.
    sample_graph = BASE_DIR / f"architecture_graph_{repository}.json"

    # Then check the imported repository location.
    imported_graph = (
        IMPORTED_GRAPH_DIR / repository / "architecture_graph.json"
    )

    if sample_graph.is_file():
        graph_file = sample_graph
    elif imported_graph.is_file():
        graph_file = imported_graph
    else:
        raise HTTPException(
            status_code=404,
            detail=f"Architecture graph not found for: {repository}"
        )

    try:
        with graph_file.open("r", encoding="utf-8") as file:
            graph = json.load(file)

        if not isinstance(graph, dict):
            raise ValueError("Invalid graph format.")

        return graph

    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail="Architecture graph contains invalid JSON."
        )
# ---------------------------------------------------------
# Request model
# ---------------------------------------------------------

class QuestionRequest(BaseModel):
    question: str
    repository: str

class ChangeImpactRequest(BaseModel):
    repository: str
    component: str
    max_depth: int = 10

class ImportRepositoryRequest(BaseModel):
    url: str
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


# ---------------------------------------------------------
# Architecture graph endpoint
# ---------------------------------------------------------

@app.get("/repositories")
def get_repositories():
    repositories = set()

    # Include original sample repositories.
    for file in BASE_DIR.glob("architecture_graph_*.json"):
        name = file.stem.replace(
            "architecture_graph_",
            ""
        )
        repositories.add(name)

    # Include imported repositories with generated graphs.
    imported_graph_dir = (
        BASE_DIR / "imported_repositories" / "generated"
    )

    if imported_graph_dir.exists():
        for repo_dir in imported_graph_dir.iterdir():
            graph_file = repo_dir / "architecture_graph.json"

            if repo_dir.is_dir() and graph_file.is_file():
                repositories.add(repo_dir.name)

    return {
        "repositories": sorted(repositories)
    }

@app.get("/architecture/{repository}")
def get_architecture(repository: str):
    graph = load_repository_graph(repository)

    return {
        "repository": repository,
        "graph": graph
    }

# ---------------------------------------------------------
# Import GitHub Repository
# ---------------------------------------------------------

@app.post("/import-repository")
def import_github_repository(request: ImportRepositoryRequest):

    metadata = None
    repo_path = None
    generated_dir = None

    try:
        # 1. Clone repository
        metadata = import_repository(request.url)

        repo_id = metadata["repository_id"]

        repo_path = BASE_DIR / metadata["local_path"]

        generated_dir = (
            BASE_DIR
            / "imported_repositories"
            / "generated"
            / repo_id
        )

        generated_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        # 2. Analyze all registered source languages
        analysis = analyze_repository(str(repo_path))

        if not analysis:
            raise ValueError(
                "No supported source files were found in this repository."
            )

        analysis_file = generated_dir / "analysis.json"

        analysis_file.write_text(
            json.dumps(analysis, indent=2),
            encoding="utf-8"
        )

        # 3. Build architecture graph
        graph = build_graph(str(analysis_file))

        graph_file = generated_dir / "architecture_graph.json"

        graph_file.write_text(
            json.dumps(graph, indent=2),
            encoding="utf-8"
        )

        # 4. Generate code chunks
        chunks = create_chunks(str(repo_path))

        if not chunks:
            raise ValueError(
                "No code chunks could be generated for supported source files."
            )

        chunks_file = generated_dir / "code_chunks.json"

        chunks_file.write_text(
            json.dumps(chunks, indent=2),
            encoding="utf-8"
        )

        # 5. Build vector index
        index_repository(repo_id)

        # 6. Update metadata only after successful processing
        metadata["status"] = "ready"
        metadata["analyzed_files"] = len(analysis)
        metadata["language_counts"] = {
            language: sum(
                1 for item in analysis
                if item.get("language") == language
            )
            for language in sorted({
                item.get("language", "unknown") for item in analysis
            })
        }
        metadata["parse_errors"] = sum(
            1 for item in analysis
            if item.get("error") or item.get("parse_errors")
        )
        metadata["chunks"] = len(chunks)
        metadata["graph_nodes"] = len(graph["nodes"])
        metadata["graph_edges"] = len(graph["edges"])

        metadata_path = (
            BASE_DIR
            / "imported_repositories"
            / "metadata"
            / f"{repo_id}.json"
        )

        metadata_path.write_text(
            json.dumps(metadata, indent=2),
            encoding="utf-8"
        )

        return {
            "message": "Repository imported and indexed successfully.",
            "repository": repo_id,
            "status": "ready",
            "analyzed_files": len(analysis),
            "language_counts": metadata["language_counts"],
            "parse_errors": metadata["parse_errors"],
            "chunks": len(chunks),
            "graph_nodes": len(graph["nodes"]),
            "graph_edges": len(graph["edges"])
        }

    except Exception as error:

        # Clean up only the repository created by this request.
        if metadata:
            repo_id = metadata["repository_id"]

            if generated_dir and generated_dir.exists():
                shutil.rmtree(
                    generated_dir,
                    ignore_errors=True
                )

            if repo_path and repo_path.exists():
                shutil.rmtree(
                    repo_path,
                    ignore_errors=True
                )

            metadata_path = (
                BASE_DIR
                / "imported_repositories"
                / "metadata"
                / f"{repo_id}.json"
            )

            if metadata_path.exists():
                metadata_path.unlink()

        if isinstance(error, ValueError):
            raise HTTPException(
                status_code=400,
                detail=str(error)
            )

        raise HTTPException(
            status_code=500,
            detail=f"Repository import failed: {str(error)}"
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


@app.post("/impact-analysis")
def change_impact(request: ChangeImpactRequest):
    import json

    repository = request.repository.strip()
    component = request.component.strip()

    if not repository:
        raise HTTPException(
            status_code=400,
            detail="Repository must be specified.",
        )

    if not component:
        raise HTTPException(
            status_code=400,
            detail="Component must be specified.",
        )

    # Validate repository identifier before constructing a path.
    if (
        "/" in repository
        or "\\" in repository
        or ".." in repository
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid repository name.",
        )

    if not 1 <= request.max_depth <= 25:
        raise HTTPException(
            status_code=400,
            detail="max_depth must be between 1 and 25.",
        )

    try:
        graph = load_repository_graph(repository)

        result = analyze_change_impact(
            graph=graph,
            component=component,
            max_depth=request.max_depth,
        )

        result["repository"] = repository

        return result

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail="The architecture graph contains invalid JSON.",
        )

    except Exception:
        # Avoid exposing internal paths or implementation details.
        raise HTTPException(
            status_code=500,
            detail="Change impact analysis failed.",
        )




@app.get("/dashboard/{repository}")
def get_architecture_dashboard(repository: str):
    """
    Return architecture metrics and rule-based findings
    for a previously analyzed repository.
    """

    # Prevent repository names from escaping the project directory.
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", repository):
        raise HTTPException(
            status_code=400,
            detail="Invalid repository name.",
        )

    if repository in {".", ".."}:
        raise HTTPException(
            status_code=400,
            detail="Invalid repository name.",
        )

    try:
        graph = load_repository_graph(repository)
        metrics_report = calculate_architecture_metrics(graph)

        rules_report = analyze_architecture_rules(graph)

        return {
            "repository": repository,
            "metrics": metrics_report["metrics"],
            "component_types": metrics_report["component_types"],
            "language_distribution": metrics_report[
                "language_distribution"
            ],
            "top_connected_components": metrics_report[
                "top_connected_components"
            ],
            "highly_connected_components": metrics_report[
                "highly_connected_components"
            ],
            "isolated_components": metrics_report[
                "isolated_components"
            ],
            "health": rules_report["health"],
            "summary": rules_report["summary"],
            "findings": rules_report["findings"],
        }

    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail="The architecture graph contains invalid JSON.",
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Unable to analyze architecture graph: {exc}",
        ) from exc
