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

        self.current_class = None
        self.current_function = None

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append(alias.name)

        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            self.imports.append(node.module)

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
        function_info = {
            "name": node.name,
            "line": node.lineno,
            "arguments": [
                arg.arg for arg in node.args.args
            ],
            "class": self.current_class
        }

        self.functions.append(function_info)

        previous_function = self.current_function
        self.current_function = node.name

        self.generic_visit(node)

        self.current_function = previous_function

    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)

    def visit_Call(self, node):

        call_name = None

        if isinstance(node.func, ast.Name):
            call_name = node.func.id

        elif isinstance(node.func, ast.Attribute):
            call_name = node.func.attr

        if call_name:
            self.calls.append({
                "name": call_name,
                "called_from": self.current_function
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
        result["classes"] = analyzer.classes
        result["functions"] = analyzer.functions
        result["calls"] = analyzer.calls

    except Exception as error:

        result["error"] = str(error)

    return result


def analyze_repository(repository_path):

    results = []

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

            if filename.endswith(".py"):

                file_path = os.path.join(root, filename)

                analysis = analyze_python_file(file_path)

                results.append(analysis)

    return results


def main():

    if len(sys.argv) != 2:

        print(
            "Usage: python repository_analyzer.py <repository_path>"
        )

        sys.exit(1)

    repository_path = sys.argv[1]

    if not os.path.isdir(repository_path):

        print(
            f"Repository not found: {repository_path}"
        )

        sys.exit(1)

    results = analyze_repository(repository_path)

    output_file = "analysis.json"

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            results,
            file,
            indent=2
        )

    print("Repository analyzed successfully.")
    print(f"Python files found: {len(results)}")
    print(f"Analysis saved to: {output_file}")


if __name__ == "__main__":
    main()
