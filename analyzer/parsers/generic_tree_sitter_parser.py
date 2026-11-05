"""Non-Python parser adapter using Tree-sitter WebAssembly in an isolated Node process.

The Python process does not import the native Tree-sitter binding.
"""
import json
import subprocess
from pathlib import Path

from analyzer.parsers.base_parser import BaseParser


class GenericTreeSitterParser(BaseParser):
    def __init__(self, language: str):
        self.language = language
        self.script = Path(__file__).with_name(
            "generic_tree_sitter_parser.js"
        ).resolve()
        self.repo_root = self.script.parents[2]

    def parse_file(self, file_path: str) -> dict:
        path = Path(file_path).resolve()
        try:
            completed = subprocess.run(
                ["node", str(self.script), str(path), self.language],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
        except FileNotFoundError:
            return self._error_result(
                path, "Node.js is required for non-Python parsing. "
                "Install Node.js 18+ and run npm install in the ArchLens repository."
            )
        except subprocess.TimeoutExpired:
            return self._error_result(path, "WASM parser timed out after 90 seconds.")

        if completed.returncode != 0:
            return self._error_result(
                path, completed.stderr.strip()
                or f"WASM parser exited with code {completed.returncode}."
            )
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            return self._error_result(path, f"Parser returned invalid JSON: {error}")

        result.setdefault("interfaces", [])
        result.setdefault("inheritance", [])
        result.setdefault("implementations", [])
        result.setdefault("declaration_chunks", [])
        return result

    def _error_result(self, path: Path, message: str) -> dict:
        return {
            "file": str(path), "language": self.language,
            "imports": [], "import_details": [], "classes": [],
            "interfaces": [], "functions": [], "calls": [],
            "inheritance": [], "implementations": [],
            "declaration_chunks": [], "error": message,
        }
