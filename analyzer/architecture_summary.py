import json


GRAPH_FILE = "architecture_graph.json"


def load_graph():

    with open(GRAPH_FILE, "r") as f:
        return json.load(f)


def create_summary(graph):

    nodes = graph["nodes"]
    edges = graph["edges"]

    summary = {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "files": 0,
        "modules": 0,
        "classes": 0,
        "functions": 0,
        "relationships": {
            "imports": 0,
            "contains": 0,
            "calls": 0
        }
    }

    for node in nodes:

        node_type = node["type"]

        if node_type == "file":
            summary["files"] += 1

        elif node_type == "module":
            summary["modules"] += 1

        elif node_type == "class":
            summary["classes"] += 1

        elif node_type == "function":
            summary["functions"] += 1

    for edge in edges:

        relationship = edge["relationship"]

        if relationship in summary["relationships"]:
            summary["relationships"][relationship] += 1

    return summary


def main():

    graph = load_graph()

    summary = create_summary(graph)

    print("\nARCHITECTURE SUMMARY\n")

    print(
        json.dumps(
            summary,
            indent=2
        )
    )


if __name__ == "__main__":
    main()
