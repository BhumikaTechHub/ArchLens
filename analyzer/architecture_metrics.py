from collections import Counter, defaultdict
from pathlib import PurePosixPath
from typing import Any


def get_node_id(node: dict) -> str:
    """Return a normalized component ID."""
    return str(node.get("id", ""))


def get_node_label(node: dict) -> str:
    """Return a human-readable component name."""
    return str(
        node.get("label")
        or node.get("name")
        or node.get("id")
        or "Unknown component"
    )


def get_node_type(node: dict) -> str:
    """Return the component type."""
    return str(node.get("type") or "unknown").lower()


def get_file_path(node: dict) -> str:
    """Extract a file path when the graph provides one."""
    for key in ("file", "path", "file_path", "filename"):
        value = node.get(key)

        if isinstance(value, str) and value.strip():
            return value.replace("\\", "/")

    return ""


def infer_language(node: dict) -> str:
    """Infer a language from the component's file extension."""
    path = get_file_path(node)

    if not path:
        return "Unknown"

    suffix = PurePosixPath(path).suffix.lower()

    language_map = {
        ".py": "Python",
        ".js": "JavaScript",
        ".jsx": "JavaScript",
        ".mjs": "JavaScript",
        ".cjs": "JavaScript",
        ".ts": "TypeScript",
        ".tsx": "TypeScript",
        ".java": "Java",
        ".kt": "Kotlin",
        ".go": "Go",
        ".rs": "Rust",
        ".cpp": "C++",
        ".cc": "C++",
        ".c": "C",
        ".h": "C/C++ Header",
        ".hpp": "C++ Header",
        ".cs": "C#",
        ".php": "PHP",
        ".rb": "Ruby",
        ".swift": "Swift",
        ".html": "HTML",
        ".css": "CSS",
        ".scss": "SCSS",
        ".json": "JSON",
        ".yaml": "YAML",
        ".yml": "YAML",
        ".md": "Markdown",
        ".sql": "SQL",
        ".sh": "Shell",
        ".xml": "XML",
    }

    return language_map.get(suffix, "Other")


def calculate_architecture_metrics(
    graph: dict[str, Any],
) -> dict[str, Any]:
    """
    Calculate architecture metrics from a graph containing:
        {
            "nodes": [...],
            "edges": [...]
        }

    The function supports common node and edge field names.
    """

    raw_nodes = graph.get("nodes", [])
    raw_edges = graph.get("edges", [])

    if not isinstance(raw_nodes, list):
        raise ValueError("Graph 'nodes' must be a list.")

    if not isinstance(raw_edges, list):
        raise ValueError("Graph 'edges' must be a list.")

    # --------------------------------------------------
    # 1. Normalize nodes and remove duplicate IDs
    # --------------------------------------------------

    nodes_by_id = {}

    for node in raw_nodes:
        if not isinstance(node, dict):
            continue

        node_id = get_node_id(node)

        if not node_id:
            continue

        nodes_by_id[node_id] = node

    nodes = list(nodes_by_id.values())
    valid_ids = set(nodes_by_id.keys())

    # --------------------------------------------------
    # 2. Normalize edges and remove duplicate edges
    # --------------------------------------------------

    normalized_edges = []
    seen_edges = set()

    for edge in raw_edges:
        if not isinstance(edge, dict):
            continue

        source = edge.get("source", edge.get("from"))
        target = edge.get("target", edge.get("to"))

        if source is None or target is None:
            continue

        source = str(source)
        target = str(target)

        # Ignore edges that reference missing components.
        if source not in valid_ids or target not in valid_ids:
            continue

        edge_type = str(
            edge.get("type")
            or edge.get("label")
            or edge.get("relationship")
            or "dependency"
        )

        edge_key = (source, target, edge_type)

        if edge_key in seen_edges:
            continue

        seen_edges.add(edge_key)

        normalized_edges.append(
            {
                "source": source,
                "target": target,
                "type": edge_type,
            }
        )

    # --------------------------------------------------
    # 3. Build adjacency information
    # --------------------------------------------------

    outgoing = defaultdict(set)
    incoming = defaultdict(set)

    for edge in normalized_edges:
        source = edge["source"]
        target = edge["target"]

        outgoing[source].add(target)
        incoming[target].add(source)

    # --------------------------------------------------
    # 4. Component type distribution
    # --------------------------------------------------

    type_counts = Counter(
        get_node_type(node)
        for node in nodes
    )

    component_types = dict(
        sorted(type_counts.items())
    )

    # --------------------------------------------------
    # 5. Language distribution
    # --------------------------------------------------

    language_counts = Counter(
        infer_language(node)
        for node in nodes
    )

    language_distribution = dict(
        sorted(language_counts.items())
    )

    # --------------------------------------------------
    # 6. Connectivity metrics
    # --------------------------------------------------

    component_metrics = []

    for node in nodes:
        node_id = get_node_id(node)

        outgoing_count = len(outgoing[node_id])
        incoming_count = len(incoming[node_id])

        component_metrics.append(
            {
                "id": node_id,
                "label": get_node_label(node),
                "type": get_node_type(node),
                "file": get_file_path(node),
                "language": infer_language(node),
                "incoming_dependencies": incoming_count,
                "outgoing_dependencies": outgoing_count,
                "total_connections": incoming_count + outgoing_count,
            }
        )

    # Highest connectivity first.
    component_metrics.sort(
        key=lambda item: (
            item["total_connections"],
            item["outgoing_dependencies"],
        ),
        reverse=True,
    )

    # --------------------------------------------------
    # 7. Isolated components
    # --------------------------------------------------

    isolated_components = [
        component
        for component in component_metrics
        if component["total_connections"] == 0
    ]

    # --------------------------------------------------
    # 8. Graph density
    # --------------------------------------------------

    node_count = len(nodes)
    edge_count = len(normalized_edges)

    # Directed graph without self-loops has at most
    # n * (n - 1) distinct edges.
    possible_edges = node_count * (node_count - 1)

    graph_density = (
        edge_count / possible_edges
        if possible_edges > 0
        else 0.0
    )

    # --------------------------------------------------
    # 9. Component-level statistics
    # --------------------------------------------------

    if component_metrics:
        connection_counts = [
            component["total_connections"]
            for component in component_metrics
        ]

        average_connections = (
            sum(connection_counts) / len(connection_counts)
        )

        max_connections = max(connection_counts)

    else:
        average_connections = 0.0
        max_connections = 0

    # --------------------------------------------------
    # 10. Highly connected components
    # --------------------------------------------------

    # This is a screening threshold, not a universal
    # definition of an architecture problem.
    high_coupling_threshold = max(
        5,
        round(average_connections * 2),
    )

    highly_connected_components = [
        component
        for component in component_metrics
        if component["total_connections"] >= high_coupling_threshold
    ]

    # --------------------------------------------------
    # 11. Build the result
    # --------------------------------------------------

    return {
        "metrics": {
            "total_components": node_count,
            "total_relationships": edge_count,
            "graph_density": round(graph_density, 4),
            "average_connections_per_component": round(
                average_connections, 2
            ),
            "maximum_connections": max_connections,
            "isolated_components": len(isolated_components),
            "highly_connected_components": len(
                highly_connected_components
            ),
        },
        "component_types": component_types,
        "language_distribution": language_distribution,
        "top_connected_components": component_metrics[:10],
        "highly_connected_components": highly_connected_components,
        "isolated_components": isolated_components,
    }
