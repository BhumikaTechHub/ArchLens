import json

from scripts.evaluate_repository import build_evaluation_report, evaluate_repository


def test_evaluation_report_counts_parse_errors_chunks_and_cross_language_edges():
    analysis = [
        {
            "file": "src/app.py", "language": "python", "imports": ["requests"],
            "classes": [{"name": "App"}], "interfaces": [],
            "functions": [{"name": "run"}],
        },
        {
            "file": "src/Service.java", "language": "java", "imports": [],
            "classes": [{"name": "Service"}], "interfaces": [],
            "functions": [{"name": "execute"}], "error": "sample parse error",
        },
    ]
    chunks = [
        {"metadata": {"language": "python"}},
        {"metadata": {"language": "java"}},
        {"metadata": {"language": "python"}},
    ]
    graph = {
        "nodes": [
            {"id": "py", "language": "python"},
            {"id": "java", "language": "java"},
        ],
        "edges": [
            {"source": "py", "target": "java", "relationship": "calls"}
        ],
        "call_resolution": {"resolved_calls": 1, "unresolved_calls": 2},
        "unresolved_relationships": [],
        "unresolved_call_details": [],
    }

    report = build_evaluation_report(analysis, chunks, graph)

    assert report["summary"]["total_files"] == 2
    assert report["summary"]["successful_parse_files"] == 1
    assert report["summary"]["parse_error_files"] == 1
    assert report["summary"]["parse_success_rate"] == 0.5
    assert report["by_language"]["python"]["chunks"] == 2
    assert report["by_language"]["java"]["declarations"] == 2
    assert report["cross_language_relationships"]["count"] == 1
    assert report["accuracy_claim"] is False


def test_evaluate_repository_on_small_mixed_language_fixture(tmp_path):
    (tmp_path / "main.py").write_text(
        "def main():\n    return 1\n", encoding="utf-8"
    )
    (tmp_path / "Service.java").write_text(
        "class Service { int run() { return 1; } }", encoding="utf-8"
    )

    report = evaluate_repository(str(tmp_path))

    assert report["summary"]["total_files"] == 2
    assert set(report["by_language"]) == {"java", "python"}
    assert report["summary"]["total_chunks"] >= 2
    assert report["cross_language_relationships"]["count"] == 0
    assert "does not prove no integration exists" in report[
        "cross_language_relationships"
    ]["status"]
