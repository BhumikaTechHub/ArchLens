import ast
import os
import json
import sys


OUTPUT_FILE = "code_chunks.json"


def create_chunks(repository_path):

    chunks = []

    for root, dirs, files in os.walk(repository_path):

        dirs[:] = [
            d for d in dirs
            if d not in {
                ".git",
                "__pycache__",
                "venv",
                ".venv",
                "node_modules"
            }
        ]

        for filename in files:

            if not filename.endswith(".py"):
                continue

            file_path = os.path.join(root, filename)

            try:
                with open(
                    file_path,
                    "r",
                    encoding="utf-8"
                ) as file:
                    source = file.read()

                tree = ast.parse(source)

                # File-level chunk
                chunks.append({
                    "id": f"{file_path}:file",
                    "text": source,
                    "metadata": {
                        "file": file_path,
                        "type": "file",
                        "name": filename
                    }
                })

                # Function/class chunks
                for node in ast.walk(tree):

                    if isinstance(
                        node,
                        (
                            ast.FunctionDef,
                            ast.AsyncFunctionDef,
                            ast.ClassDef
                        )
                    ):

                        segment = ast.get_source_segment(
                            source,
                            node
                        )

                        if not segment:
                            continue

                        if isinstance(node, ast.ClassDef):
                            node_type = "class"
                        else:
                            node_type = "function"

                        chunks.append({
                            "id": f"{file_path}:{node_type}:{node.name}:{node.lineno}",
                            "text": segment,
                            "metadata": {
                                "file": file_path,
                                "type": node_type,
                                "name": node.name,
                                "line": node.lineno
                            }
                       })

            except Exception as error:

                print(
                    f"Could not analyze {file_path}: {error}"
                )

    return chunks


def main():

    if len(sys.argv) != 2:
        print(
            "Usage: python create_code_chunks.py <repository_path>"
        )
        sys.exit(1)

    repository_path = sys.argv[1]

    chunks = create_chunks(repository_path)

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            chunks,
            file,
            indent=2
        )

    print("Code chunking completed.")
    print(f"Total chunks: {len(chunks)}")
    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
