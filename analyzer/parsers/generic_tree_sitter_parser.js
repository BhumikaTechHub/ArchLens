#!/usr/bin/env node
// Parse non-Python, non-JavaScript/TypeScript sources with Tree-sitter WebAssembly.
// The parser runs in a separate Node process; Python never loads the native binding.
const fs = require("node:fs");

const CLASS_NODES = new Set([
  "class_declaration", "interface_declaration", "enum_declaration",
  "record_declaration", "struct_declaration", "type_declaration",
  "type_spec", "struct_specifier", "class_specifier", "struct_item",
  "enum_item", "trait_item", "impl_item", "mod_item", "trait_declaration",
  "class", "module", "object_declaration", "protocol_declaration",
  "enum_specifier", "namespace_definition"
]);
const INTERFACE_NODES = new Set([
  "interface_declaration", "trait_item", "trait_declaration",
  "protocol_declaration"
]);
const FUNCTION_NODES = new Set([
  "function_declaration", "generator_function_declaration",
  "method_definition", "method_declaration", "constructor_declaration",
  "function_definition", "function_item", "method", "singleton_method"
]);
const IMPORT_NODES = new Set([
  "import_declaration", "using_directive", "preproc_include",
  "use_declaration", "namespace_use_declaration"
]);

const GRAMMAR_CANDIDATES = {
  csharp: ["c_sharp", "csharp"],
  cpp: ["cpp"],
  c: ["c"],
  java: ["java"],
  go: ["go"],
  rust: ["rust"],
  php: ["php"],
  ruby: ["ruby"],
  kotlin: ["kotlin"],
  swift: ["swift"]
};

function makeResult(file, language) {
  return {
    file, language, imports: [], import_details: [], classes: [],
    interfaces: [], functions: [], calls: [], inheritance: [],
    implementations: [], typed_fields: [], typed_variables: [], declaration_chunks: []
  };
}

function nodeText(node, source) {
  if (!node) return "";
  const start = node.startIndex ?? node.startByte;
  const end = node.endIndex ?? node.endByte;
  return source.slice(start, end);
}

function getName(node, source) {
  let nameNode = null;
  try {
    nameNode = node.childForFieldName("name");
  } catch (_) {}
  if (nameNode) return nodeText(nameNode, source).trim();

  for (const child of node.namedChildren || []) {
    if (["identifier", "type_identifier", "constant",
         "namespace_identifier", "name"].includes(child.type)) {
      return nodeText(child, source).trim();
    }
  }
  return null;
}

async function main() {
  const [, , filePath, language] = process.argv;
  const result = makeResult(filePath, language);
  try {
    const { Parser: ExportedParser, Language } = require("web-tree-sitter");
    const Parser = ExportedParser || require("web-tree-sitter");
    const wasmPackage = await import("tree-sitter-wasm");
    const getWasmPath = wasmPackage.getWasmPath;
    if (typeof getWasmPath !== "function") {
      throw new Error("tree-sitter-wasm does not expose getWasmPath().");
    }

    const source = fs.readFileSync(filePath, "utf8");
    await Parser.init();
    const parser = new Parser();
    const candidates = GRAMMAR_CANDIDATES[language] || [language];
    let grammarPath = null;
    let loadError = null;
    let grammar = null;
    for (const candidate of candidates) {
      try {
        const candidatePath = getWasmPath(candidate);
        grammar = await (Language || Parser.Language).load(candidatePath);
        grammarPath = candidatePath;
        break;
      } catch (error) {
        loadError = error;
      }
    }
    if (!grammar) {
      throw new Error(
        `No compatible WASM grammar found for '${language}': ${loadError?.message || "not packaged"}`
      );
    }

    parser.setLanguage(grammar);
    const tree = parser.parse(source);
    const root = tree.rootNode;
    const hasParseErrors = typeof root.hasError === "function" ? root.hasError() : root.hasError;
    if (hasParseErrors) result.parse_errors = true;

    function visit(node, enclosingClass = null, enclosingFunction = null, enclosingFunctionLine = null) {
      const type = node.type;
      const line = (node.startPosition?.row ?? 0) + 1;
      const endLine = (node.endPosition?.row ?? 0) + 1;

      if (IMPORT_NODES.has(type)) {
        const statement = nodeText(node, source).trim();
        if (statement) {
          result.imports.push(statement);
          result.import_details.push({
            type: "import", module: statement, name: null, alias: null,
            import_kind: "statement", line, level: 0
          });
        }
      }

      let currentClass = enclosingClass;
      if (CLASS_NODES.has(type)) {
        const name = getName(node, source);
        if (name) {
          const target = INTERFACE_NODES.has(type)
            ? result.interfaces : result.classes;
          target.push({ name, line });
          currentClass = name;
          result.declaration_chunks.push({
            code: nodeText(node, source), type: INTERFACE_NODES.has(type) ? "interface" : "class",
            name, class_name: enclosingClass, line, end_line: endLine
          });
        }
      }

      let currentFunction = enclosingFunction;
      let currentFunctionLine = enclosingFunctionLine;
      if (FUNCTION_NODES.has(type)) {
        const name = getName(node, source) || "<anonymous>";
        const parametersNode = node.childForFieldName("parameters");
        const parameterNodes = parametersNode
          ? (parametersNode.namedChildren || []).filter(child =>
              ["formal_parameter", "spread_parameter", "receiver_parameter", "parameter"].includes(child.type))
          : [];
        const parameterCount = parametersNode ? parameterNodes.length : null;
        const parameterTypes = language === "java"
          ? parameterNodes.map(parameter => {
              const typeNode = parameter.childForFieldName("type");
              return typeNode ? nodeText(typeNode, source).replace(/<.*>$/, "").trim() : null;
            })
          : [];
        result.functions.push({
          name, line, arguments: [], class: currentClass,
          parameter_count: parameterCount,
          ...(language === "java" ? { parameter_types: parameterTypes } : {})
        });
        result.declaration_chunks.push({
          code: nodeText(node, source), type: "function", name,
          class_name: currentClass, line, end_line: endLine
        });
        currentFunction = name;
        currentFunctionLine = line;
      }

      // Java declarations expose enough structure to resolve conservative
      // inheritance, implementation and field-typed method-call relationships.
      if (language === "java" && type === "class_declaration") {
        const superclass = node.childForFieldName("superclass");
        if (superclass) {
          const parent = nodeText(superclass, source).replace(/^extends\s+/, "").trim();
          if (parent) result.inheritance.push({ class: getName(node, source), parent, line });
        }
        const interfaces = node.childForFieldName("interfaces");
        if (interfaces) {
          for (const child of interfaces.namedChildren || []) {
            const interfaceName = nodeText(child, source).trim();
            if (interfaceName) result.implementations.push({
              class: getName(node, source), interface: interfaceName, line
            });
          }
        }
      }

      if (language === "java" && type === "field_declaration") {
        const fieldType = node.childForFieldName("type");
        const declarators = (node.namedChildren || []).filter(child => child.type === "variable_declarator");
        const declaredType = fieldType ? nodeText(fieldType, source).replace(/<.*>$/, "").trim() : "";
        if (declaredType && /^[A-Za-z_$][\w$]*$/.test(declaredType)) {
          for (const declarator of declarators) {
            const fieldName = getName(declarator, source);
            if (fieldName) result.typed_fields.push({ class: currentClass, name: fieldName, type: declaredType, line });
          }
        }
      }

      if (language === "java" && type === "formal_parameter" && currentFunction) {
        const typeNode = node.childForFieldName("type");
        const nameNode = node.childForFieldName("name");
        const declaredType = typeNode ? nodeText(typeNode, source).replace(/<.*>$/, "").trim() : "";
        const variableName = nameNode ? nodeText(nameNode, source).trim() : "";
        if (variableName && declaredType && /^[A-Za-z_$][\w$]*$/.test(declaredType)) {
          result.typed_variables.push({ class: currentClass, function: currentFunction, name: variableName, type: declaredType, line });
        }
      }

      if (language === "java" && type === "local_variable_declaration" && currentFunction) {
        const typeNode = node.childForFieldName("type");
        const declaredType = typeNode ? nodeText(typeNode, source).replace(/<.*>$/, "").trim() : "";
        if (declaredType && /^[A-Za-z_$][\w$]*$/.test(declaredType)) {
          for (const declarator of (node.namedChildren || []).filter(child => child.type === "variable_declarator")) {
            const variableName = getName(declarator, source);
            if (variableName) result.typed_variables.push({ class: currentClass, function: currentFunction, name: variableName, type: declaredType, line });
          }
        }
      }

      if (language === "java" && type === "method_invocation") {
        const nameNode = node.childForFieldName("name");
        const objectNode = node.childForFieldName("object");
        const argumentsNode = node.childForFieldName("arguments");
        const name = nameNode ? nodeText(nameNode, source).trim() : null;
        const receiver = objectNode ? nodeText(objectNode, source).trim() : null;
        const argumentNodes = argumentsNode ? (argumentsNode.namedChildren || []) : [];
        const argumentCount = argumentsNode ? argumentNodes.length : null;
        const argumentTexts = argumentNodes.map(argument => nodeText(argument, source).trim());
        if (name && currentFunction) {
          result.calls.push({
            name, called_from: currentFunction,
            called_from_line: currentFunctionLine,
            called_from_class: currentClass, line,
            call_type: receiver ? "attribute" : "direct",
            expression: nodeText(node, source),
            receiver: receiver || null,
            argument_count: argumentCount,
            argument_texts: argumentTexts
          });
        }
      }

      for (const child of node.namedChildren || []) {
        visit(child, currentClass, currentFunction, currentFunctionLine);
      }
    }

    visit(root);
    parser.delete();
  } catch (error) {
    result.error = error?.stack || String(error);
  }
  process.stdout.write(JSON.stringify(result));
}

main().catch(error => {
  process.stderr.write(error?.stack || String(error));
  process.exitCode = 1;
});
