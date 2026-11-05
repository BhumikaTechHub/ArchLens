import json
import os
import sys
from collections import defaultdict
def get_module_name(file_path, repo_root):
    relative = os.path.relpath(file_path, repo_root)

    parts = relative.replace("\\", "/").split("/")

    if parts[0] == "src":
        parts = parts[1:]

    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    elif parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]

    return ".".join(parts)

def resolve_import_module(module, level, current_module):
    if level == 0:
        return module

    package = current_module.split(".")[:-1]

    if level > 1:
        package = package[:-(level - 1)]

    if module:
        package.extend(module.split("."))

    return ".".join(package)

def build_module_index(analysis):
    module_map = {}

    file_paths = [item["file"] for item in analysis]

    if not file_paths:
        return module_map

    repo_root = os.path.commonpath(file_paths)

    # Move the root above src/ when a src layout exists.
    for file_path in file_paths:
        parts = file_path.replace("\\", "/").split("/")

        if "src" in parts:
            src_index = parts.index("src")
            src_root = "/".join(parts[:src_index])
            repo_root = src_root or "."
            break

    for item in analysis:
        module_name = get_module_name(item["file"], repo_root)
        module_map[module_name] = item

    return module_map

def resolve_import_target(import_detail, current_module, module_map):
    module = import_detail.get("module")
    name = import_detail.get("name")
    level = import_detail.get("level", 0)

    base_module = resolve_import_module(
        module, level, current_module
    )

    if not name:
        return None, None, None

    # First check whether the imported name is itself a submodule.
    submodule = ".".join(filter(None, [base_module, name]))

    if submodule in module_map:
        return module_map[submodule], None, submodule

    # Otherwise, treat it as a symbol imported from the module.
    if base_module in module_map:
        return module_map[base_module], name, base_module

    return None, None, None

def classify_file(file_path):
    normalized = file_path.replace("\\", "/").lower()
    parts = normalized.split("/")

    if "tests" in parts or "test" in parts:
        return "test"

    if "docs" in parts or "documentation" in parts:
        return "documentation"

    filename = parts[-1]

    if filename in {
        "setup.py",
        "setup.cfg",
        "pyproject.toml",
        "requirements.txt",
        "tox.ini",
        "pytest.ini",
    }:
        return "configuration"

    if "src" in parts:
        return "production"

    return "other"

def build_graph(analysis_file):
    with open(analysis_file, "r", encoding="utf-8") as f:
        analysis = json.load(f)

    nodes = []
    edges = []

    function_nodes = defaultdict(list)
    class_nodes = {}
    file_nodes = {}

    # Create file nodes
    for item in analysis:
        file_path = item["file"]
        file_id = f"file:{file_path}"
        file_nodes[file_path] = file_id

        nodes.append({
            "id": file_id,
            "type": "file",
            "language": item.get("language", "unknown"),
            "label": os.path.basename(file_path),
            "file": file_path,
            "file_category": classify_file(file_path),
        })

    # Create module nodes and import relationships
    module_ids = set()

    for item in analysis:
        file_path = item["file"]
        source_id = file_nodes[file_path]

        for imported in item.get("imports", []):
            module_id = f"module:{imported}"

            if module_id not in module_ids:
                module_ids.add(module_id)
                nodes.append({
                    "id": module_id,
                    "type": "module",
                    "label": imported,
                    "file": "",
                })

            edges.append({
                "source": source_id,
                "target": module_id,
                "relationship": "imports",
            })

    # Create class nodes
    for item in analysis:
        file_path = item["file"]
        file_id = file_nodes[file_path]

        for cls in item.get("classes", []):
            class_name = cls["name"]
            line = cls.get("line", 0)

            class_id = f"class:{file_path}:{class_name}:{line}"

            class_nodes[(file_path, class_name)] = class_id

            nodes.append({
                "id": class_id,
                "type": "class",
                "language": item.get("language", "unknown"),
                "label": class_name,
                "file": file_path,
                "line": line,
                "file_category": classify_file(file_path),
            })

            edges.append({
                "source": file_id,
                "target": class_id,
                "relationship": "contains",
            })

    # Create interface nodes
    interface_nodes = {}

    for item in analysis:
        file_path = item["file"]
        file_id = file_nodes[file_path]

        for interface in item.get("interfaces", []):
            interface_name = interface["name"]
            line = interface.get("line", 0)

            interface_id = (
                f"interface:{file_path}:{interface_name}:{line}"
            )

            interface_nodes[(file_path, interface_name)] = interface_id

            nodes.append({
                "id": interface_id,
                "type": "interface",
                "language": item.get("language", "unknown"),
                "label": interface_name,
                "file": file_path,
                "line": line,
                "file_category": classify_file(file_path),
            })

            edges.append({
                "source": file_id,
                "target": interface_id,
                "relationship": "contains",
            })

    # Resolve inheritance and interface implementations
    for item in analysis:
        file_path = item["file"]

        for relationship in item.get("inheritance", []):
            class_name = relationship.get("class")
            parent_name = relationship.get("parent")

            source_id = class_nodes.get((file_path, class_name))
            target_id = class_nodes.get((file_path, parent_name))

            if source_id and target_id:
                edges.append({
                    "source": source_id,
                    "target": target_id,
                    "relationship": "extends",
                    "line": relationship.get("line"),
                })

        for relationship in item.get("implementations", []):
            class_name = relationship.get("class")
            interface_name = relationship.get("interface")

            source_id = class_nodes.get((file_path, class_name))
            target_id = interface_nodes.get(
                (file_path, interface_name)
            )

            if source_id and target_id:
                edges.append({
                    "source": source_id,
                    "target": target_id,
                    "relationship": "implements",
                    "line": relationship.get("line"),
                })

    # Resolve cross-file inheritance and interface implementation only when
    # the referenced symbol has one unambiguous definition in the repository.
    # Ambiguous and missing references are retained as diagnostics, not guessed.
    classes_by_name = defaultdict(list)
    interfaces_by_name = defaultdict(list)

    for (file_path, class_name), node_id in class_nodes.items():
        classes_by_name[class_name].append((file_path, node_id))

    for (file_path, interface_name), node_id in interface_nodes.items():
        interfaces_by_name[interface_name].append((file_path, node_id))

    unresolved_relationships = []

    for item in analysis:
        file_path = item["file"]

        for relationship in item.get("inheritance", []):
            child_name = relationship.get("class")
            parent_name = relationship.get("parent")
            child_id = class_nodes.get((file_path, child_name))
            if not child_id or not parent_name:
                continue
            if class_nodes.get((file_path, parent_name)):
                continue

            candidates = classes_by_name.get(parent_name, [])
            candidates = [entry for entry in candidates if entry[0] != file_path]
            if len(candidates) == 1:
                edges.append({
                    "source": child_id,
                    "target": candidates[0][1],
                    "relationship": "extends",
                    "line": relationship.get("line"),
                    "resolution": "unique_cross_file_symbol",
                })
            elif len(candidates) > 1:
                unresolved_relationships.append({
                    "file": file_path, "kind": "extends",
                    "source": child_name, "target": parent_name,
                    "reason": "ambiguous_target",
                })

        for relationship in item.get("implementations", []):
            child_name = relationship.get("class")
            interface_name = relationship.get("interface")
            child_id = class_nodes.get((file_path, child_name))
            if not child_id or not interface_name:
                continue
            if interface_nodes.get((file_path, interface_name)):
                continue

            candidates = interfaces_by_name.get(interface_name, [])
            candidates = [entry for entry in candidates if entry[0] != file_path]
            if len(candidates) == 1:
                edges.append({
                    "source": child_id,
                    "target": candidates[0][1],
                    "relationship": "implements",
                    "line": relationship.get("line"),
                    "resolution": "unique_cross_file_symbol",
                })
            elif len(candidates) > 1:
                unresolved_relationships.append({
                    "file": file_path, "kind": "implements",
                    "source": child_name, "target": interface_name,
                    "reason": "ambiguous_target",
                })

    # Create module index for symbol-level import resolution.
    module_map = build_module_index(analysis)

    module_by_file = {
        record["file"]: module
        for module, record in module_map.items()
    }

    # Resolve imported class symbols.
    for item in analysis:
        current_module = module_by_file.get(item["file"])

        for imp in item.get("import_details", []):
            if imp.get("type") != "from_import":
                continue

            target_record, symbol, target_module = resolve_import_target(
                imp, current_module, module_map
            )

            if not target_record or not symbol:
                continue

            target_class_id = class_nodes.get(
                (target_record["file"], symbol)
            )

            if not target_class_id:
                continue

            edges.append({
                "source": file_nodes[item["file"]],
                "target": target_class_id,
                "relationship": "imports_symbol",
                "line": imp.get("line"),
            })

    # Resolve JavaScript and TypeScript named imports
    analysis_paths = {
        os.path.normpath(item["file"]): item
        for item in analysis
    }

    for item in analysis:
        source_file = item["file"]
        source_id = file_nodes[source_file]

        for imp in item.get("import_details", []):

            if imp.get("import_kind") != "named":
                continue

            module = imp.get("module", "")
            imported_name = imp.get("name")

            # Only resolve relative imports for now.
            if not module.startswith(".") or not imported_name:
                continue

            base_path = os.path.normpath(
                os.path.join(os.path.dirname(source_file), module)
            )

            candidates = [
                base_path,
                base_path + ".ts",
                base_path + ".tsx",
                base_path + ".js",
                base_path + ".jsx",
                os.path.join(base_path, "index.ts"),
                os.path.join(base_path, "index.tsx"),
                os.path.join(base_path, "index.js"),
                os.path.join(base_path, "index.jsx"),
            ]

            target_file = next(
                (
                    path for path in candidates
                    if path in analysis_paths
                ),
                None
            )

            if not target_file:
                continue

            target_class_id = class_nodes.get(
                (target_file, imported_name)
            )

            if not target_class_id:
                continue

            edges.append({
                "source": source_id,
                "target": target_class_id,
                "relationship": "imports_symbol",
                "imported_name": imported_name,
                "local_name": imp.get("alias") or imported_name,
                "line": imp.get("line"),
                "resolution": "relative_named_import",
            })

    # Create function nodes
    for item in analysis:
        file_path = item["file"]
        file_id = file_nodes[file_path]

        for function in item.get("functions", []):
            function_name = function["name"]
            line = function.get("line", 0)
            class_name = function.get("class")

            function_id = (
                f"function:{file_path}:{function_name}:{line}"
            )

            function_info = {
                "id": function_id,
                "name": function_name,
                "file": file_path,
                "class": class_name,
                "line": line,
                "parameter_count": function.get("parameter_count"),
                "parameter_types": function.get("parameter_types"),
            }

            function_nodes[function_name].append(function_info)

            nodes.append({
                "id": function_id,
                "type": "function",
                "language": item.get("language", "unknown"),
                "label": function_name,
                "file": file_path,
                "line": line,
                "class": class_name,
                "file_category": classify_file(file_path),
            })

            if class_name:
                class_id = class_nodes.get((file_path, class_name))
                interface_id = interface_nodes.get((file_path, class_name))

                owner_id = class_id or interface_id
                if owner_id:
                    edges.append({
                        "source": owner_id,
                        "target": function_id,
                        "relationship": "contains",
                    })
            else:
                edges.append({
                    "source": file_id,
                    "target": function_id,
                    "relationship": "contains",
                })

    # Resolve call relationships using explicit import bindings where available.
    module_map = build_module_index(analysis)
    module_by_file = {
        record["file"]: module for module, record in module_map.items()
    }
    analysis_paths = {
        os.path.normpath(record["file"]): record for record in analysis
    }

    def resolve_js_module(source_file, module):
        if not module or not module.startswith("."):
            return None
        base_path = os.path.normpath(
            os.path.join(os.path.dirname(source_file), module)
        )
        candidates = [
            base_path, base_path + ".ts", base_path + ".tsx",
            base_path + ".js", base_path + ".jsx", base_path + ".mjs",
            base_path + ".cjs",
            os.path.join(base_path, "index.ts"),
            os.path.join(base_path, "index.tsx"),
            os.path.join(base_path, "index.js"),
            os.path.join(base_path, "index.jsx"),
        ]
        matches = [analysis_paths[path] for path in candidates if path in analysis_paths]
        # Duplicate candidate paths should not create artificial ambiguity.
        unique = {record["file"]: record for record in matches}
        return next(iter(unique.values())) if len(unique) == 1 else None

    # Java V2: match declared receiver types to project-owned types. A type
    # name must be unique; otherwise leave the call unresolved.
    java_types = defaultdict(list)
    for (owner_file, owner_name), owner_id in {**class_nodes, **interface_nodes}.items():
        java_types[owner_name].append(owner_file)

    def java_owner_methods(type_name, method_name, argument_count=None, argument_types=None):
        if not type_name or len(set(java_types.get(type_name, []))) != 1:
            return []
        owner_file = java_types[type_name][0]
        candidates = [
            candidate for candidate in function_nodes.get(method_name, [])
            if candidate["file"] == owner_file and candidate["class"] == type_name
        ]
        if argument_count is not None:
            arity_matches = [
                candidate for candidate in candidates
                if candidate.get("parameter_count") == argument_count
            ]
            if arity_matches:
                candidates = arity_matches
            elif candidates and all(
                candidate.get("parameter_count") is not None
                for candidate in candidates
            ):
                return []

        # Prefer exact declared parameter types when every call argument has
        # a locally known type. If type information is incomplete, retain the
        # conservative arity-based candidates instead of guessing.
        if argument_types and all(argument_types):
            typed_candidates = [
                candidate for candidate in candidates
                if candidate.get("parameter_types")
                and len(candidate["parameter_types"]) == len(argument_types)
                and all(candidate_type is not None for candidate_type in candidate["parameter_types"])
                and candidate["parameter_types"] == argument_types
            ]
            if typed_candidates:
                return typed_candidates
            if any(candidate.get("parameter_types") for candidate in candidates):
                return []
        return candidates

    resolved_calls = 0
    unresolved_calls = 0
    unresolved_reasons = defaultdict(int)
    unresolved_call_details = []

    for item in analysis:
        file_path = item["file"]
        current_module = module_by_file.get(file_path)
        function_imports = {}
        class_imports = {}
        import_resolution_issues = []

        for imp in item.get("import_details", []):
            if imp.get("type") == "from_import":
                target_record, symbol, target_module = resolve_import_target(
                    imp, current_module, module_map
                )
                if not target_record or not symbol:
                    continue
                local_name = imp.get("alias") or symbol
                if (target_record["file"], symbol) in class_nodes:
                    class_imports[local_name] = (target_record, symbol)
                elif any(
                    fn.get("name") == symbol and fn.get("class") is None
                    for fn in target_record.get("functions", [])
                ):
                    function_imports[local_name] = (target_record, symbol)

            elif (
                imp.get("type") == "import"
                and imp.get("import_kind") == "named"
            ):
                target_record = resolve_js_module(file_path, imp.get("module"))
                symbol = imp.get("name")
                if not target_record or not symbol:
                    continue
                local_name = imp.get("alias") or symbol
                if (target_record["file"], symbol) in class_nodes:
                    class_imports[local_name] = (target_record, symbol)
                elif any(
                    fn.get("name") == symbol and fn.get("class") is None
                    for fn in target_record.get("functions", [])
                ):
                    function_imports[local_name] = (target_record, symbol)

        # Track simple Python variable assignments such as
        # service = UserService() within the same function/class scope.
        instance_bindings = {}
        for instance in item.get("instantiations", []):
            variable = instance.get("variable")
            class_name = instance.get("class_name")
            if not variable or not class_name:
                continue

            class_target = class_imports.get(class_name)
            if class_target:
                target_record, class_symbol = class_target
            else:
                target_record = item
                class_symbol = class_name

            if (target_record["file"], class_symbol) not in class_nodes:
                continue

            key = (
                instance.get("scope_function"),
                instance.get("scope_class"),
                variable,
            )
            instance_bindings[key] = (target_record, class_symbol)

        for call in item.get("calls", []):
            called_name = call.get("name")
            called_from = call.get("called_from")
            caller_line = call.get("called_from_line")
            caller_class = call.get("called_from_class")
            call_type = call.get("call_type", "direct")
            receiver = call.get("receiver")

            def unresolved(reason):
                nonlocal_dummy = None
                unresolved_call_details.append({
                    "file": file_path,
                    "line": call.get("line"),
                    "caller": called_from,
                    "expression": call.get("expression"),
                    "target": called_name,
                    "reason": reason,
                })

            if not called_name or not called_from or not caller_line:
                unresolved_calls += 1
                unresolved_reasons["missing_caller"] += 1
                unresolved("missing_caller")
                continue

            source_candidates = [
                candidate
                for candidate in function_nodes.get(called_from, [])
                if candidate["file"] == file_path
                and candidate["line"] == caller_line
                and candidate["class"] == caller_class
            ]
            if len(source_candidates) != 1:
                unresolved_calls += 1
                unresolved_reasons["ambiguous_or_missing_caller"] += 1
                unresolved("ambiguous_or_missing_caller")
                continue

            source = source_candidates[0]
            target_candidates = []
            resolution = "unique_name_and_scope"

            if call_type == "direct":
                binding = function_imports.get(called_name)
                if binding:
                    target_record, symbol = binding
                    target_candidates = [
                        candidate for candidate in function_nodes.get(symbol, [])
                        if candidate["file"] == target_record["file"]
                        and candidate["class"] is None
                    ]
                    resolution = "imported_function"
                else:
                    target_candidates = [
                        candidate for candidate in function_nodes.get(called_name, [])
                        if candidate["file"] == file_path
                    ]

            elif call_type == "attribute" and receiver == "self":
                if caller_class:
                    target_candidates = [
                        candidate for candidate in function_nodes.get(called_name, [])
                        if candidate["file"] == file_path
                        and candidate["class"] == caller_class
                    ]

            elif call_type == "attribute" and receiver and item.get("language") == "java":
                # Resolve Java calls only through an explicitly typed field or
                # an explicit this/super receiver. Never infer from method name alone.
                target_owner = None
                if receiver in {"this", "super"} and caller_class:
                    target_owner = caller_class
                else:
                    # Both 'repository.findById()' and
                    # 'this.repository.findById()' refer to a typed field.
                    field_receiver = receiver.removeprefix("this.") if receiver else ""
                    matching_fields = [
                        field for field in item.get("typed_fields", [])
                        if field.get("class") == caller_class
                        and field.get("name") == field_receiver
                    ]
                    field_types = {field.get("type") for field in matching_fields}
                    variable_fields = [
                        variable for variable in item.get("typed_variables", [])
                        if variable.get("class") == caller_class
                        and variable.get("function") == called_from
                        and variable.get("name") == field_receiver
                    ]
                    variable_types = {variable.get("type") for variable in variable_fields}
                    all_receiver_types = field_types | variable_types
                    if len(all_receiver_types) == 1:
                        target_owner = next(iter(all_receiver_types))

                if target_owner:
                    argument_types = []
                    typed_arguments = {
                        variable.get("name"): variable.get("type")
                        for variable in item.get("typed_variables", [])
                        if variable.get("class") == caller_class
                        and variable.get("function") == called_from
                    }
                    for argument in call.get("argument_texts", []):
                        argument = argument.strip()
                        if argument in typed_arguments:
                            argument_types.append(typed_arguments[argument])
                        elif argument == "true" or argument == "false":
                            argument_types.append("boolean")
                        elif argument.startswith('"') or argument.startswith("'"):
                            argument_types.append("String")
                        elif argument.isdigit():
                            argument_types.append("int")
                        else:
                            argument_types.append(None)
                    owner_candidates = java_owner_methods(
                        target_owner, called_name, call.get("argument_count"),
                        argument_types if argument_types else None
                    )
                    if len(owner_candidates) == 1:
                        target_candidates = owner_candidates
                        resolution = "java_typed_field" if receiver not in {"this", "super"} else "java_same_class"
                    elif len(owner_candidates) > 1:
                        target_candidates = owner_candidates

            elif call_type == "attribute" and receiver:
                # Class-qualified calls can be resolved through imported class aliases.
                class_binding = class_imports.get(receiver)
                instance_binding = instance_bindings.get((
                    called_from, caller_class, receiver
                ))
                if instance_binding:
                    target_record, class_symbol = instance_binding
                    target_candidates = [
                        candidate for candidate in function_nodes.get(called_name, [])
                        if candidate["file"] == target_record["file"]
                        and candidate["class"] == class_symbol
                    ]
                    resolution = "instance_method"
                elif class_binding:
                    target_record, class_symbol = class_binding
                    target_candidates = [
                        candidate for candidate in function_nodes.get(called_name, [])
                        if candidate["file"] == target_record["file"]
                        and candidate["class"] == class_symbol
                    ]
                    resolution = "imported_class_method"
                elif receiver.isidentifier():
                    target_candidates = [
                        candidate for candidate in function_nodes.get(called_name, [])
                        if candidate["file"] == file_path
                        and candidate["class"] == receiver
                    ]

            else:
                unresolved_calls += 1
                unresolved_reasons["unsupported_call_type"] += 1
                unresolved("unsupported_call_type")
                continue

            if len(target_candidates) != 1:
                unresolved_calls += 1
                reason = "target_not_found" if not target_candidates else "ambiguous_target"
                unresolved_reasons[reason] += 1
                unresolved(reason)
                continue

            target = target_candidates[0]
            edges.append({
                "source": source["id"],
                "target": target["id"],
                "relationship": "calls",
                "call_expression": call.get("expression"),
                "call_line": call.get("line"),
                "resolution": resolution,
            })
            resolved_calls += 1

    # Remove duplicate edges
    unique_edges = []
    seen_edges = set()

    for edge in edges:
        key = (
            edge["source"],
            edge["target"],
            edge["relationship"],
            edge.get("call_line"),
            edge.get("line"),
            edge.get("local_name"),
            edge.get("imported_name"),
        )

        if key not in seen_edges:
            seen_edges.add(key)
            unique_edges.append(edge)

    return {
        "nodes": nodes,
        "edges": unique_edges,
        "unresolved_relationships": unresolved_relationships,
        "unresolved_call_details": unresolved_call_details,
        "call_resolution": {
            "resolved_calls": resolved_calls,
            "unresolved_calls": unresolved_calls,
            "unresolved_reasons": dict(unresolved_reasons),
            "method": "Conservative same-file, class-scope, and imported-symbol resolution",
        },
    }


def main():
    if len(sys.argv) != 3:
        print(
            "Usage: python3 analyzer/build_graph.py "
            "<analysis_file> <output_file>"
        )
        sys.exit(1)

    analysis_file = sys.argv[1]
    output_file = sys.argv[2]

    graph = build_graph(analysis_file)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2)

    print("Architecture graph created.")
    print(f"Input : {analysis_file}")
    print(f"Output: {output_file}")
    print(f"Nodes : {len(graph['nodes'])}")
    print(f"Edges : {len(graph['edges'])}")
    print("Call resolution:")
    print(json.dumps(graph["call_resolution"], indent=2))


if __name__ == "__main__":
    main()
