import json
import os
import sys


# ============================================================
# BUILD REPOSITORY-SPECIFIC ARCHITECTURE GRAPH
# ============================================================

def build_graph(analysis_file):

    with open(
        analysis_file,
        "r",
        encoding="utf-8"
    ) as f:
        analysis = json.load(f)

    nodes = []
    edges = []

    # --------------------------------------------------------
    # Maps for resolving relationships
    # --------------------------------------------------------

    function_nodes = {}
    class_nodes = {}
    file_nodes = {}

    # --------------------------------------------------------
    # FILE NODES
    # --------------------------------------------------------

    for item in analysis:

        file_path = item["file"]

        file_id = f"file:{file_path}"

        file_nodes[file_path] = file_id

        nodes.append({
            "id": file_id,
            "type": "file",
            "label": os.path.basename(file_path)
        })

    # --------------------------------------------------------
    # IMPORT NODES
    # --------------------------------------------------------

    imported_modules = set()

    for item in analysis:

        file_path = item["file"]
        source_id = file_nodes[file_path]

        for imported in item.get("imports", []):

            # Example:
            # from payment import process_payment
            #
            # imported may be:
            # payment

            module_name = imported

            imported_modules.add(module_name)

            module_id = f"module:{module_name}"

            if not any(
                node["id"] == module_id
                for node in nodes
            ):
                nodes.append({
                    "id": module_id,
                    "type": "module",
                    "label": module_name
                })

            edges.append({
                "source": source_id,
                "target": module_id,
                "relationship": "imports"
            })

    # --------------------------------------------------------
    # CLASS NODES
    # --------------------------------------------------------

    for item in analysis:

        file_path = item["file"]

        file_id = file_nodes[file_path]

        for cls in item.get("classes", []):

            class_name = cls["name"]

            class_id = (
                f"class:{file_path}:{class_name}"
            )

            class_nodes[class_name] = class_id

            nodes.append({
                "id": class_id,
                "type": "class",
                "label": class_name
            })

            edges.append({
                "source": file_id,
                "target": class_id,
                "relationship": "contains"
            })

    # --------------------------------------------------------
    # FUNCTION NODES
    # --------------------------------------------------------

    for item in analysis:

        file_path = item["file"]

        file_id = file_nodes[file_path]

        for function in item.get(
            "functions",
            []
        ):

            function_name = function["name"]

            function_id = (
                f"function:{file_path}:{function_name}"
            )

            function_nodes.setdefault(
                function_name,
                []
            ).append(function_id)

            nodes.append({
                "id": function_id,
                "type": "function",
                "label": function_name
            })

            class_name = function.get(
                "class"
            )

            if class_name:

                class_id = class_nodes.get(
                    class_name
                )

                if class_id:

                    edges.append({
                        "source": class_id,
                        "target": function_id,
                        "relationship": "contains"
                    })

            else:

                edges.append({
                    "source": file_id,
                    "target": function_id,
                    "relationship": "contains"
                })

    # --------------------------------------------------------
    # CALL RELATIONSHIPS
    # --------------------------------------------------------

    for item in analysis:

        file_path = item["file"]

        for call in item.get(
            "calls",
            []
        ):

            called_name = call["name"]

            called_from = call.get(
                "called_from"
            )

            # Find source function
            source_candidates = []

            for function_name, function_ids in function_nodes.items():

                if function_name == called_from:

                    source_candidates.extend(
                        function_ids
                    )

            if not source_candidates:
                continue

            source_id = None

            # Prefer a function in the same file
            for candidate in source_candidates:

                if f"function:{file_path}:" in candidate:

                    source_id = candidate
                    break

            if source_id is None:

                source_id = source_candidates[0]

            # ------------------------------------------------
            # Resolve target function
            # ------------------------------------------------

            target_id = None

            candidates = function_nodes.get(
                called_name,
                []
            )

            # Prefer a function from another file
            # when the call is imported.
            for candidate in candidates:

                if candidate != source_id:
                    target_id = candidate
                    break

            if target_id:

                edges.append({
                    "source": source_id,
                    "target": target_id,
                    "relationship": "calls"
                })

    # --------------------------------------------------------
    # REMOVE DUPLICATE EDGES
    # --------------------------------------------------------

    unique_edges = []

    seen_edges = set()

    for edge in edges:

        key = (
            edge["source"],
            edge["target"],
            edge["relationship"]
        )

        if key not in seen_edges:

            seen_edges.add(key)

            unique_edges.append(edge)

    edges = unique_edges

    # --------------------------------------------------------
    # FINAL GRAPH
    # --------------------------------------------------------

    graph = {
        "nodes": nodes,
        "edges": edges
    }

    return graph


# ============================================================
# MAIN
# ============================================================

def main():

    if len(sys.argv) != 3:

        print(
            "Usage:\n"
            "python3 analyzer/build_graph.py "
            "<analysis_file> <output_file>"
        )

        sys.exit(1)

    analysis_file = sys.argv[1]
    output_file = sys.argv[2]

    graph = build_graph(
        analysis_file
    )

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            graph,
            f,
            indent=2
        )

    print(
        "Architecture graph created."
    )

    print(
        f"Input : {analysis_file}"
    )

    print(
        f"Output: {output_file}"
    )

    print(
        f"Nodes : {len(graph['nodes'])}"
    )

    print(
        f"Edges : {len(graph['edges'])}"
    )


if __name__ == "__main__":
    main()
