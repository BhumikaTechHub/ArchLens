# ArchLens

## AI-Powered Software Architecture & Knowledge Explorer

ArchLens analyzes source repositories, builds an architecture graph, indexes code, and provides repository-aware question answering.

## Language support

ArchLens uses Python's AST for Python, the official TypeScript compiler API for JavaScript/JSX/TypeScript/TSX, and Tree-sitter WebAssembly grammars for the other configured languages.

| Language | File extensions | Current support |
|---|---|---|
| Python | `.py` | AST analysis and declaration-aware chunks |
| JavaScript | `.js`, `.mjs`, `.cjs` | TypeScript compiler AST: imports, declarations, calls, class heritage, and declaration chunks |
| TypeScript | `.ts` | TypeScript compiler AST: imports, declarations, calls, class heritage, and declaration chunks |
| JSX / TSX | `.jsx`, `.tsx` | TypeScript compiler AST using JSX/TSX syntax mode |
| Java | `.java` | WASM syntax analysis and declaration chunks |
| C# | `.cs` | WASM syntax analysis and declaration chunks |
| Go | `.go` | WASM syntax analysis and declaration chunks |
| C | `.c`, `.h` | WASM syntax analysis and declaration chunks |
| C++ | `.cc`, `.cpp`, `.cxx`, `.hpp`, `.hh`, `.hxx` | WASM syntax analysis and declaration chunks |
| Rust | `.rs` | WASM syntax analysis and declaration chunks |
| PHP | `.php` | WASM syntax analysis and declaration chunks |
| Ruby | `.rb` | WASM syntax analysis and declaration chunks |
| Kotlin | `.kt`, `.kts` | WASM syntax analysis and declaration chunks |
| Swift | `.swift` | WASM syntax analysis and declaration chunks |

**Support-level note:** JavaScript/TypeScript parsing is performed by the TypeScript compiler API through Node.js; it no longer uses the native Tree-sitter Python binding. Java, C#, Go, C, C++, Rust, PHP, Ruby, Kotlin, and Swift use the Tree-sitter WebAssembly adapter, which extracts common declarations and imports. The WebAssembly parser runs in a separate Node.js process instead of loading the native Python Tree-sitter binding. This improves process isolation but does not make generic-language extraction equivalent to full language-specific semantic analysis. C header files (`.h`) are currently treated as C; C++ header extensions are mapped to C++.

## Core capabilities

- Repository import from public GitHub HTTPS URLs
- Python AST, TypeScript compiler AST, and Tree-sitter WebAssembly source analysis
- File, class, interface, and function extraction where supported by the grammar
- Import statement extraction
- Architecture graph generation
- Language-tagged file and declaration chunks
- ChromaDB vector indexing
- Repository-scoped semantic retrieval
- RAG question answering with Ollama
- FastAPI backend and interactive web frontend

## Processing flow

```text
GitHub Repository
       |
       v
Language / Extension Registry
       |
       +--> Python AST Parser
       |
       +--> TypeScript compiler API (JS / JSX / TS / TSX)
       |
       +--> Tree-sitter WASM Parsers (Java / C# / Go / C / C++ / Rust / PHP / Ruby / Kotlin / Swift)
       |
       v
Normalized Analysis Records
       |
       +--> Architecture Graph
       |
       +--> Language-aware Code Chunks
                    |
                    v
              Embeddings
                    |
                    v
                 ChromaDB
                    |
                    v
          Repository-aware Retrieval
                    |
                    v
               Ollama LLM
                    |
                    v
              FastAPI / UI
```

## Technology stack

- Python, FastAPI
- Python AST
- TypeScript compiler API (Node.js)
- Tree-sitter WebAssembly
- ChromaDB
- Ollama
- `nomic-embed-text` embeddings
- Qwen 2.5 Coder (configurable)
- HTML, CSS, JavaScript

## Run locally

Install dependencies (Node.js 18+ is required for JavaScript/TypeScript/JSX/TSX and WebAssembly-based language parsing):

```bash
npm install
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Start the backend:

```bash
uvicorn backend.app:app --reload
```

For Docker, use:

```bash
docker compose up --build
```

The backend expects Ollama to be available at `OLLAMA_URL` (defaults to `http://localhost:11434`). In Docker Compose, the configured host URL is `http://host.docker.internal:11434`.

## Tests

Run the parser and language chunking tests:

```bash
pytest -q
```

The multi-language tests verify that configured grammars load and representative source files produce language-tagged chunks. They are not a substitute for evaluation on unfamiliar repositories.

### Evaluate an unfamiliar repository

Run the structural evaluation report against a local repository:

```bash
python scripts/evaluate_repository.py /path/to/target-repository --output archlens-evaluation.json
```

The report includes parse success rate, files and declarations by language, chunk counts, graph relationship counts, unresolved calls/relationships, and any cross-language edges present in the graph. It is a coverage and diagnostics report, not a semantic-accuracy score. Review representative results manually before making accuracy claims.

## Current limitations

- WASM grammar parsing is isolated from Python's native bindings, but extraction remains conservative and is not production-grade semantic analysis for every language. JavaScript/TypeScript uses the TypeScript compiler AST; other non-Python languages still use generic Tree-sitter extraction.
- Cross-file inheritance and interface implementation are resolved only when a referenced symbol has one unique definition; ambiguous matches are reported rather than guessed.
- Python and JavaScript/TypeScript import-to-class links remain limited to the import forms currently extracted by their parsers.
- Cross-file call resolution currently supports Python `from ... import ...` function/class aliases and JavaScript/TypeScript relative named imports for functions and class-qualified methods.
- Python object-instance method resolution currently handles simple constructor assignments only; reassignment, factory-returned objects, and complex data flow are not modeled.
- Python-to-Java (and other cross-language) call or service relationship resolution is not implemented. Parsing both languages in one repository does not mean ArchLens understands how their components communicate.
- Default/namespace imports, re-exports, package-specific module rules, and cross-file calls for the generic Tree-sitter languages are not yet implemented.
- Code chunking and indexing are language-aware, but retrieval quality must be evaluated per language.
- Large repositories may require chunk-size limits, incremental indexing, and resource controls.
- Private GitHub repositories and authenticated Git providers are not currently supported by the import endpoint.
