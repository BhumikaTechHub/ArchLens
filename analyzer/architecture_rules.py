from collections import defaultdict, deque
from typing import Any


def normalize_node_id(value: Any) -> str:
    return str(value) if value is not None else ""


def get_node_label(node: dict) -> str:
    return str(
        node.get("label")
        or node.get("name")
        or node.get("id")
        or "Unknown component"
    )


def get_node_type(node: dict) -> str:
    return str(node.get("type") or "unknown").lower()


def get_node_path(node: dict) -> str:
    for key in ("file", "path", "file_path", "filename"):
        value = node.get(key)

        if isinstance(value, str) and value.strip():
            return value.replace("\\", "/")

    return ""


def normalize_graph(graph: dict[str, Any]):
    """Normalize graph nodes and edges for rule evaluation."""

    raw_nodes = graph.get("nodes", [])
    raw_edges = graph.get("edges", [])

    if not isinstance(raw_nodes, list):
        raise ValueError("Graph 'nodes' must be a list.")

    if not isinstance(raw_edges, list):
        raise ValueError("Graph 'edges' must be a list.")

    nodes = {}

    for node in raw_nodes:
        if not isinstance(node, dict):
            continue

        node_id = normalize_node_id(node.get("id"))

        if node_id:
            nodes[node_id] = node

    edges = []
    seen = set()

    for edge in raw_edges:
        if not isinstance(edge, dict):
            continue

        source = normalize_node_id(
            edge.get("source", edge.get("from"))
        )

        target = normalize_node_id(
            edge.get("target", edge.get("to"))
        )

        if source not in nodes or target not in nodes:
            continue

        relationship = str(
            edge.get("type")
            or edge.get("label")
            or edge.get("relationship")
            or "dependency"
        )

        key = (source, target, relationship)

        if key in seen:
            continue

        seen.add(key)

        edges.append(
            {
                "source": source,
                "target": target,
                "type": relationship,
            }
        )

    return nodes, edges


def build_adjacency(nodes, edges):
    outgoing = defaultdict(set)
    incoming = defaultdict(set)

    for node_id in nodes:
        outgoing[node_id]
        incoming[node_id]

    for edge in edges:
        source = edge["source"]
        target = edge["target"]

        outgoing[source].add(target)
        incoming[target].add(source)

    return outgoing, incoming


def find_strongly_connected_components(nodes, outgoing):
    """
    Tarjan's algorithm.

    Returns strongly connected components containing
    more than one node, plus single-node self-loops.
    """

    index = 0
    stack = []
    on_stack = set()

    indexes = {}
    lowlinks = {}

    cycles = []

    def strong_connect(node_id):
        nonlocal index

        indexes[node_id] = index
        lowlinks[node_id] = index

        index += 1

        stack.append(node_id)
        on_stack.add(node_id)

        for neighbor in outgoing[node_id]:

            if neighbor not in indexes:
                strong_connect(neighbor)

                lowlinks[node_id] = min(
                    lowlinks[node_id],
                    lowlinks[neighbor],
                )

            elif neighbor in on_stack:
                lowlinks[node_id] = min(
                    lowlinks[node_id],
                    indexes[neighbor],
                )

        if lowlinks[node_id] == indexes[node_id]:
            component = []

            while stack:
                member = stack.pop()
                on_stack.remove(member)

                component.append(member)

                if member == node_id:
                    break

            is_multi_node_cycle = len(component) > 1

            is_self_loop = (
                len(component) == 1
                and component[0] in outgoing[component[0]]
            )

            if is_multi_node_cycle or is_self_loop:
                cycles.append(component)

    for node_id in nodes:

        if node_id not in indexes:
            strong_connect(node_id)

    return cycles


def make_finding(
    rule_id,
    title,
    severity,
    description,
    affected_components,
    recommendation,
    evidence=None,
):
    return {
        "rule_id": rule_id,
        "title": title,
        "severity": severity,
        "description": description,
        "affected_components": affected_components,
        "recommendation": recommendation,
        "evidence": evidence or {},
    }


def analyze_architecture_rules(
    graph: dict[str, Any],
    high_coupling_threshold: int = 8,
    max_cycle_findings: int = 20,
    max_coupling_findings: int = 20,
):
    """
    Evaluate architecture rules against an existing graph.

    Severity meanings:
        critical: strong evidence of a structural problem
        high: potentially significant design concern
        medium: worth reviewing
        low: informational or minor concern

    These severities represent rule-based review priority,
    not measured production failure probabilities.
    """

    nodes, edges = normalize_graph(graph)

    outgoing, incoming = build_adjacency(nodes, edges)

    findings = []

    # --------------------------------------------------
    # Rule 1: Circular dependencies
    # --------------------------------------------------

    cycles = find_strongly_connected_components(
        nodes,
        outgoing,
    )

    for cycle in cycles[:max_cycle_findings]:

        affected = [
            {
                "id": node_id,
                "label": get_node_label(nodes[node_id]),
                "type": get_node_type(nodes[node_id]),
                "file": get_node_path(nodes[node_id]),
            }
            for node_id in sorted(cycle)
        ]

        cycle_labels = [
            get_node_label(nodes[node_id])
            for node_id in sorted(cycle)
        ]

        findings.append(
            make_finding(
                rule_id="ARCH001",
                title="Circular dependency detected",
                severity="high",
                description=(
                    "These components form a dependency cycle. "
                    "Changes to one component may affect other "
                    "components in the same cycle."
                ),
                affected_components=affected,
                recommendation=(
                    "Review the dependency direction. Consider "
                    "introducing an abstraction, moving shared "
                    "responsibilities into a separate component, "
                    "or restructuring the dependency flow."
                ),
                evidence={
                    "component_count": len(cycle),
                    "components": cycle_labels,
                },
            )
        )

    # --------------------------------------------------
    # Rule 2: High coupling
    # --------------------------------------------------

    coupling_results = []

    for node_id, node in nodes.items():

        incoming_count = len(incoming[node_id])
        outgoing_count = len(outgoing[node_id])

        # Count unique neighboring components.
        total_connections = len(
            incoming[node_id] | outgoing[node_id]
        )

        if total_connections >= high_coupling_threshold:

            coupling_results.append(
                {
                    "id": node_id,
                    "label": get_node_label(node),
                    "type": get_node_type(node),
                    "file": get_node_path(node),
                    "incoming_dependencies": incoming_count,
                    "outgoing_dependencies": outgoing_count,
                    "total_connections": total_connections,
                }
            )

    coupling_results.sort(
        key=lambda item: item["total_connections"],
        reverse=True,
    )

    for component in coupling_results[:max_coupling_findings]:

        findings.append(
            make_finding(
                rule_id="ARCH002",
                title="Highly connected component",
                severity="medium",
                description=(
                    f"This component has "
                    f"{component['total_connections']} unique "
                    "connected components in the dependency graph."
                ),
                affected_components=[
                    {
                        "id": component["id"],
                        "label": component["label"],
                        "type": component["type"],
                        "file": component["file"],
                    }
                ],
                recommendation=(
                    "Review whether this component has too many "
                    "responsibilities. Consider separating unrelated "
                    "concerns or introducing clearer interfaces."
                ),
                evidence={
                    "incoming_dependencies": component[
                        "incoming_dependencies"
                    ],
                    "outgoing_dependencies": component[
                        "outgoing_dependencies"
                    ],
                    "total_connections": component[
                        "total_connections"
                    ],
                    "threshold": high_coupling_threshold,
                },
            )
        )

    # --------------------------------------------------
    # Rule 3: Isolated components
    # --------------------------------------------------

    isolated_components = []

    for node_id, node in nodes.items():

        if not incoming[node_id] and not outgoing[node_id]:

            isolated_components.append(
                {
                    "id": node_id,
                    "label": get_node_label(node),
                    "type": get_node_type(node),
                    "file": get_node_path(node),
                }
            )

    if isolated_components:

        findings.append(
            make_finding(
                rule_id="ARCH003",
                title="Isolated components detected",
                severity="low",
                description=(
                    f"{len(isolated_components)} components have "
                    "no incoming or outgoing relationships in the "
                    "current architecture graph."
                ),
                affected_components=isolated_components[:50],
                recommendation=(
                    "Verify whether these components are genuinely "
                    "independent or whether the analyzer missed "
                    "relationships. Entry points, configuration "
                    "files, tests, and dynamically loaded modules "
                    "may legitimately appear isolated."
                ),
                evidence={
                    "isolated_component_count": len(
                        isolated_components
                    ),
                },
            )
        )

    # --------------------------------------------------
    # Rule 4: Dependency concentration
    # --------------------------------------------------

    # Flag components with unusually many outgoing dependencies
    # separately from high total connectivity.

    outgoing_counts = {
        node_id: len(outgoing[node_id])
        for node_id in nodes
    }

    if outgoing_counts:

        maximum_outgoing = max(outgoing_counts.values())

        if maximum_outgoing >= high_coupling_threshold:

            most_dependent = [
                {
                    "id": node_id,
                    "label": get_node_label(nodes[node_id]),
                    "type": get_node_type(nodes[node_id]),
                    "file": get_node_path(nodes[node_id]),
                }
                for node_id, count in outgoing_counts.items()
                if count == maximum_outgoing
            ]

            findings.append(
                make_finding(
                    rule_id="ARCH004",
                    title="High outgoing dependency count",
                    severity="medium",
                    description=(
                        "At least one component directly depends on "
                        f"{maximum_outgoing} other components. "
                        "This can increase coordination and change "
                        "complexity."
                    ),
                    affected_components=most_dependent,
                    recommendation=(
                        "Review whether the component coordinates "
                        "too many responsibilities. Consider grouping "
                        "related functionality behind focused interfaces."
                    ),
                    evidence={
                        "maximum_outgoing_dependencies": maximum_outgoing,
                        "threshold": high_coupling_threshold,
                    },
                )
            )

    # --------------------------------------------------
    # Rule 5: Basic graph integrity
    # --------------------------------------------------

    invalid_edges = []

    valid_node_ids = set(nodes)

    raw_edges = graph.get("edges", [])

    if isinstance(raw_edges, list):

        for edge in raw_edges:

            if not isinstance(edge, dict):
                continue

            source = normalize_node_id(
                edge.get("source", edge.get("from"))
            )

            target = normalize_node_id(
                edge.get("target", edge.get("to"))
            )

            if (
                not source
                or not target
                or source not in valid_node_ids
                or target not in valid_node_ids
            ):
                invalid_edges.append(
                    {
                        "source": source or None,
                        "target": target or None,
                    }
                )

    if invalid_edges:

        findings.append(
            make_finding(
                rule_id="ARCH005",
                title="Invalid graph relationships",
                severity="medium",
                description=(
                    f"{len(invalid_edges)} graph relationships "
                    "reference missing or invalid components."
                ),
                affected_components=[],
                recommendation=(
                    "Review graph generation and ensure that every "
                    "relationship references an existing component ID."
                ),
                evidence={
                    "invalid_edge_count": len(invalid_edges),
                    "examples": invalid_edges[:10],
                },
            )
        )

    # --------------------------------------------------
    # Prioritize findings
    # --------------------------------------------------

    severity_order = {
        "critical": 0,
        "high": 1,
        "medium": 2,
        "low": 3,
    }

    findings.sort(
        key=lambda finding: (
            severity_order.get(finding["severity"], 99),
            finding["rule_id"],
            finding["title"],
        )
    )

    severity_counts = defaultdict(int)

    for finding in findings:
        severity_counts[finding["severity"]] += 1

    # --------------------------------------------------
    # Calculate a transparent heuristic score
    # --------------------------------------------------

    # This is a rule-based indicator, not a certified
    # architecture quality measurement.
    penalty_weights = {
        "critical": 20,
        "high": 10,
        "medium": 5,
        "low": 1,
    }

    total_penalty = sum(
        penalty_weights.get(finding["severity"], 0)
        for finding in findings
    )

    health_score = max(0, 100 - total_penalty)

    return {
        "health": {
            "score": health_score,
            "label": (
                "Needs attention"
                if health_score < 60
                else "Review recommended"
                if health_score < 80
                else "Good"
            ),
            "method": (
                "Heuristic score: 100 minus severity-weighted "
                "architecture rule findings. It is not a validated "
                "measure of software quality."
            ),
        },
        "summary": {
            "total_findings": len(findings),
            "critical": severity_counts["critical"],
            "high": severity_counts["high"],
            "medium": severity_counts["medium"],
            "low": severity_counts["low"],
            "circular_dependency_groups": len(cycles),
            "isolated_components": len(isolated_components),
            "high_coupling_components": len(coupling_results),
        },
        "findings": findings,
    }
