"""JavaScript/TypeScript parser backed by the official TypeScript compiler API.

Requires Node.js and the pinned TypeScript npm dependency (npm install).
"""
import json
import subprocess
from pathlib import Path

from analyzer.parsers.base_parser import BaseParser


class TreeSitterParser(BaseParser):
    """Compatibility name retained for existing imports; no Tree-sitter is used."""

    def __init__(self, language: str):
        if language not in {"javascript", "typescript", "tsx"}:
            raise ValueError(f"Unsupported language: {language}")
        self.language = language
        self.script = (
            Path(__file__).with_name("typescript_ast_parser.js").resolve()
        )
        self.repo_root = self.script.parents[2]

    def parse_file(self, file_path: str) -> dict:
        path = Path(file_path).resolve()
        try:
            completed = subprocess.run(
                ["node", str(self.script), str(path), self.language],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except FileNotFoundError:
            return self._error_result(
                path, "Node.js is required for JavaScript/TypeScript analysis. "
                "Install Node.js, then run npm install in the ArchLens repository."
            )
        except subprocess.TimeoutExpired:
            return self._error_result(
                path, "JavaScript/TypeScript parser timed out after 60 seconds."
            )

        if completed.returncode != 0:
            message = completed.stderr.strip() or (
                f"TypeScript parser exited with code {completed.returncode}."
            )
            return self._error_result(path, message)

        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            return self._error_result(
                path, f"Parser returned invalid JSON: {error}"
            )

        # Preserve the existing normalized record contract consumed by
        # build_graph.py and the repository evaluation script.
        result.setdefault("interfaces", [])
        result.setdefault("inheritance", [])
        result.setdefault("implementations", [])
        result.setdefault("instantiations", [])
        return result

    def _error_result(self, path: Path, message: str) -> dict:
        return {
            "file": str(path),
            "language": self.language,
            "imports": [],
            "import_details": [],
            "classes": [],
            "interfaces": [],
            "functions": [],
            "calls": [],
            "inheritance": [],
            "implementations": [],
            "declaration_chunks": [],
            "error": message,
        }
