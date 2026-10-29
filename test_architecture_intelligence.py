from analyzer.architecture_metrics import (
    calculate_architecture_metrics,
)

from analyzer.architecture_rules import (
    analyze_architecture_rules,
)


sample_graph = {
    "nodes": [
        {
            "id": "app.py",
            "label": "app.py",
            "type": "file",
            "path": "backend/app.py",
        },
        {
            "id": "service.py",
            "label": "service.py",
            "type": "file",
            "path": "backend/service.py",
        },
        {
            "id": "database.py",
            "label": "database.py",
            "type": "file",
            "path": "backend/database.py",
        },
        {
            "id": "utils.py",
            "label": "utils.py",
            "type": "file",
            "path": "backend/utils.py",
        },
        {
            "id": "unused.py",
            "label": "unused.py",
            "type": "file",
            "path": "backend/unused.py",
        },
    ],
    "edges": [
        {
            "source": "app.py",
            "target": "service.py",
            "type": "imports",
        },
        {
            "source": "service.py",
            "target": "database.py",
            "type": "imports",
        },
        {
            "source": "database.py",
            "target": "app.py",
            "type": "imports",
        },
        {
            "source": "service.py",
            "target": "utils.py",
            "type": "imports",
        },
    ],
}


if __name__ == "__main__":

    print("\n========== STAGE 1: METRICS ==========")

    metrics = calculate_architecture_metrics(sample_graph)

    print(metrics)

    print("\n========== STAGE 2: RULES ==========")

    report = analyze_architecture_rules(sample_graph)

    print("\nHealth:")
    print(report["health"])

    print("\nSummary:")
    print(report["summary"])

    print("\nFindings:")

    for finding in report["findings"]:
        print(
            f"\n[{finding['severity'].upper()}] "
            f"{finding['rule_id']}: {finding['title']}"
        )

        print(finding["description"])
        print(f"Recommendation: {finding['recommendation']}")
