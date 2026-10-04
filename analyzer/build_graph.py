import json
import os


ANALYSIS_FILE = "analysis.json"
OUTPUT_FILE = "architecture_graph.json"


def load_analysis():
    with open(ANALYSIS_FILE, "r") as f:
        return json.load(f)


def build_graph(analysis):
    nodes = []
    edges = []

    node_ids = set()

    # -----------------------------------------
    # Helper functions
    # -----------------------------------------

    def add_node(node_id, node_type, label, file=None):
        if node_id not in node_ids:
            node = {
                "id": node_id,
                "type": node_type,
                "label": label
            }

            if file:
                node["file"] = file

            nodes.append(node)
            node_ids.add(node_id)

    def add_edge(source, target, relationship):
        edges.append({
            "source": source,
            "target": target,
            "relationship": relationship
        })

    # -----------------------------------------
    # Build lookup tables
    # -----------------------------------------

    function_lookup = {}

    for file_info in analysis:

        file_path = file_info["file"]

        for function in file_info.get("functions", []):

            function_name = function["name"]

            function_id = f"function:{file_path}:{function_name}"

            function_lookup[function_name] = function_id

    # -----------------------------------------
    # Process files
    # -----------------------------------------

    for file_info in analysis:

        file_path = file_info["file"]

        file_id = f"file:{file_path}"

        add_node(
            file_id,
            "file",
            os.path.basename(file_path),
            file_path
        )

        # -------------------------------------
        # Imports
        # -------------------------------------

        for imported in file_info.get("imports", []):

            module_id = f"module:{imported}"

            add_node(
                module_id,
                "module",
                imported
            )

            add_edge(
                file_id,
                module_id,
                "imports"
            )

        # -------------------------------------
        # Classes
        # -------------------------------------

        for class_info in file_info.get("classes", []):

            class_name = class_info["name"]

            class_id = f"class:{file_path}:{class_name}"

            add_node(
                class_id,
                "class",
                class_name,
                file_path
            )

            add_edge(
                file_id,
                class_id,
                "contains"
            )

        # -------------------------------------
        # Functions
        # -------------------------------------

        for function in file_info.get("functions", []):

            function_name = function["name"]

            function_id = (
                f"function:{file_path}:{function_name}"
            )

            add_node(
                function_id,
                "function",
                function_name,
                file_path
            )

            class_name = function.get("class")

            if class_name:

                class_id = (
                    f"class:{file_path}:{class_name}"
                )

                add_edge(
                    class_id,
                    function_id,
                    "contains"
                )

            else:

                add_edge(
                    file_id,
                    function_id,
                    "contains"
                )

            # ---------------------------------
            # Function calls
            # ---------------------------------

            for call in file_info.get("calls", []):

                if call.get("called_from") != function_name:
                    continue

                called_name = call["name"]

                # Resolve function if known
                if called_name in function_lookup:

                    target_id = function_lookup[called_name]

                    add_edge(
                        function_id,
                        target_id,
                        "calls"
                    )

                else:

                    reference_id = (
                        f"reference:{called_name}"
                    )

                    add_node(
                        reference_id,
                        "function_reference",
                        called_name
                    )

                    add_edge(
                        function_id,
                        reference_id,
                        "calls"
                    )

    return {
        "nodes": nodes,
        "edges": edges
    }


def main():

    analysis = load_analysis()

    graph = build_graph(analysis)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(
            graph,
            f,
            indent=2
        )

    print("Architecture graph created.")

    print(
        f"Nodes: {len(graph['nodes'])}"
    )

    print(
        f"Edges: {len(graph['edges'])}"
    )

    print(
        f"Saved to: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
