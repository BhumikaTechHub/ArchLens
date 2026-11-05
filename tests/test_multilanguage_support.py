from pathlib import Path

from analyzer.create_code_chunks import create_chunks
from analyzer.repository_analyzer import analyze_repository


SAMPLES = {
    "sample.java": "class UserService { String getUser(int id) { return \"user\"; } }",
    "sample.cs": "class UserService { public string GetUser(int id) { return \"user\"; } }",
    "sample.go": "package main\ntype UserService struct {}\nfunc (s UserService) GetUser(id int) string { return \"user\" }",
    "sample.c": "struct User { int id; };\nint get_user(int id) { return id; }",
    "sample.cpp": "class UserService { public: int getUser(int id) { return id; } };",
    "sample.rs": "struct User { id: i32 }\nfn get_user(id: i32) -> i32 { id }",
    "sample.php": "<?php class UserService { public function getUser($id) { return $id; } }",
    "sample.rb": "class UserService\n  def get_user(id)\n    id\n  end\nend",
    "sample.kt": "class UserService { fun getUser(id: Int): Int { return id } }",
    "sample.swift": "class UserService { func getUser(id: Int) -> Int { return id } }",
}


def test_repository_analyzer_recognizes_additional_languages(tmp_path):
    for filename, source in SAMPLES.items():
        (tmp_path / filename).write_text(source, encoding="utf-8")

    results = analyze_repository(str(tmp_path))
    languages = {item["language"] for item in results}

    assert {
        "java", "csharp", "go", "c", "cpp",
        "rust", "php", "ruby", "kotlin", "swift",
    } <= languages
    errors = [(item["language"], item.get("error")) for item in results if item.get("error")]
    assert not errors, errors


def test_chunker_creates_language_tagged_chunks(tmp_path):
    for filename, source in SAMPLES.items():
        (tmp_path / filename).write_text(source, encoding="utf-8")

    chunks = create_chunks(str(tmp_path))
    languages = {chunk["metadata"]["language"] for chunk in chunks}

    assert len(chunks) >= len(SAMPLES)
    assert {
        "java", "csharp", "go", "c", "cpp",
        "rust", "php", "ruby", "kotlin", "swift",
    } <= languages
    assert all(chunk["document"].strip() for chunk in chunks)

    declaration_languages = {
        chunk["metadata"]["language"]
        for chunk in chunks
        if chunk["metadata"]["type"] in {"class", "function"}
    }
    assert {
        "java", "csharp", "go", "c", "cpp",
        "rust", "php", "ruby", "kotlin", "swift",
    } <= declaration_languages


def test_javascript_and_typescript_receive_language_tagged_chunks():
    chunks = create_chunks("tests/fixtures")
    languages = {chunk["metadata"]["language"] for chunk in chunks}

    assert "javascript" in languages
    assert "typescript" in languages
    assert all(chunk["metadata"].get("file") for chunk in chunks)


def test_build_graph_resolves_unique_cross_file_inheritance_and_implementation(tmp_path):
    import json

    from analyzer.build_graph import build_graph

    analysis = [
        {
            "file": str(tmp_path / "base.py"), "language": "python",
            "imports": [], "classes": [{"name": "BaseService", "line": 1}],
            "interfaces": [{"name": "ServiceContract", "line": 2}],
            "functions": [], "calls": [], "inheritance": [],
            "implementations": [],
        },
        {
            "file": str(tmp_path / "implementation.py"), "language": "python",
            "imports": [], "classes": [{"name": "UserService", "line": 1}],
            "interfaces": [], "functions": [], "calls": [],
            "inheritance": [{"class": "UserService", "parent": "BaseService", "line": 1}],
            "implementations": [{"class": "UserService", "interface": "ServiceContract", "line": 1}],
        },
    ]
    analysis_file = tmp_path / "analysis.json"
    analysis_file.write_text(json.dumps(analysis), encoding="utf-8")

    graph = build_graph(str(analysis_file))
    relationships = {
        (edge["relationship"], edge["source"], edge["target"])
        for edge in graph["edges"]
    }

    child = f"class:{analysis[1]['file']}:UserService:1"
    parent = f"class:{analysis[0]['file']}:BaseService:1"
    interface = f"interface:{analysis[0]['file']}:ServiceContract:2"
    assert ("extends", child, parent) in relationships
    assert ("implements", child, interface) in relationships
    assert not graph["unresolved_relationships"]


def test_build_graph_does_not_guess_ambiguous_cross_file_parent(tmp_path):
    import json

    from analyzer.build_graph import build_graph

    analysis = [
        {
            "file": str(tmp_path / "one.py"), "language": "python",
            "imports": [], "classes": [{"name": "Base", "line": 1}],
            "interfaces": [], "functions": [], "calls": [],
            "inheritance": [], "implementations": [],
        },
        {
            "file": str(tmp_path / "two.py"), "language": "python",
            "imports": [], "classes": [{"name": "Base", "line": 1}],
            "interfaces": [], "functions": [], "calls": [],
            "inheritance": [], "implementations": [],
        },
        {
            "file": str(tmp_path / "child.py"), "language": "python",
            "imports": [], "classes": [{"name": "Child", "line": 1}],
            "interfaces": [], "functions": [], "calls": [],
            "inheritance": [{"class": "Child", "parent": "Base", "line": 1}],
            "implementations": [],
        },
    ]
    analysis_file = tmp_path / "analysis.json"
    analysis_file.write_text(json.dumps(analysis), encoding="utf-8")

    graph = build_graph(str(analysis_file))
    assert not [
        edge for edge in graph["edges"]
        if edge["relationship"] == "extends"
        and edge["source"].endswith(":Child:1")
    ]
    assert {
        "file": analysis[2]["file"], "kind": "extends",
        "source": "Child", "target": "Base", "reason": "ambiguous_target",
    } in graph["unresolved_relationships"]


def test_build_graph_prefers_same_file_parent_over_external_duplicate(tmp_path):
    import json

    from analyzer.build_graph import build_graph

    analysis = [
        {
            "file": str(tmp_path / "local.py"), "language": "python",
            "imports": [], "classes": [
                {"name": "Base", "line": 1}, {"name": "Child", "line": 2}
            ],
            "interfaces": [], "functions": [], "calls": [],
            "inheritance": [{"class": "Child", "parent": "Base", "line": 2}],
            "implementations": [],
        },
        {
            "file": str(tmp_path / "external.py"), "language": "python",
            "imports": [], "classes": [{"name": "Base", "line": 1}],
            "interfaces": [], "functions": [], "calls": [],
            "inheritance": [], "implementations": [],
        },
    ]
    analysis_file = tmp_path / "analysis.json"
    analysis_file.write_text(json.dumps(analysis), encoding="utf-8")

    graph = build_graph(str(analysis_file))
    child = f"class:{analysis[0]['file']}:Child:2"
    targets = {
        edge["target"] for edge in graph["edges"]
        if edge["relationship"] == "extends" and edge["source"] == child
    }
    assert targets == {f"class:{analysis[0]['file']}:Base:1"}


def test_build_graph_resolves_python_imported_function_and_class_method_aliases(tmp_path):
    import json

    from analyzer.build_graph import build_graph

    service_file = str(tmp_path / "services.py")
    caller_file = str(tmp_path / "consumer.py")
    analysis = [
        {
            "file": service_file, "language": "python", "imports": [],
            "import_details": [], "classes": [{"name": "UserService", "line": 1}],
            "interfaces": [], "functions": [
                {"name": "fetch_user", "line": 2, "class": None},
                {"name": "get_user", "line": 3, "class": "UserService"},
            ], "calls": [], "inheritance": [], "implementations": [],
        },
        {
            "file": caller_file, "language": "python", "imports": ["services"],
            "import_details": [
                {"type": "from_import", "module": "services", "name": "fetch_user",
                 "alias": "load_user", "level": 0, "line": 1},
                {"type": "from_import", "module": "services", "name": "UserService",
                 "alias": "Service", "level": 0, "line": 2},
            ],
            "classes": [], "interfaces": [],
            "functions": [{"name": "run", "line": 4, "class": None}],
            "calls": [
                {"name": "load_user", "called_from": "run", "called_from_line": 4,
                 "called_from_class": None, "call_type": "direct", "line": 5},
                {"name": "get_user", "called_from": "run", "called_from_line": 4,
                 "called_from_class": None, "call_type": "attribute",
                 "receiver": "Service", "line": 6},
            ],
            "inheritance": [], "implementations": [],
        },
    ]
    analysis_file = tmp_path / "analysis.json"
    analysis_file.write_text(json.dumps(analysis), encoding="utf-8")

    graph = build_graph(str(analysis_file))
    calls = [edge for edge in graph["edges"] if edge["relationship"] == "calls"]
    assert len(calls) == 2
    assert {edge["resolution"] for edge in calls} == {
        "imported_function", "imported_class_method"
    }
    assert graph["call_resolution"]["resolved_calls"] == 2


def test_build_graph_resolves_javascript_named_import_function_alias(tmp_path):
    import json

    from analyzer.build_graph import build_graph

    source_file = str(tmp_path / "helpers.js")
    caller_file = str(tmp_path / "app.js")
    analysis = [
        {
            "file": source_file, "language": "javascript", "imports": [],
            "import_details": [], "classes": [], "interfaces": [],
            "functions": [{"name": "formatUser", "line": 1, "class": None}],
            "calls": [], "inheritance": [], "implementations": [],
        },
        {
            "file": caller_file, "language": "javascript", "imports": ["./helpers"],
            "import_details": [
                {"type": "import", "module": "./helpers", "name": "formatUser",
                 "alias": "format", "import_kind": "named", "line": 1},
            ],
            "classes": [], "interfaces": [],
            "functions": [{"name": "render", "line": 2, "class": None}],
            "calls": [
                {"name": "format", "called_from": "render", "called_from_line": 2,
                 "called_from_class": None, "call_type": "direct",
                 "expression": "format(user)", "line": 3},
            ],
            "inheritance": [], "implementations": [],
        },
    ]
    analysis_file = tmp_path / "analysis.json"
    analysis_file.write_text(json.dumps(analysis), encoding="utf-8")

    graph = build_graph(str(analysis_file))
    calls = [edge for edge in graph["edges"] if edge["relationship"] == "calls"]
    assert len(calls) == 1
    assert calls[0]["resolution"] == "imported_function"
    assert graph["call_resolution"]["resolved_calls"] == 1


def test_python_instance_method_call_resolves_across_files(tmp_path):
    import json

    from analyzer.build_graph import build_graph
    from analyzer.repository_analyzer import analyze_repository

    (tmp_path / "services.py").write_text(
        "class UserService:\n"
        "    def get_user(self):\n"
        "        return 'user'\n",
        encoding="utf-8",
    )
    (tmp_path / "consumer.py").write_text(
        "from services import UserService\n"
        "def run():\n"
        "    service = UserService()\n"
        "    service.get_user()\n",
        encoding="utf-8",
    )

    analysis = analyze_repository(str(tmp_path))
    consumer = next(item for item in analysis if item["file"].endswith("consumer.py"))
    assert consumer["instantiations"] == [{
        "variable": "service",
        "class_name": "UserService",
        "line": 3,
        "scope_function": "run",
        "scope_class": None,
    }]

    analysis_file = tmp_path / "analysis.json"
    analysis_file.write_text(json.dumps(analysis), encoding="utf-8")
    graph = build_graph(str(analysis_file))

    service_class = next(
        node for node in graph["nodes"]
        if node["type"] == "class" and node["label"] == "UserService"
    )
    method = next(
        node for node in graph["nodes"]
        if node["type"] == "function" and node["label"] == "get_user"
    )
    instance_calls = [
        edge for edge in graph["edges"]
        if edge["relationship"] == "calls"
        and edge.get("resolution") == "instance_method"
    ]
    assert len(instance_calls) == 1
    assert instance_calls[0]["target"] == method["id"]
    assert method["file"] == service_class["file"]


def test_python_instance_method_resolution_respects_function_scope(tmp_path):
    import json

    from analyzer.build_graph import build_graph

    service_file = str(tmp_path / "services.py")
    caller_file = str(tmp_path / "consumer.py")
    analysis = [
        {
            "file": service_file, "language": "python", "imports": [],
            "import_details": [], "classes": [{"name": "UserService", "line": 1}],
            "interfaces": [], "functions": [
                {"name": "get_user", "line": 2, "class": "UserService"}
            ], "calls": [], "instantiations": [],
            "inheritance": [], "implementations": [],
        },
        {
            "file": caller_file, "language": "python", "imports": ["services"],
            "import_details": [
                {"type": "from_import", "module": "services", "name": "UserService",
                 "alias": None, "level": 0, "line": 1}
            ],
            "classes": [], "interfaces": [],
            "functions": [
                {"name": "first", "line": 2, "class": None},
                {"name": "second", "line": 5, "class": None},
            ],
            "calls": [
                {"name": "get_user", "called_from": "second", "called_from_line": 5,
                 "called_from_class": None, "call_type": "attribute",
                 "receiver": "service", "line": 6}
            ],
            "instantiations": [{
                "variable": "service", "class_name": "UserService", "line": 3,
                "scope_function": "first", "scope_class": None
            }],
            "inheritance": [], "implementations": [],
        },
    ]
    analysis_file = tmp_path / "analysis.json"
    analysis_file.write_text(json.dumps(analysis), encoding="utf-8")

    graph = build_graph(str(analysis_file))
    assert not [
        edge for edge in graph["edges"]
        if edge["relationship"] == "calls"
        and edge.get("resolution") == "instance_method"
    ]
    assert any(
        detail["reason"] == "target_not_found"
        for detail in graph["unresolved_call_details"]
    )



def test_repository_analyzer_skips_unsupported_file_extensions(tmp_path):
    (tmp_path / "main.py").write_text(
        "def main(): return 1", encoding="utf-8"
    )
    (tmp_path / "settings.json").write_text(
        '{"enabled": true}', encoding="utf-8"
    )
    (tmp_path / "README.md").write_text(
        "# Project documentation", encoding="utf-8"
    )
    (tmp_path / "logo.png").write_bytes(b"not really an image")

    results = analyze_repository(str(tmp_path))

    assert len(results) == 1
    assert results[0]["language"] == "python"
    assert not results[0].get("error")
    assert results[0]["file"].endswith("main.py")



def test_javascript_typescript_parser_uses_compiler_ast_and_extracts_structure():
    from analyzer.parsers.tree_sitter_parser import TreeSitterParser

    javascript = TreeSitterParser("javascript").parse_file(
        "tests/fixtures/sample.js"
    )
    typescript = TreeSitterParser("typescript").parse_file(
        "tests/fixtures/sample.ts"
    )

    assert not javascript.get("error"), javascript.get("error")
    assert not typescript.get("error"), typescript.get("error")
    assert any(item["name"] == "UserService" for item in javascript["classes"])
    assert any(item["name"] == "greet" for item in javascript["functions"])
    assert any(item["name"] == "UserService" for item in typescript["classes"])
    assert any(item["name"] == "User" for item in typescript["interfaces"])
    assert any(item["parent"] == "UserService" for item in typescript["inheritance"])
    assert any(item["interface"] == "Admin" for item in typescript["implementations"])
    assert javascript["declaration_chunks"]
    assert typescript["declaration_chunks"]


def test_javascript_parser_handles_full_frontend_app_without_native_treesitter():
    from analyzer.parsers.tree_sitter_parser import TreeSitterParser

    parsed = TreeSitterParser("javascript").parse_file("frontend/app.js")

    assert not parsed.get("error"), parsed.get("error")
    assert parsed["functions"]
    assert parsed["calls"]
    assert parsed["declaration_chunks"]


def test_java_only_repository_can_be_analyzed_graphed_and_chunked(tmp_path):
    import json
    from analyzer.build_graph import build_graph

    (tmp_path / "Main.java").write_text(
        "package demo;\n"
        "interface Repository { String find(int id); }\n"
        "class UserRepository implements Repository {\n"
        "  public String find(int id) { return lookup(id); }\n"
        "  private String lookup(int id) { return \"user\"; }\n"
        "}\n",
        encoding="utf-8",
    )

    analysis = analyze_repository(str(tmp_path))
    assert len(analysis) == 1
    assert analysis[0]["language"] == "java"
    assert not analysis[0].get("error")
    assert analysis[0]["classes"]
    assert analysis[0]["functions"]

    analysis_path = tmp_path / "analysis.json"
    analysis_path.write_text(json.dumps(analysis), encoding="utf-8")
    graph = build_graph(str(analysis_path))
    chunks = create_chunks(str(tmp_path))

    assert graph["nodes"]
    assert any(node.get("language") == "java" for node in graph["nodes"])
    assert chunks
    assert {chunk["metadata"]["language"] for chunk in chunks} == {"java"}



def test_java_only_repository_uses_wasm_parser_without_python(tmp_path):
    from analyzer.build_graph import build_graph
    import json

    (tmp_path / "UserService.java").write_text(
        "package demo;\n"
        "import java.util.List;\n"
        "public class UserService {\n"
        "  public User findUser(int id) { return new User(); }\n"
        "}\n"
        "class User { }\n",
        encoding="utf-8",
    )

    analysis = analyze_repository(str(tmp_path))
    assert len(analysis) == 1
    assert analysis[0]["language"] == "java"
    assert not analysis[0].get("error"), analysis[0].get("error")
    assert any(item["name"] == "UserService" for item in analysis[0]["classes"])
    assert any(item["name"] == "findUser" for item in analysis[0]["functions"])
    assert analysis[0]["imports"]

    chunks = create_chunks(str(tmp_path))
    assert any(
        chunk["metadata"]["language"] == "java"
        and chunk["metadata"]["type"] == "class"
        and chunk["metadata"]["name"] == "UserService"
        for chunk in chunks
    )
    assert any(chunk["metadata"]["type"] == "file" for chunk in chunks)

    analysis_file = tmp_path / "analysis.json"
    analysis_file.write_text(json.dumps(analysis), encoding="utf-8")
    graph = build_graph(str(analysis_file))
    assert any(node.get("label") == "UserService" for node in graph["nodes"])


def test_java_parser_extracts_implementations_typed_fields_and_method_calls(tmp_path):
    import json

    from analyzer.build_graph import build_graph

    (tmp_path / "Repository.java").write_text(
        "package demo;\n"
        "interface Repository { Object findById(int id); }\n"
        "class JpaRepository implements Repository {\n"
        "  public Object findById(int id) { return null; }\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "OwnerController.java").write_text(
        "package demo;\n"
        "class OwnerController {\n"
        "  private Repository repository;\n"
        "  public Object showOwner(int id) { return repository.findById(id); }\n"
        "}\n",
        encoding="utf-8",
    )

    analysis = analyze_repository(str(tmp_path))
    assert all(not item.get("error") for item in analysis), analysis

    repository_record = next(
        item for item in analysis if item["file"].endswith("Repository.java")
    )
    controller_record = next(
        item for item in analysis if item["file"].endswith("OwnerController.java")
    )

    assert {
        "class": "JpaRepository", "interface": "Repository", "line": 3
    } in repository_record["implementations"]
    assert {
        "class": "OwnerController", "name": "repository",
        "type": "Repository", "line": 3
    } in controller_record["typed_fields"]
    assert any(
        call["name"] == "findById"
        and call["receiver"] == "repository"
        and call["called_from"] == "showOwner"
        for call in controller_record["calls"]
    )

    analysis_path = tmp_path / "analysis.json"
    analysis_path.write_text(json.dumps(analysis), encoding="utf-8")
    graph = build_graph(str(analysis_path))

    implementation_edges = [
        edge for edge in graph["edges"]
        if edge["relationship"] == "implements"
    ]
    call_edges = [
        edge for edge in graph["edges"]
        if edge["relationship"] == "calls"
        and edge.get("resolution") == "java_typed_field"
    ]
    assert len(implementation_edges) == 1
    assert len(call_edges) == 1
    assert graph["call_resolution"]["resolved_calls"] == 1


def test_java_this_field_call_resolves_to_declared_interface(tmp_path):
    import json
    from analyzer.build_graph import build_graph

    (tmp_path / "OwnerRepository.java").write_text(
        "interface OwnerRepository { Object findById(int id); }\n",
        encoding="utf-8",
    )
    (tmp_path / "OwnerController.java").write_text(
        "class OwnerController {\n"
        "  private OwnerRepository owners;\n"
        "  Object showOwner(int id) { return this.owners.findById(id); }\n"
        "}\n",
        encoding="utf-8",
    )
    analysis = analyze_repository(str(tmp_path))
    assert all(not record.get("error") for record in analysis), analysis
    analysis_path = tmp_path / "analysis.json"
    analysis_path.write_text(json.dumps(analysis), encoding="utf-8")
    graph = build_graph(str(analysis_path))
    matches = [
        edge for edge in graph["edges"]
        if edge["relationship"] == "calls"
        and "findById" in edge.get("call_expression", "")
        and edge.get("resolution") == "java_typed_field"
    ]
    assert len(matches) == 1
    assert "OwnerRepository.java" in matches[0]["target"]


def test_java_typed_parameters_and_locals_resolve_calls_with_overloads(tmp_path):
    import json

    from analyzer.build_graph import build_graph

    (tmp_path / "Owner.java").write_text(
        "class Owner {\n"
        "  Pet getPet(int id) { return null; }\n"
        "  Pet getPet(String name) { return null; }\n"
        "  void addVisit(int id, Visit visit) {}\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "Pet.java").write_text(
        "class Pet { void addVisit(Visit visit) {} }\n",
        encoding="utf-8",
    )
    (tmp_path / "Visit.java").write_text(
        "class Visit {}\n",
        encoding="utf-8",
    )
    (tmp_path / "VisitController.java").write_text(
        "class VisitController {\n"
        "  void load(Owner owner, int petId, Visit visit) {\n"
        "    Pet pet = owner.getPet(petId);\n"
        "    pet.addVisit(visit);\n"
        "    owner.addVisit(petId, visit);\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )

    analysis = analyze_repository(str(tmp_path))
    assert all(not item.get("error") for item in analysis), analysis
    analysis_path = tmp_path / "analysis.json"
    analysis_path.write_text(json.dumps(analysis), encoding="utf-8")
    graph = build_graph(str(analysis_path))

    calls = [
        edge for edge in graph["edges"]
        if edge["relationship"] == "calls"
        and edge.get("resolution") == "java_typed_field"
    ]
    assert len(calls) == 3
    assert graph["call_resolution"]["resolved_calls"] == 3
    assert not [
        detail for detail in graph["unresolved_call_details"]
        if detail["target"] in {"getPet", "addVisit"}
    ]
