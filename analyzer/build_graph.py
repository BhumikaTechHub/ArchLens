import json
import os


INPUT_FILE = "analysis.json"
OUTPUT_FILE = "architecture_graph.json"


def build_graph(analysis):

    nodes = []
    edges = []

    node_ids = set()

    def add_node(node_id, node_type, label):
        if node_id not in node_ids:
            nodes.append({
                "id": node_id,
                "type": node_type,
                "label": label
            })
            node_ids.add(node_id)

    def add_edge(source, target, relationship):
        edges.append({
            "source": source,
            "target": target,
            "relationship": relationship
        })

    for file_data in analysis:

        file_path = file_data["file"]

        # File node
        file_id = f"file:{file_path}"

        add_node(
            file_id,
            "file",
            os.path.basename(file_path)
        )

        # Imported modules
        for imported_module in file_data.get("imports", []):

            module_id = f"module:{imported_module}"

            add_node(
                module_id,
                "module",
                imported_module
            )

            add_edge(
                file_id,
                module_id,
                "imports"
            )

        # Classes
        for class_data in file_data.get("classes", []):

            class_name = class_data["name"]
            class_id = f"class:{file_path}:{class_name}"

            add_node(
                class_id,
                "class",
                class_name
            )

            add_edge(
                file_id,
                class_id,
                "contains"
            )

        # Functions
        for function_data in file_data.get("functions", []):

            function_name = function_data["name"]
            function_id = f"function:{file_path}:{function_name}"

            add_node(
                function_id,
                "function",
                function_name
            )

            class_name = function_data.get("class")

            if class_name:

                class_id = f"class:{file_path}:{class_name}"

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

        # Function calls
        for call in file_data.get("calls", []):

            called_name = call["name"]
            called_from = call.get("called_from")

            if not called_from:
                continue

            source_id = f"function:{file_path}:{called_from}"

            # We don't yet know which file contains the
            # called function, so create a reference node.
            target_id = f"call:{called_name}"

            add_node(
                target_id,
                "function_reference",
                called_name
            )

            add_edge(
                source_id,
                target_id,
                "calls"
            )

    return {
        "nodes": nodes,
        "edges": edges
    }


def main():

    with open(INPUT_FILE, "r", encoding="utf-8") as file:
        analysis = json.load(file)

    graph = build_graph(analysis)

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            graph,
            file,
            indent=2
        )

    print("Architecture graph created successfully.")
    print(f"Nodes: {len(graph['nodes'])}")
    print(f"Edges: {len(graph['edges'])}")
    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
