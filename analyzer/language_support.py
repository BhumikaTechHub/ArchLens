"""Central registry for languages and source-file extensions supported by ArchLens."""

LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".jsx": "tsx", ".ts": "typescript", ".tsx": "tsx",
    ".java": "java", ".cs": "csharp", ".go": "go",
    ".c": "c", ".h": "c", ".cc": "cpp", ".cpp": "cpp",
    ".cxx": "cpp", ".hpp": "cpp", ".hh": "cpp", ".hxx": "cpp",
    ".rs": "rust", ".php": "php", ".rb": "ruby",
    ".kt": "kotlin", ".kts": "kotlin", ".swift": "swift",
}

# Tree-sitter language-pack grammar identifiers. Kept separate from display names.
TREE_SITTER_LANGUAGES = {
    "javascript", "typescript", "tsx", "java", "csharp", "go",
    "c", "cpp", "rust", "php", "ruby", "kotlin", "swift",
}
