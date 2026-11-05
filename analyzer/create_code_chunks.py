import ast
import json
import os
import sys
from pathlib import Path


from analyzer.language_support import LANGUAGE_BY_EXTENSION
from analyzer.parsers.tree_sitter_parser import TreeSitterParser
from analyzer.parsers.generic_tree_sitter_parser import GenericTreeSitterParser


IGNORE_DIRS = {
    ".git", "__pycache__", "venv", ".venv", "node_modules",
    "vendor", "dist", "build", "target", ".next",
}


def _python_chunks(source, relative_path, repo_name):
    chunks = []
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return chunks

    parent_map = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parent_map[child] = parent

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            code = ast.get_source_segment(source, node) or ""
            if code.strip():
                chunks.append({
                    "document": code,
                    "metadata": {
                        "repository": repo_name, "file": relative_path,
                        "language": "python", "type": "class",
                        "name": node.name, "line": node.lineno,
                        "end_line": node.end_lineno,
                    },
                })
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            code = ast.get_source_segment(source, node) or ""
            parent = parent_map.get(node)
            while parent and not isinstance(parent, ast.ClassDef):
                parent = parent_map.get(parent)
            class_name = parent.name if parent else None
            if code.strip():
                chunks.append({
                    "document": code,
                    "metadata": {
                        "repository": repo_name, "file": relative_path,
                        "language": "python", "type": "function",
                        "name": node.name, "class_name": class_name,
                        "qualified_name": (
                            f"{class_name}.{node.name}" if class_name else node.name
                        ),
                        "line": node.lineno, "end_line": node.end_lineno,
                    },
                })
    return chunks


def create_chunks(repository_path):
    """Create language-aware file and declaration chunks for a repository."""
    repository_path = os.path.abspath(repository_path)
    repo_name = os.path.basename(repository_path)
    chunks = []

    for root, dirs, files in os.walk(repository_path):
        dirs[:] = [directory for directory in dirs if directory not in IGNORE_DIRS]

        for filename in files:
            extension = Path(filename).suffix.lower()
            language = LANGUAGE_BY_EXTENSION.get(extension)
            if not language:
                continue

            file_path = os.path.join(root, filename)
            relative_path = os.path.relpath(file_path, repository_path)

            try:
                source_bytes = Path(file_path).read_bytes()
                source = source_bytes.decode("utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            if not source.strip():
                continue

            # File-level context supports questions that span declarations.
            chunks.append({
                "document": source,
                "metadata": {
                    "repository": repo_name,
                    "file": relative_path,
                    "language": language,
                    "type": "file",
                    "name": filename,
                    "line": 1,
                },
            })

            if language == "python":
                chunks.extend(_python_chunks(source, relative_path, repo_name))
            elif language in {"javascript", "typescript", "tsx"}:
                parsed = TreeSitterParser(language).parse_file(file_path)
                for declaration in parsed.get("declaration_chunks", []):
                    chunks.append({
                        "document": declaration["code"],
                        "metadata": {
                            "repository": repo_name,
                            "file": relative_path,
                            "language": language,
                            "type": declaration["type"],
                            "name": declaration["name"],
                            "class_name": declaration.get("class_name"),
                            "qualified_name": (
                                str(declaration["class_name"]) + "." + str(declaration["name"])
                                if declaration.get("class_name")
                                and declaration["type"] == "function"
                                else declaration["name"]
                            ),
                            "line": declaration["line"],
                            "end_line": declaration["end_line"],
                            "parse_errors": bool(parsed.get("parse_errors", False)),
                        },
                    })
                if parsed.get("error"):
                    print(
                        "JavaScript/TypeScript chunking skipped declarations in "
                        + relative_path + ": " + parsed["error"]
                    )
            else:
                parsed = GenericTreeSitterParser(language).parse_file(file_path)
                for declaration in parsed.get("declaration_chunks", []):
                    chunks.append({
                        "document": declaration["code"],
                        "metadata": {
                            "repository": repo_name,
                            "file": relative_path,
                            "language": language,
                            "type": declaration["type"],
                            "name": declaration["name"],
                            "class_name": declaration.get("class_name"),
                            "qualified_name": (
                                str(declaration["class_name"]) + "." + str(declaration["name"])
                                if declaration.get("class_name")
                                and declaration["type"] == "function"
                                else declaration["name"]
                            ),
                            "line": declaration["line"],
                            "end_line": declaration["end_line"],
                            "parse_errors": bool(parsed.get("parse_errors", False)),
                        },
                    })
                if parsed.get("error"):
                    print("WASM chunking skipped declarations in "
                          + relative_path + ": " + parsed["error"])

    return chunks


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 analyzer/create_code_chunks.py <repository_path>")
        sys.exit(1)

    repository_path = sys.argv[1]
    if not os.path.isdir(repository_path):
        print(f"Repository not found: {repository_path}")
        sys.exit(1)

    repo_name = os.path.basename(os.path.abspath(repository_path))
    chunks = create_chunks(repository_path)
    output_file = f"code_chunks_{repo_name}.json"

    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(chunks, file, indent=2)

    print("Code chunking completed.")
    print(f"Repository: {repo_name}")
    print(f"Total chunks: {len(chunks)}")
    print(f"Languages: {', '.join(sorted({c['metadata']['language'] for c in chunks}))}")
    print(f"Saved to: {output_file}")


if __name__ == "__main__":
    main()
