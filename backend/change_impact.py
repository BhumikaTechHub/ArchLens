from collections import defaultdict, deque
from typing import Any


# =========================================================
# NORMALIZATION HELPERS
# =========================================================

def normalize(value: Any) -> str:
    """Normalize identifiers for case-insensitive matching."""
    return str(value or "").replace("\\", "/").strip().lower()


def component_identifiers(node: dict) -> set[str]:
    """
    Collect identifiers that can be used to find a graph component.
    """
    identifiers = {
        normalize(node.get("id")),
        normalize(node.get("label")),
        normalize(node.get("file")),
        normalize(node.get("path")),
    }

    return {
        identifier
        for identifier in identifiers
        if identifier
    }


# =========================================================
# FIND COMPONENT
# =========================================================

def find_component(
    nodes: list[dict],
    component: str,
) -> dict | None:
    """
    Find a component by exact ID, label, filename, or path.

    If a filename matches multiple components, return None
    rather than choosing an arbitrary component.
    """
    target = normalize(component)

    if not target:
        return None

    # Prefer exact matches.
    exact_matches = [
        node
        for node in nodes
        if target in component_identifiers(node)
    ]

    if len(exact_matches) == 1:
        return exact_matches[0]

    if len(exact_matches) > 1:
        # Prefer a unique exact ID match.
        id_matches = [
            node
            for node in exact_matches
            if normalize(node.get("id")) == target
        ]

        if len(id_matches) == 1:
            return id_matches[0]

        return None

    # Allow a filename to match a unique full path.
    path_matches = []

    for node in nodes:
        identifiers = component_identifiers(node)

        if any(
            identifier.endswith("/" + target)
            for identifier in identifiers
        ):
            path_matches.append(node)

    if len(path_matches) == 1:
        return path_matches[0]

    return None


# =========================================================
# BUILD DEPENDENCY GRAPH
# =========================================================

def build_adjacency(
    nodes: list[dict],
    edges: list[dict],
) -> tuple[dict, dict, dict]:
    """
    Build outgoing and incoming adjacency lists.

    Graph edges use the convention:

        source -> target

    The returned node_map uses string IDs to ensure consistent
    matching between API requests and Cytoscape graph elements.
    """
    node_map = {
        str(node["id"]): node
        for node in nodes
        if node.get("id") is not None
    }

    outgoing = defaultdict(list)
    incoming = defaultdict(list)

    for edge in edges:
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))

        # Ignore edges referring to missing graph nodes.
        if source not in node_map or target not in node_map:
            continue

        relationship = str(
            edge.get("relationship") or "related_to"
        )

        outgoing[source].append(
            (target, relationship)
        )

        incoming[target].append(
            (source, relationship)
        )

    return node_map, outgoing, incoming


# =========================================================
# FIND SHORTEST DEPENDENCY PATH
# =========================================================

def find_dependency_path(
    start_id: str,
    target_id: str,
    adjacency: dict,
    max_depth: int = 10,
) -> list[dict] | None:
    """
    Find a shortest path using breadth-first search.

    Each path step contains:
        source
        target
        relationship

    The adjacency determines traversal direction.

    For upstream analysis, the incoming adjacency is used,
    so the returned path follows dependents back toward
    components they rely on.
    """
    start_id = str(start_id)
    target_id = str(target_id)

    if start_id == target_id:
        return []

    queue = deque([
        (start_id, [])
    ])

    visited = {start_id}

    while queue:
        current_id, path = queue.popleft()

        if len(path) >= max_depth:
            continue

        for neighbor_id, relationship in adjacency.get(
            current_id, []
        ):
            neighbor_id = str(neighbor_id)

            if neighbor_id in visited:
                continue

            step = {
                "source": current_id,
                "target": neighbor_id,
                "relationship": relationship,
            }

            new_path = path + [step]

            if neighbor_id == target_id:
                return new_path

            visited.add(neighbor_id)

            queue.append(
                (neighbor_id, new_path)
            )

    return None


# =========================================================
# TRAVERSE DEPENDENCIES
# =========================================================

def traverse_dependencies(
    start_id: str,
    adjacency: dict,
    max_depth: int,
) -> dict:
    """
    Discover reachable components and their shortest distance.

    Returns:
        {
            component_id: {
                "depth": 1,
                "relationship": "imports"
            }
        }
    """
    results = {}

    queue = deque([
        (str(start_id), 0, None)
    ])

    visited = {
        str(start_id)
    }

    while queue:
        current_id, depth, first_relationship = queue.popleft()

        if depth >= max_depth:
            continue

        for neighbor_id, relationship in adjacency.get(
            current_id, []
        ):
            neighbor_id = str(neighbor_id)

            if neighbor_id in visited:
                continue

            visited.add(neighbor_id)

            relationship_for_result = (
                first_relationship
                if first_relationship is not None
                else relationship
            )

            results[neighbor_id] = {
                "depth": depth + 1,
                "relationship": relationship_for_result,
            }

            queue.append(
                (
                    neighbor_id,
                    depth + 1,
                    relationship_for_result,
                )
            )

    return results


# =========================================================
# BUILD PATH EXPLANATION
# =========================================================

def build_path_explanation(
    selected_id: str,
    target_id: str,
    direction: str,
    node_map: dict,
    outgoing: dict,
    incoming: dict,
    max_depth: int,
) -> dict | None:
    """
    Construct a readable dependency path between two components.

    Downstream:
        Follow source -> target graph edges.

    Upstream:
        Traverse incoming edges to discover components that
        depend on the selected component.

    For upstream paths, the displayed arrows represent the
    impact-traversal direction, not the original edge direction.
    """
    if direction == "downstream":
        adjacency = outgoing
    else:
        adjacency = incoming

    steps = find_dependency_path(
        start_id=selected_id,
        target_id=target_id,
        adjacency=adjacency,
        max_depth=max_depth,
    )

    if steps is None:
        return None

    path_node_ids = [str(selected_id)]

    for step in steps:
        path_node_ids.append(
            str(step["target"])
        )

    path_nodes = []

    for index, node_id in enumerate(path_node_ids):
        node = node_map.get(node_id)

        if node is None:
            return None

        path_item = {
            "id": node_id,
            "label": node.get("label", node_id),
            "type": node.get("type", "unknown"),
        }

        file_path = node.get("file") or node.get("path")

        if file_path:
            path_item["file"] = file_path

        if index < len(steps):
            path_item["relationship_to_next"] = (
                steps[index]["relationship"]
            )

        path_nodes.append(path_item)

    return {
        "direction": direction,
        "nodes": path_nodes,
        "length": len(steps),
    }


# =========================================================
# IDENTIFY TEST COMPONENTS
# =========================================================

def is_test_component(node: dict) -> bool:
    """
    Identify possible test files or test components using
    common naming conventions.

    This is a heuristic. It does not prove that a component
    is an executable test.
    """
    identifiers = component_identifiers(node)

    for identifier in identifiers:
        filename = identifier.rsplit("/", 1)[-1]

        if filename.startswith("test_"):
            return True

        if filename.endswith("_test.py"):
            return True

        if filename.endswith(".test.js"):
            return True

        if filename.endswith(".test.jsx"):
            return True

        if filename.endswith(".test.ts"):
            return True

        if filename.endswith(".test.tsx"):
            return True

        if filename.endswith(".spec.js"):
            return True

        if filename.endswith(".spec.ts"):
            return True

        if "/tests/" in f"/{identifier}/":
            return True

        if "/test/" in f"/{identifier}/":
            return True

    return False


# =========================================================
# FIND RELATED TESTS
# =========================================================

def find_related_tests(
    selected_id: str,
    test_ids: set[str],
    affected_ids: set[str],
    node_map: dict,
    outgoing: dict,
    incoming: dict,
) -> list[dict]:
    """
    Find potential related tests based on graph connectivity.

    A test is considered related if:
        1. It is itself reachable from the selected component; or
        2. It directly connects to the selected component or
           another affected component.

    The result is only as complete as the architecture graph.
    """
    relevant_test_ids = set()

    for test_id in test_ids:
        if test_id in affected_ids:
            relevant_test_ids.add(test_id)
            continue

        neighbors = {
            neighbor
            for neighbor, _ in outgoing[test_id]
        }

        neighbors.update(
            neighbor
            for neighbor, _ in incoming[test_id]
        )

        if (
            selected_id in neighbors
            or neighbors.intersection(affected_ids)
        ):
            relevant_test_ids.add(test_id)

    related_tests = []

    for test_id in sorted(relevant_test_ids):
        node = node_map[test_id]

        test = {
            "id": test_id,
            "label": node.get("label", test_id),
        }

        file_path = node.get("file") or node.get("path")

        if file_path:
            test["file"] = file_path

        related_tests.append(test)

    return related_tests


# =========================================================
# MAIN CHANGE IMPACT ANALYSIS
# =========================================================

def analyze_change_impact(
    graph: dict,
    component: str,
    max_depth: int = 10,
) -> dict:
    """
    Analyze potential impact from changing a selected component.

    Features:
        - Component lookup
        - Direct dependency discovery
        - Indirect dependency discovery
        - Upstream and downstream traversal
        - Related-test detection
        - Dependency-path explanations
        - Heuristic impact score
        - Risk labels
    """
    # -----------------------------------------------------
    # VALIDATE INPUT
    # -----------------------------------------------------

    if not isinstance(graph, dict):
        raise ValueError(
            "Architecture graph must be a JSON object."
        )

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    if not isinstance(nodes, list):
        raise ValueError(
            "Architecture graph 'nodes' must be a list."
        )

    if not isinstance(edges, list):
        raise ValueError(
            "Architecture graph 'edges' must be a list."
        )

    if not 1 <= max_depth <= 25:
        raise ValueError(
            "max_depth must be between 1 and 25."
        )

    # -----------------------------------------------------
    # FIND SELECTED COMPONENT
    # -----------------------------------------------------

    selected = find_component(
        nodes,
        component,
    )

    if selected is None:
        raise ValueError(
            f"Component '{component}' was not found or "
            "matches multiple components. Try its exact "
            "graph ID or full file path."
        )

    selected_id = str(selected["id"])

    # -----------------------------------------------------
    # BUILD GRAPH STRUCTURES
    # -----------------------------------------------------

    node_map, outgoing, incoming = build_adjacency(
        nodes,
        edges,
    )

    if selected_id not in node_map:
        raise ValueError(
            "Selected component is missing a valid graph ID."
        )

    # -----------------------------------------------------
    # DISCOVER UPSTREAM AND DOWNSTREAM COMPONENTS
    # -----------------------------------------------------

    downstream = traverse_dependencies(
        start_id=selected_id,
        adjacency=outgoing,
        max_depth=max_depth,
    )

    upstream = traverse_dependencies(
        start_id=selected_id,
        adjacency=incoming,
        max_depth=max_depth,
    )

    # -----------------------------------------------------
    # COMBINE AFFECTED COMPONENTS
    # -----------------------------------------------------

    affected = {}

    for direction, results in (
        ("downstream", downstream),
        ("upstream", upstream),
    ):
        for node_id, info in results.items():
            candidate = {
                "direction": direction,
                "depth": info["depth"],
                "relationship": info["relationship"],
            }

            current = affected.get(node_id)

            if (
                current is None
                or candidate["depth"] < current["depth"]
            ):
                affected[node_id] = candidate

    # -----------------------------------------------------
    # IDENTIFY TEST NODES
    # -----------------------------------------------------

    test_ids = {
        node_id
        for node_id, node in node_map.items()
        if is_test_component(node)
    }

    related_tests = find_related_tests(
        selected_id=selected_id,
        test_ids=test_ids,
        affected_ids=set(affected.keys()),
        node_map=node_map,
        outgoing=outgoing,
        incoming=incoming,
    )

    # -----------------------------------------------------
    # CALCULATE IMPACT SCORE
    # -----------------------------------------------------

    direct_count = sum(
        1
        for info in affected.values()
        if info["depth"] == 1
    )

    indirect_count = sum(
        1
        for info in affected.values()
        if info["depth"] > 1
    )

    test_count = len(related_tests)

    impact_score = min(
        100,
        direct_count * 20
        + indirect_count * 5
        + test_count * 10,
    )

    if impact_score >= 70:
        overall_risk = "high"
    elif impact_score >= 30:
        overall_risk = "medium"
    else:
        overall_risk = "low"

    # -----------------------------------------------------
    # BUILD IMPACTED COMPONENT REPORT
    # -----------------------------------------------------

    impacted_components = []

    sorted_affected = sorted(
        affected.items(),
        key=lambda item: (
            item[1]["depth"],
            item[1]["direction"],
            item[0],
        ),
    )

    for node_id, info in sorted_affected:
        node = node_map[node_id]

        # Per-component heuristic risk.
        if info["depth"] == 1:
            risk = "high"
        elif info["depth"] <= 3:
            risk = "medium"
        else:
            risk = "low"

        # Build the path explanation.
        dependency_path = build_path_explanation(
            selected_id=selected_id,
            target_id=node_id,
            direction=info["direction"],
            node_map=node_map,
            outgoing=outgoing,
            incoming=incoming,
            max_depth=max_depth,
        )

        impacted_component = {
            "id": node_id,
            "label": node.get("label", node_id),
            "type": node.get("type", "unknown"),
            "direction": info["direction"],
            "depth": info["depth"],
            "relationship": info["relationship"],
            "risk": risk,
            "is_test": node_id in test_ids,
            "dependency_path": dependency_path,
        }

        file_path = node.get("file") or node.get("path")

        if file_path:
            impacted_component["file"] = file_path

        impacted_components.append(
            impacted_component
        )

    # -----------------------------------------------------
    # BUILD SELECTED COMPONENT INFORMATION
    # -----------------------------------------------------

    selected_component = {
        "id": selected_id,
        "label": selected.get("label", selected_id),
        "type": selected.get("type", "unknown"),
    }

    selected_file = (
        selected.get("file")
        or selected.get("path")
    )

    if selected_file:
        selected_component["file"] = selected_file

    # -----------------------------------------------------
    # FINAL RESPONSE
    # -----------------------------------------------------

    return {
        "selected_component": selected_component,

        "summary": {
            "direct_dependencies": direct_count,
            "indirect_dependencies": indirect_count,
            "related_tests": len(related_tests),
            "impact_score": impact_score,
            "overall_risk": overall_risk,
        },

        "impacted_components": impacted_components,

        "related_tests": related_tests,

        "limitations": [
            (
                "Impact is estimated from the available "
                "architecture graph."
            ),
            (
                "Missing graph relationships can cause "
                "affected components to be missed."
            ),
            (
                "The impact score is a heuristic, not a "
                "probability of failure."
            ),
            (
                "Related-test detection depends on test "
                "naming and graph connectivity."
            ),
            (
                "Static analysis cannot guarantee runtime behavior."
            ),
            (
                "Upstream dependency paths follow impact traversal "
                "in reverse graph direction."
            ),
        ],
    }
