from analyzer.parsers.tree_sitter_parser import TreeSitterParser


def test_javascript_function_detection():
    parser = TreeSitterParser("javascript")
    result = parser.parse_file("tests/fixtures/sample.js")

    function_names = [
        function["name"]
        for function in result["functions"]
    ]

    assert "startServer" in function_names
    assert "greet" in function_names
    assert "add" in function_names


def test_javascript_function_arguments():
    parser = TreeSitterParser("javascript")
    result = parser.parse_file("tests/fixtures/sample.js")

    functions = {
        function["name"]: function["arguments"]
        for function in result["functions"]
    }

    assert functions["greet"] == ["name"]
    assert functions["add"] == ["a", "b"]
    assert functions["sum"] == ["...numbers"]


def test_javascript_constructor_detection():
    parser = TreeSitterParser("javascript")
    result = parser.parse_file("tests/fixtures/sample.js")

    constructors = [
        call for call in result["calls"]
        if call["call_type"] == "constructor"
    ]

    assert any(
        call["name"] == "UserService"
        for call in constructors
    )


def test_typescript_interface_detection():
    parser = TreeSitterParser("typescript")
    result = parser.parse_file("tests/fixtures/sample.ts")

    interface_names = [
        interface["name"]
        for interface in result["interfaces"]
    ]

    assert "User" in interface_names
    assert "Admin" in interface_names


def test_typescript_inheritance():
    parser = TreeSitterParser("typescript")
    result = parser.parse_file("tests/fixtures/sample.ts")

    assert {
        "class": "AdminService",
        "parent": "UserService",
        "line": 25,
    } in result["inheritance"]


def test_typescript_interface_implementation():
    parser = TreeSitterParser("typescript")
    result = parser.parse_file("tests/fixtures/sample.ts")

    assert {
        "class": "AdminService",
        "interface": "Admin",
        "line": 25,
    } in result["implementations"]
