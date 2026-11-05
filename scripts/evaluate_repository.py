"""Generate a reproducible structural evaluation report for an analyzed repository.

This report measures parser/indexing coverage and graph diagnostics. It does not
claim semantic accuracy; accuracy requires a manually verified ground-truth set.
"""
import argparse
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analyzer.build_graph import build_graph
from analyzer.create_code_chunks import create_chunks
from analyzer.repository_analyzer import analyze_repository


def build_evaluation_report(analysis, chunks, graph):
    """Summarize parser, chunking, graph, and cross-language coverage."""
    files_by_language = Counter()
    parse_error_files = []
    declarations_by_language = Counter()
    imports_by_language = Counter()

    for item in analysis:
        language = item.get("language", "unknown")
        files_by_language[language] += 1
        if item.get("error"):
            parse_error_files.append({
                "file": item.get("file"),
                "language": language,
                "error": item["error"],
            })
        declarations_by_language[language] += (
            len(item.get("classes", []))
            + len(item.get("interfaces", []))
            + len(item.get("functions", []))
        )
        imports_by_language[language] += len(item.get("imports", []))

    chunks_by_language = Counter(
        chunk.get("metadata", {}).get("language", "unknown")
        for chunk in chunks
    )

    nodes_by_id = {node["id"]: node for node in graph.get("nodes", [])}
    cross_language_edges = []
    relationship_counts = Counter()
    for edge in graph.get("edges", []):
        relationship_counts[edge.get("relationship", "unknown")] += 1
        source = nodes_by_id.get(edge.get("source"), {})
        target = nodes_by_id.get(edge.get("target"), {})
        source_language = source.get("language")
        target_language = target.get("language")
        if (
            source_language and target_language
            and source_language != target_language
        ):
            cross_language_edges.append({
                "source": edge.get("source"),
                "target": edge.get("target"),
                "relationship": edge.get("relationship"),
                "source_language": source_language,
                "target_language": target_language,
            })

    total_files = len(analysis)
    successful_files = total_files - len(parse_error_files)
    call_resolution = graph.get("call_resolution", {})
    return {
        "scope": "structural parser, chunking, and graph diagnostics",
        "accuracy_claim": False,
        "summary": {
            "total_files": total_files,
            "successful_parse_files": successful_files,
            "parse_error_files": len(parse_error_files),
            "parse_success_rate": (
                round(successful_files / total_files, 4)
                if total_files else None
            ),
            "total_chunks": len(chunks),
            "graph_nodes": len(graph.get("nodes", [])),
            "graph_edges": len(graph.get("edges", [])),
        },
        "by_language": {
            language: {
                "files": files_by_language[language],
                "declarations": declarations_by_language[language],
                "imports": imports_by_language[language],
                "chunks": chunks_by_language[language],
            }
            for language in sorted(files_by_language)
        },
        "graph_relationships": dict(sorted(relationship_counts.items())),
        "call_resolution": call_resolution,
        "cross_language_relationships": {
            "count": len(cross_language_edges),
            "edges": cross_language_edges,
            "status": (
                "observed in graph"
                if cross_language_edges
                else "none detected; this does not prove no integration exists"
            ),
        },
        "parse_errors": parse_error_files,
        "unresolved_relationships": graph.get(
            "unresolved_relationships", []
        ),
        "unresolved_call_details": graph.get(
            "unresolved_call_details", []
        ),
        "interpretation": [
            "Parse success measures syntax-processing coverage, not semantic correctness.",
            "Chunk counts measure indexing inputs, not retrieval relevance.",
            "Resolved-call counts cover only relationship types currently implemented.",
            "No cross-language graph edge means no supported cross-language relationship was detected; API, database, queue, and process integrations may still exist.",
        ],
    }


def evaluate_repository(repository_path):
    repository_path = Path(repository_path).resolve()
    if not repository_path.is_dir():
        raise ValueError(f"Repository path is not a directory: {repository_path}")

    analysis = analyze_repository(str(repository_path))
    chunks = create_chunks(str(repository_path))
    with tempfile.TemporaryDirectory(prefix="archlens-eval-") as temp_dir:
        analysis_path = Path(temp_dir) / "analysis.json"
        analysis_path.write_text(
            json.dumps(analysis, indent=2), encoding="utf-8"
        )
        graph = build_graph(str(analysis_path))

    return build_evaluation_report(analysis, chunks, graph)


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate ArchLens structural coverage on a local repository."
    )
    parser.add_argument("repository", help="Path to the repository to evaluate")
    parser.add_argument(
        "--output",
        help="Optional path for the JSON report (default: print to stdout)",
    )
    args = parser.parse_args()

    report = evaluate_repository(args.repository)
    rendered = json.dumps(report, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
        print(f"Evaluation report saved to: {args.output}")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
