import ast
import os
import json
import sys


class CodeAnalyzer(ast.NodeVisitor):

    def __init__(self):
        self.imports = []
        self.classes = []
        self.functions = []
        self.calls = []
        self.import_details = []
        self.instantiations = []


        self.current_class = None
        self.current_function = None
        self.current_function_line = None

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append(alias.name)

            self.import_details.append({
                "type": "import",
                "module": alias.name,
                "name": None,
                "alias": alias.asname,
                "line": node.lineno,
                "level": 0
            })

        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            self.imports.append(node.module)

        for alias in node.names:
            self.import_details.append({
                "type": "from_import",
                "module": node.module,
                "name": alias.name,
                "alias": alias.asname,
                "line": node.lineno,
                "level": node.level
            })

        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.classes.append({
            "name": node.name,
            "line": node.lineno
        })

        previous_class = self.current_class
        self.current_class = node.name

        self.generic_visit(node)

        self.current_class = previous_class
    def visit_FunctionDef(self, node):
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node):
        self._visit_function(node)

    def _visit_function(self, node):
        function_info = {
            "name": node.name,
            "line": node.lineno,
            "arguments": [
                arg.arg for arg in node.args.posonlyargs
                + node.args.args
                + node.args.kwonlyargs
            ],
            "class": self.current_class
        }

        self.functions.append(function_info)

        previous_function = self.current_function
        previous_line = self.current_function_line

        self.current_function = node.name
        self.current_function_line = node.lineno

        self.generic_visit(node)

        self.current_function = previous_function
        self.current_function_line = previous_line

    def _record_instantiation(self, target, value, line):
        if not isinstance(value, ast.Call):
            return
        if isinstance(value.func, ast.Name):
            class_name = value.func.id
        elif isinstance(value.func, ast.Attribute):
            try:
                class_name = ast.unparse(value.func)
            except Exception:
                return
        else:
            return
        if not isinstance(target, ast.Name):
            return
        if not hasattr(self, "instantiations"):
            self.instantiations = []
        self.instantiations.append({
            "variable": target.id,
            "class_name": class_name,
            "line": line,
            "scope_function": self.current_function,
            "scope_class": self.current_class,
        })

    def visit_Assign(self, node):
        for target in node.targets:
            self._record_instantiation(target, node.value, node.lineno)
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        self._record_instantiation(node.target, node.value, node.lineno)
        self.generic_visit(node)

    def visit_Call(self, node):
        call_name = None
        call_type = None
        call_expression = None
        receiver = None

        try:
            call_expression = ast.unparse(node.func)
        except Exception:
            call_expression = None

        if isinstance(node.func, ast.Name):
            call_name = node.func.id
            call_type = "direct"

        elif isinstance(node.func, ast.Attribute):
            call_name = node.func.attr
            call_type = "attribute"

            try:
                receiver = ast.unparse(node.func.value)
            except Exception:
                receiver = None

        if call_name:
            self.calls.append({
                "name": call_name,
                "called_from": self.current_function,
                "called_from_line": self.current_function_line,
                "called_from_class": self.current_class,
                "line": node.lineno,
                "call_type": call_type,
                "expression": call_expression,
                "receiver": receiver
            })

        self.generic_visit(node)


def analyze_python_file(file_path):
    result = {
        "file": file_path,
        "imports": [],
        "classes": [],
        "functions": [],
        "calls": []
    }

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            source_code = file.read()

        tree = ast.parse(source_code)

        analyzer = CodeAnalyzer()
        analyzer.visit(tree)

        result["imports"] = analyzer.imports
        result["import_details"] = analyzer.import_details
        result["classes"] = analyzer.classes
        result["functions"] = analyzer.functions
        result["calls"] = analyzer.calls
        result["instantiations"] = analyzer.instantiations

    except Exception as error:
        result["error"] = str(error)

    return result


def analyze_repository(repository_path):
    from analyzer.language_support import LANGUAGE_BY_EXTENSION
    from analyzer.parsers.python_parser import PythonParser
    from analyzer.parsers.tree_sitter_parser import TreeSitterParser
    from analyzer.parsers.generic_tree_sitter_parser import GenericTreeSitterParser

    python_parser = PythonParser()
    parser_cache = {}

    def parser_for(extension):
        language = LANGUAGE_BY_EXTENSION.get(extension)
        if not language:
            return None
        if language == "python":
            return python_parser
        if language in {"javascript", "typescript", "tsx"}:
            key = language
            if key not in parser_cache:
                parser_cache[key] = TreeSitterParser(language)
            return parser_cache[key]
        if language == "tsx":
            key = "tsx"
        else:
            key = language
        if key not in parser_cache:
            parser_cache[key] = GenericTreeSitterParser(key)
        return parser_cache[key]

    results = []
    ignored_dirs = {
        ".git", "__pycache__", "venv", ".venv", "node_modules",
        "vendor", "dist", "build", "target", ".next",
    }

    for root, dirs, files in os.walk(repository_path):
        dirs[:] = [directory for directory in dirs if directory not in ignored_dirs]
        for filename in files:
            extension = os.path.splitext(filename)[1].lower()
            language = LANGUAGE_BY_EXTENSION.get(extension)

            # Repositories contain many non-source files (JSON, YAML, Markdown,
            # images, lockfiles, etc.). Analyze only registered source extensions.
            if not language:
                continue

            file_path = os.path.join(root, filename)
            try:
                parser = parser_for(extension)
                results.append(parser.parse_file(file_path))
            except Exception as error:
                # An unavailable grammar or malformed source must not abort
                # analysis of every other supported file in the repository.
                results.append({
                    "file": file_path,
                    "language": language,
                    "imports": [],
                    "import_details": [],
                    "classes": [],
                    "interfaces": [],
                    "functions": [],
                    "calls": [],
                    "inheritance": [],
                    "implementations": [],
                    "error": str(error),
                })

    return results

def main():
    if len(sys.argv) != 2:
        print(
            "Usage: python repository_analyzer.py <repository_path>"
        )
        sys.exit(1)

    repository_path = sys.argv[1]

    if not os.path.isdir(repository_path):
        print(f"Repository not found: {repository_path}")
        sys.exit(1)

    results = analyze_repository(repository_path)

    output_file = "analysis.json"

    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(results, file, indent=2)

    print("Repository analyzed successfully.")
    print(f"Source files analyzed: {len(results)}")
    print(f"Analysis saved to: {output_file}")


if __name__ == "__main__":
    main()
