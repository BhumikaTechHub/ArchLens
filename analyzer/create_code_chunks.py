import ast
import json
import os
import sys


IGNORE_DIRS = {
    ".git",
    "__pycache__",
    "venv",
    ".venv",
    "node_modules"
}


def get_source_segment(source, node):
    """
    Get the exact source code for an AST node.
    """
    try:
        segment = ast.get_source_segment(source, node)
        return segment if segment else ""
    except Exception:
        return ""


def create_chunks(repository_path):
    """
    Create code-aware chunks from a Python repository.
    """

    repository_path = os.path.abspath(repository_path)
    repo_name = os.path.basename(repository_path)

    chunks = []

    for root, dirs, files in os.walk(repository_path):

        # Ignore unnecessary directories
        dirs[:] = [
            d for d in dirs
            if d not in IGNORE_DIRS
        ]

        for filename in files:

            if not filename.endswith(".py"):
                continue

            file_path = os.path.join(root, filename)

            # Relative path inside repository
            relative_path = os.path.relpath(
                file_path,
                repository_path
            )

            try:
                with open(
                    file_path,
                    "r",
                    encoding="utf-8"
                ) as f:
                    source = f.read()

                tree = ast.parse(source)

            except Exception as e:
                print(
                    f"Could not analyze {file_path}: {e}"
                )
                continue

            # -------------------------------------------------
            # FILE CHUNK
            # -------------------------------------------------

            if source.strip():

                chunks.append({
                    "document": source,
                    "metadata": {
                        "repository": repo_name,
                        "file": relative_path,
                        "type": "file",
                        "name": filename,
                        "line": 1
                    }
                })

            # -------------------------------------------------
            # CLASS + FUNCTION CHUNKS
            # -------------------------------------------------

            for node in ast.walk(tree):

                # -----------------------------
                # CLASS
                # -----------------------------

                if isinstance(node, ast.ClassDef):

                    class_code = get_source_segment(
                        source,
                        node
                    )

                    if class_code.strip():

                        chunks.append({
                            "document": class_code,
                            "metadata": {
                                "repository": repo_name,
                                "file": relative_path,
                                "type": "class",
                                "name": node.name,
                                "line": node.lineno
                            }
                        })

                # -----------------------------
                # FUNCTION
                # -----------------------------

                elif isinstance(
                    node,
                    (ast.FunctionDef, ast.AsyncFunctionDef)
                ):

                    function_code = get_source_segment(
                        source,
                        node
                    )

                    if function_code.strip():

                        chunks.append({
                            "document": function_code,
                            "metadata": {
                                "repository": repo_name,
                                "file": relative_path,
                                "type": "function",
                                "name": node.name,
                                "line": node.lineno
                            }
                        })

    return chunks


def main():

    # ---------------------------------------------------------
    # COMMAND-LINE ARGUMENT
    # ---------------------------------------------------------

    if len(sys.argv) < 2:

        print(
            "Usage: python3 analyzer/create_code_chunks.py "
            "<repository_path>"
        )

        sys.exit(1)

    repository_path = sys.argv[1]

    # ---------------------------------------------------------
    # VALIDATE REPOSITORY
    # ---------------------------------------------------------

    if not os.path.isdir(repository_path):

        print(
            f"Repository not found: {repository_path}"
        )

        sys.exit(1)

    # Repository name
    repo_name = os.path.basename(
        os.path.abspath(repository_path)
    )

    # ---------------------------------------------------------
    # CREATE CHUNKS
    # ---------------------------------------------------------

    chunks = create_chunks(repository_path)

    # ---------------------------------------------------------
    # OUTPUT FILE
    # ---------------------------------------------------------

    output_file = f"code_chunks_{repo_name}.json"

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            chunks,
            f,
            indent=2
        )

    # ---------------------------------------------------------
    # SUMMARY
    # ---------------------------------------------------------

    print("Code chunking completed.")
    print(f"Repository: {repo_name}")
    print(f"Total chunks: {len(chunks)}")
    print(f"Saved to: {output_file}")


if __name__ == "__main__":
    main()
