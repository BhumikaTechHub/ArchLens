import json
import os


GRAPH_FILE = "architecture_graph.json"


EXPECTED_RELATIONSHIPS = [
    {
        "source": "order_service.py",
        "target": "payment",
        "relationship": "imports"
    },
    {
        "source": "order_service.py",
        "target": "database",
        "relationship": "imports"
    },
    {
        "source": "order_service.py",
        "target": "notification",
        "relationship": "imports"
    },
    {
        "source": "create_order",
        "target": "save_order",
        "relationship": "calls"
    },
    {
        "source": "create_order",
        "target": "process_payment",
        "relationship": "calls"
    },
    {
        "source": "create_order",
        "target": "send_notification",
        "relationship": "calls"
    }
]


def load_graph():

    if not os.path.exists(GRAPH_FILE):
        raise FileNotFoundError(
            f"{GRAPH_FILE} not found."
        )

    with open(GRAPH_FILE, "r") as f:
        return json.load(f)


def node_matches(node, name):

    node_id = str(node.get("id", "")).lower()
    label = str(node.get("label", "")).lower()

    name = name.lower()

    return (
        name in node_id
        or name in label
    )


def relationship_matches(
    graph,
    expected
):

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    source_ids = []

    target_ids = []

    for node in nodes:

        if node_matches(
            node,
            expected["source"]
        ):
            source_ids.append(
                node.get("id")
            )

        if node_matches(
            node,
            expected["target"]
        ):
            target_ids.append(
                node.get("id")
            )


    for edge in edges:

        relationship = str(
            edge.get(
                "relationship",
                ""
            )
        ).lower()

        if relationship != expected["relationship"]:
            continue

        if (
            edge.get("source") in source_ids
            and
            edge.get("target") in target_ids
        ):
            return True

    return False


def main():

    graph = load_graph()

    total = len(
        EXPECTED_RELATIONSHIPS
    )

    correct = 0

    print("\nARCHITECTURE RELATIONSHIP EVALUATION")
    print("=" * 50)

    for expected in EXPECTED_RELATIONSHIPS:

        passed = relationship_matches(
            graph,
            expected
        )

        if passed:
            correct += 1

        status = "PASS" if passed else "FAIL"

        print(
            f"[{status}] "
            f"{expected['source']} "
            f"--{expected['relationship']}--> "
            f"{expected['target']}"
        )

    accuracy = (
        correct / total * 100
        if total
        else 0
    )

    print("\nResults")
    print("-" * 50)
    print(f"Correct: {correct}/{total}")
    print(f"Accuracy: {accuracy:.2f}%")

    with open(
        "evaluation/architecture_results.json",
        "w"
    ) as f:

        json.dump(
            {
                "total": total,
                "correct": correct,
                "accuracy": accuracy
            },
            f,
            indent=2
        )


if __name__ == "__main__":
    main()
