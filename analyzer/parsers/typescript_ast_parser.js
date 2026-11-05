#!/usr/bin/env node
"use strict";

// Uses the official TypeScript compiler parser for JavaScript, JSX, TypeScript,
// and TSX. This avoids the native Tree-sitter binding used by the old adapter.
const fs = require("node:fs");
const path = require("node:path");
const ts = require("typescript");

const filePath = process.argv[2];
const language = process.argv[3] || "javascript";
if (!filePath) {
  process.stderr.write("Usage: node typescript_ast_parser.js <file> <language>\n");
  process.exit(2);
}

const source = fs.readFileSync(filePath, "utf8");
const scriptKind = language === "tsx" ? ts.ScriptKind.TSX
  : language === "typescript" ? ts.ScriptKind.TS
  : language === "jsx" ? ts.ScriptKind.JSX : ts.ScriptKind.JS;
const sourceFile = ts.createSourceFile(
  path.basename(filePath), source, ts.ScriptTarget.Latest, true, scriptKind
);

const result = {
  file: filePath,
  language,
  imports: [],
  import_details: [],
  classes: [],
  interfaces: [],
  functions: [],
  calls: [],
  inheritance: [],
  implementations: [],
  declaration_chunks: []
};

function lineOf(node) {
  return sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1;
}
function endLineOf(node) {
  return sourceFile.getLineAndCharacterOfPosition(node.end).line + 1;
}
function textOf(node) {
  return node ? node.getText(sourceFile) : "";
}
function parameterNames(parameters) {
  return parameters.map((parameter) => {
    const name = parameter.name;
    let value = textOf(name);
    if (ts.isIdentifier(name) && parameter.dotDotDotToken) value = "..." + value;
    return value;
  });
}
function addChunk(node, kind, name, className) {
  const code = textOf(node);
  if (!code.trim()) return;
  result.declaration_chunks.push({
    type: kind,
    name: name || "<anonymous:" + kind + ">",
    class_name: className || null,
    line: lineOf(node),
    end_line: endLineOf(node),
    code
  });
}
function importDeclaration(node) {
  const module = node.moduleSpecifier && ts.isStringLiteral(node.moduleSpecifier)
    ? node.moduleSpecifier.text : null;
  if (!module) return;
  result.imports.push(module);
  const line = lineOf(node);
  const clause = node.importClause;
  if (!clause) {
    result.import_details.push({
      type: "import", module, name: null, alias: null,
      import_kind: "side_effect", line, level: 0
    });
    return;
  }
  if (clause.name) {
    result.import_details.push({
      type: "import", module, name: null, alias: clause.name.text,
      import_kind: "default", line, level: 0
    });
  }
  if (clause.namedBindings && ts.isNamespaceImport(clause.namedBindings)) {
    result.import_details.push({
      type: "import", module, name: null,
      alias: clause.namedBindings.name.text,
      import_kind: "namespace", line, level: 0
    });
  } else if (clause.namedBindings && ts.isNamedImports(clause.namedBindings)) {
    for (const element of clause.namedBindings.elements) {
      result.import_details.push({
        type: "import", module, name: element.propertyName
          ? element.propertyName.text : element.name.text,
        alias: element.propertyName ? element.name.text : null,
        import_kind: "named", line, level: 0
      });
    }
  }
}
function functionInfo(node, className) {
  let name = null;
  if (node.name && ts.isIdentifier(node.name)) name = node.name.text;
  if (!name && (ts.isArrowFunction(node) || ts.isFunctionExpression(node))) {
    const parent = node.parent;
    if (parent && ts.isVariableDeclaration(parent) && ts.isIdentifier(parent.name)) {
      name = parent.name.text;
    } else if (parent && ts.isPropertyAssignment(parent)) {
      name = textOf(parent.name);
    }
  }
  if (!name && ts.isConstructorDeclaration(node)) name = "constructor";
  return {
    name: name || "<anonymous>",
    line: lineOf(node),
    arguments: parameterNames(node.parameters || []),
    class: className || null
  };
}

function visit(node, currentFunction = null, currentFunctionLine = null, currentClass = null) {
  if (ts.isImportDeclaration(node)) importDeclaration(node);

  if (ts.isClassDeclaration(node) || ts.isClassExpression(node)) {
    const name = node.name ? node.name.text : "<anonymous>";
    result.classes.push({ name, line: lineOf(node) });
    addChunk(node, "class", name, currentClass);
    for (const clause of node.heritageClauses || []) {
      for (const type of clause.types) {
        const target = textOf(type.expression);
        if (clause.token === ts.SyntaxKind.ExtendsKeyword) {
          result.inheritance.push({ class: name, parent: target, line: lineOf(node) });
        } else if (clause.token === ts.SyntaxKind.ImplementsKeyword) {
          result.implementations.push({ class: name, interface: target, line: lineOf(node) });
        }
      }
    }
    currentClass = name;
  }

  if (ts.isInterfaceDeclaration(node)) {
    const name = node.name.text;
    result.interfaces.push({ name, line: lineOf(node) });
    addChunk(node, "class", name, currentClass);
  }

  let isFunction = ts.isFunctionDeclaration(node) ||
    ts.isMethodDeclaration(node) || ts.isConstructorDeclaration(node) ||
    ts.isArrowFunction(node) || ts.isFunctionExpression(node);
  if (isFunction) {
    const info = functionInfo(node, currentClass);
    result.functions.push(info);
    addChunk(node, "function", info.name, currentClass);
    currentFunction = info.name;
    currentFunctionLine = info.line;
  }

  if (ts.isCallExpression(node) || ts.isNewExpression(node)) {
    const expression = node.expression;
    let name = textOf(expression);
    let receiver = null;
    let callType = "direct";
    if (ts.isPropertyAccessExpression(expression)) {
      receiver = textOf(expression.expression);
      name = expression.name.text;
      callType = "attribute";
    } else if (ts.isElementAccessExpression(expression)) {
      receiver = textOf(expression.expression);
      name = textOf(expression.argumentExpression) || name;
      callType = "attribute";
    }
    result.calls.push({
      name,
      called_from: currentFunction,
      called_from_line: currentFunctionLine,
      called_from_class: currentClass,
      line: lineOf(node),
      call_type: ts.isNewExpression(node) ? "constructor" : callType,
      expression: textOf(expression),
      receiver: ts.isNewExpression(node) ? null : receiver
    });
  }

  ts.forEachChild(node, child =>
    visit(child, currentFunction, currentFunctionLine, currentClass)
  );
}

visit(sourceFile);
const diagnostics = sourceFile.parseDiagnostics || [];
if (diagnostics.length) {
  result.parse_errors = true;
  result.parse_diagnostics = diagnostics.slice(0, 50).map(diagnostic => ({
    line: diagnostic.start == null ? null
      : sourceFile.getLineAndCharacterOfPosition(diagnostic.start).line + 1,
    message: ts.flattenDiagnosticMessageText(diagnostic.messageText, "\n")
  }));
}
process.stdout.write(JSON.stringify(result));
