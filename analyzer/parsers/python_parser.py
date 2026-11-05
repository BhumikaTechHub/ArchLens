from analyzer.parsers.base_parser import BaseParser
from analyzer.repository_analyzer import analyze_python_file


class PythonParser(BaseParser):

    def parse_file(self, file_path: str) -> dict:
        result = analyze_python_file(file_path)

        result["language"] = "python"

        result.setdefault("inheritance", [])
        result.setdefault("implementations", [])
        result.setdefault("interfaces", [])
        result.setdefault("instantiations", [])

        return result
