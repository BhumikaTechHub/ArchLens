import json
import os
import requests
import chromadb
import re
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
EMBEDDING_MODEL = "nomic-embed-text"

# Change this if you want another installed model.
# Example:
# LLM_MODEL = "smollm2:360m"
LLM_MODEL = os.getenv(
    "LLM_MODEL",
    "qwen2.5-coder:3b"
)

COLLECTION_NAME = "archlens_code"

VECTOR_DB_FOLDER = "vector_db"

TOP_K = 8

ALLOWED_REPOSITORIES = {
    "ecommerce",
    "auth_system",
    "task_manager"
}

BASE_DIR = Path(__file__).resolve().parent.parent
# ============================================================
# EMBEDDING
# ============================================================

def get_embedding(text):

    response = requests.post(
        f"{OLLAMA_URL}/api/embed",
        json={
            "model": EMBEDDING_MODEL,
            "input": [text]
        },
        timeout=120
    )

    response.raise_for_status()

    data = response.json()

    if "embeddings" not in data:
        raise RuntimeError(
            f"Ollama embedding response is invalid: {data}"
        )

    return data["embeddings"][0]


# ============================================================
# REPOSITORY VALIDATION
# ============================================================

def validate_repository(repo_name):
    if (
        not isinstance(repo_name, str)
        or not re.fullmatch(r"[A-Za-z0-9_.-]+", repo_name)
        or repo_name in {".", ".."}
    ):
        raise ValueError("Invalid repository name.")

    # Existing sample repositories
    if repo_name in ALLOWED_REPOSITORIES:
        return

    # Imported repositories must have metadata and an indexed database.
    metadata_file = (
        BASE_DIR
        / "imported_repositories"
        / "metadata"
        / f"{repo_name}.json"
    )

    vector_db_dir = (
        BASE_DIR
        / "imported_repositories"
        / "generated"
        / repo_name
        / "vector_db"
    )

    if metadata_file.is_file() and vector_db_dir.is_dir():
        return

    raise ValueError(f"Repository not found or not indexed: {repo_name}")

# ============================================================
# GET REPOSITORY CHROMA COLLECTION
# ============================================================

def get_collection(repo_name):
    validate_repository(repo_name)

    if repo_name in ALLOWED_REPOSITORIES:
        vector_db_path = (
            BASE_DIR / VECTOR_DB_FOLDER / repo_name
        )
    else:
        vector_db_path = (
            BASE_DIR
            / "imported_repositories"
            / "generated"
            / repo_name
            / "vector_db"
        )

    if not vector_db_path.is_dir():
        raise ValueError(
            f"Vector database not found for repository: {repo_name}"
        )

    client = chromadb.PersistentClient(
        path=str(vector_db_path)
    )

    collection = client.get_collection(
        name=COLLECTION_NAME
    )

    return collection


# ============================================================
# RETRIEVE CODE
# ============================================================
def retrieve_code(
    question,
    repo_name,
    top_k=TOP_K
):

    collection = get_collection(repo_name)

    retrieved = []
    seen = set()

    # --------------------------------------------------
    # 1. SEMANTIC RETRIEVAL
    # --------------------------------------------------

    query_embedding = get_embedding(question)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for document, metadata, distance in zip(
        documents,
        metadatas,
        distances
    ):

        if metadata.get("repository") != repo_name:
            continue

        key = (
            metadata.get("file"),
            metadata.get("qualified_name"),
            metadata.get("type"),
            metadata.get("line")
        )

        if key in seen:
            continue

        seen.add(key)

        retrieved.append({
            "document": document,
            "file": metadata.get("file", "unknown"),
            "type": metadata.get("type", "unknown"),
            "name": metadata.get("name", "unknown"),
            "class_name": metadata.get("class_name"),
            "qualified_name": metadata.get("qualified_name"),
            "line": metadata.get("line", "unknown"),
            "end_line": metadata.get("end_line"),
            "repository": repo_name,
            "distance": distance
        })

    # --------------------------------------------------
    # 2. CLASS-AWARE RETRIEVAL
    # --------------------------------------------------

    graph = load_architecture_graph(repo_name)

    question_lower = question.lower()

    class_names = {
        node.get("label")
        for node in graph.get("nodes", [])
        if (
            node.get("type") == "class"
            and node.get("label")
            and node["label"].lower() in question_lower
        )
    }

    # Keep only useful semantic results.
    # Avoid test files unless the question explicitly asks about tests.
    if not any(word in question_lower for word in ["test", "tests", "testing"]):
        retrieved = [
            item for item in retrieved
            if not item["file"].replace("\\", "/").startswith("tests/")
        ]

    important_methods = {
        "__init__",
        "mount",
        "get_adapter",
        "send"
    }

    for class_name in class_names:

        class_results = collection.get(
            where={"class_name": class_name},
            include=["documents", "metadatas"]
        )

        class_documents = class_results.get("documents", [])
        class_metadatas = class_results.get("metadatas", [])

        candidates = []

        for document, metadata in zip(
            class_documents,
            class_metadatas
        ):

            if metadata.get("repository") != repo_name:
                continue

            if metadata.get("name") not in important_methods:
                continue

            if metadata.get("type") != "function":
                continue

            candidates.append((document, metadata))

        for document, metadata in candidates:

            key = (
                metadata.get("file"),
                metadata.get("qualified_name"),
                metadata.get("type"),
                metadata.get("line")
            )

            if key in seen:
                continue

            seen.add(key)

            retrieved.append({
                "document": document,
                "file": metadata.get("file", "unknown"),
                "type": metadata.get("type", "unknown"),
                "name": metadata.get("name", "unknown"),
                "class_name": metadata.get("class_name"),
                "qualified_name": metadata.get("qualified_name"),
                "line": metadata.get("line", "unknown"),
                "end_line": metadata.get("end_line"),
                "repository": repo_name,
                "distance": None
            })

    # --------------------------------------------------
    # 3. IMPORTED-CLASS RETRIEVAL
    # --------------------------------------------------

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    nodes_by_id = {
        node.get("id"): node
        for node in nodes
    }

    imported_class_names = set()

    for class_name in class_names:

        class_node_ids = {
            node.get("id")
            for node in nodes
            if (
                node.get("type") == "class"
                and node.get("label") == class_name
            )
        }

        containing_file_ids = {
            edge.get("source")
            for edge in edges
            if (
                edge.get("relationship") == "contains"
                and edge.get("target") in class_node_ids
            )
        }

        for edge in edges:

            if (
                edge.get("relationship") != "imports_symbol"
                or edge.get("source") not in containing_file_ids
            ):
                continue

            target_node = nodes_by_id.get(edge.get("target"), {})
            imported_name = target_node.get("label")

            if imported_name:
                imported_class_names.add(imported_name)

    # Match imported classes against words in the question.
    question_words = set(
        re.findall(r"[a-z]+", question_lower)
    )

    def class_name_words(name):
        name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", name)
        name = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
        return set(re.findall(r"[a-z]+", name.lower()))

    scored_classes = []

    for name in imported_class_names:
        score = len(class_name_words(name) & question_words)

        if score > 0:
            scored_classes.append((name, score))

    if scored_classes:

        best_score = max(score for _, score in scored_classes)

        relevant_imports = {
            name
            for name, score in scored_classes
            if score == best_score
        }

        adapter_methods = {
            "__init__",
            "send",
            "get_connection_with_tls_context",
            "cert_verify",
            "request_url",
            "build_response"
        }

        for imported_class in relevant_imports:

            imported_results = collection.get(
                where={"class_name": imported_class},
                include=["documents", "metadatas"]
            )

            for document, metadata in zip(
                imported_results.get("documents", []),
                imported_results.get("metadatas", [])
            ):

                if metadata.get("repository") != repo_name:
                    continue

                if metadata.get("type") != "function":
                    continue

                if metadata.get("name") not in adapter_methods:
                    continue

                key = (
                    metadata.get("file"),
                    metadata.get("qualified_name"),
                    metadata.get("type"),
                    metadata.get("line")
                )

                if key in seen:
                    continue

                seen.add(key)

                retrieved.append({
                    "document": document,
                    "file": metadata.get("file", "unknown"),
                    "type": metadata.get("type", "unknown"),
                    "name": metadata.get("name", "unknown"),
                    "class_name": metadata.get("class_name"),
                    "qualified_name": metadata.get("qualified_name"),
                    "line": metadata.get("line", "unknown"),
                    "end_line": metadata.get("end_line"),
                    "repository": repo_name,
                    "distance": None
                })
    # --------------------------------------------------
    # 4. REMOVE REDUNDANT FILE AND CLASS CHUNKS
    # --------------------------------------------------

    files_with_functions = {
        item["file"]
        for item in retrieved
        if item.get("type") == "function"
    }

    classes_with_functions = {
        (item["file"], item.get("class_name"))
        for item in retrieved
        if item.get("type") == "function"
    }

    retrieved = [
        item for item in retrieved
        if not (
            item.get("type") == "file"
            and item.get("file") in files_with_functions
        )
        and not (
            item.get("type") == "class"
            and (
                item.get("file"),
                item.get("name")
            ) in classes_with_functions
        )
    ]
    return retrieved

# ============================================================
# LOAD ARCHITECTURE GRAPH
# ============================================================

def load_architecture_graph(repo_name):

    validate_repository(repo_name)

    sample_graph = (
        BASE_DIR / f"architecture_graph_{repo_name}.json"
    )

    imported_graph = (
        BASE_DIR
        / "imported_repositories"
        / "generated"
        / repo_name
        / "architecture_graph.json"
    )

    if sample_graph.is_file():
        graph_file = sample_graph

    elif imported_graph.is_file():
        graph_file = imported_graph

    else:
        return {
            "nodes": [],
            "edges": []
        }

    try:

        with graph_file.open(
            "r",
            encoding="utf-8"
        ) as f:

            graph = json.load(f)

        if not isinstance(graph, dict):
            raise ValueError("Invalid architecture graph.")

        return graph

    except (OSError, json.JSONDecodeError, ValueError):

        return {
            "nodes": [],
            "edges": []
        }


# ============================================================
# FORMAT ARCHITECTURE RELATIONSHIPS
# ============================================================

def format_architecture_context(
    repo_name
):

    graph = load_architecture_graph(
        repo_name
    )

    nodes = graph.get(
        "nodes",
        []
    )

    edges = graph.get(
        "edges",
        []
    )

    if not nodes or not edges:
        return ""

    node_labels = {}

    for node in nodes:

        node_id = node.get(
            "id"
        )

        label = node.get(
            "label",
            node_id
        )

        if node_id:
            node_labels[node_id] = label

    relationships = []

    for edge in edges:

        source = edge.get(
            "source"
        )

        target = edge.get(
            "target"
        )

        relationship = edge.get(
            "relationship",
            "related_to"
        )

        source_label = node_labels.get(
            source,
            source
        )

        target_label = node_labels.get(
            target,
            target
        )

        relationships.append(
            f"{source_label} "
            f"--{relationship}--> "
            f"{target_label}"
        )

    if not relationships:
        return ""

    return "\n".join(
        relationships
    )

# ============================================================
# TARGETED GRAPH RETRIEVAL
# ============================================================

def get_relevant_graph_context(repo_name, question):

    graph = load_architecture_graph(repo_name)

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    if not nodes or not edges:
        return ""

    node_map = {
        node["id"]: node
        for node in nodes
        if node.get("id")
    }

    question_lower = question.lower()

    relevant_ids = {
        node_id
        for node_id, node in node_map.items()
        if (
            node.get("label")
            and len(node["label"]) > 2
            and node["label"].lower() in question_lower
        )
    }

    if not relevant_ids:
        return ""

    selected_edges = {}

    # Keep the class-to-file relationships.
    for edge in edges:

        source = edge.get("source")
        target = edge.get("target")

        if (
            edge.get("relationship") == "contains"
            and target in relevant_ids
        ):
            key = (source, target, "contains")
            selected_edges[key] = edge

    # Expand context through imported class relationships.
    relevant_file_ids = set()

    # Find files containing the relevant classes.
    for edge in edges:
        if (
            edge.get("relationship") == "contains"
            and edge.get("target") in relevant_ids
        ):
            relevant_file_ids.add(edge.get("source"))

    imported_class_ids = set()

    # Follow symbol-level imports from those files.
    for edge in edges:
        if (
            edge.get("relationship") == "imports_symbol"
            and edge.get("source") in relevant_file_ids
        ):
            target_id = edge.get("target")

            if target_id in node_map:
                imported_class_ids.add(target_id)

                selected_edges[
                    (edge.get("source"), target_id, "imports_symbol")
                ] = edge

    # Include relevant and imported classes.
    relevant_class_ids = relevant_ids | imported_class_ids
    relevant_method_ids = set()

    for edge in edges:
        if (
            edge.get("relationship") == "contains"
            and edge.get("source") in relevant_class_ids
        ):
            target_id = edge.get("target")
            target_node = node_map.get(target_id, {})

            if target_node.get("type") == "function":
                relevant_method_ids.add(target_id)

                selected_edges[
                    (edge.get("source"), target_id, "contains")
                ] = edge


    # Include calls made by those selected methods.
    for edge in edges:

        if (
            edge.get("relationship") == "calls"
            and edge.get("source") in relevant_method_ids
        ):

            key = (
                edge.get("source"),
                edge.get("target"),
                "calls"
            )
            selected_edges[key] = edge

    relationships = []

    for edge in selected_edges.values():

        source = node_map.get(edge.get("source"), {})
        target = node_map.get(edge.get("target"), {})

        relationships.append(
            f"{source.get('label', edge.get('source'))} "
            f"--{edge.get('relationship')}--> "
            f"{target.get('label', edge.get('target'))}"
        )

    return "\n".join(relationships)

# ============================================================
# FORMAT CODE CONTEXT
# ============================================================

def format_code_context(
    retrieved
):

    context_parts = []

    for item in retrieved:

        context_parts.append(
            f"""
FILE: {item['file']}
TYPE: {item['type']}
NAME: {item['name']}
LINE: {item['line']}

CODE:
{item['document']}
"""
        )

    return "\n".join(
        context_parts
    )


# ============================================================
# GENERATE ANSWER
# ============================================================

def generate_answer(
    question,
    repo_name,
    retrieved
):

    code_context = format_code_context(
        retrieved
    )

    architecture_context = get_relevant_graph_context(repo_name, question)

    if not code_context and not architecture_context:

        return (
            "I don't have enough information "
            "in the analyzed repository."
        )

    prompt = f"""
You are ArchLens, an AI software architecture
and code knowledge assistant.

Repository:
{repo_name}

Your task is to answer the user's question
using ONLY the repository information provided below.

IMPORTANT RULES:

1. Do not invent files, functions, classes,
   APIs, dependencies, or relationships.

2. Do not use outside knowledge.

3. Prefer the architecture relationships when
   the question asks about calls, dependencies,
   imports, or execution flow.

4. Use the code context to explain the actual
   implementation.

5. If the repository context does not contain
   enough information, say exactly:

"I don't have enough information in the analyzed repository."

6. Do not use information from another repository.

7. When describing a flow, mention the actual
   function names and classes found in the repository.

8. Keep the answer concise but complete.

9. Never create hypothetical classes, functions,
   variables, or code examples.

10. Clearly distinguish actual repository
    implementation from general explanations.

11. When explaining a class, describe its actual
    methods and responsibilities using retrieved code.

12. When explaining relationships, identify the
    actual caller and called function or class.

13. If a relationship cannot be verified from the
    provided context, do not claim that it exists.

ARCHITECTURE RELATIONSHIPS:
{architecture_context}

REPOSITORY CODE:
{code_context}

USER QUESTION:
{question}

ANSWER FORMAT:

- Explain the actual implementation first.
- Mention relevant classes and methods.
- Explain verified relationships where available.
- Include source file names.
- Do not generate hypothetical code examples.

ANSWER:
"""

    response = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": LLM_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0,
                "num_predict": 350
            }
        },
        timeout=300
    )

    response.raise_for_status()

    data = response.json()

    answer = data.get(
        "response",
        ""
    ).strip()

    if not answer:

        return (
            "I don't have enough information "
            "in the analyzed repository."
        )

    return answer


# ============================================================
# MAIN RAG PIPELINE
# ============================================================

def ask(
    question,
    repo_name
):

    question = question.strip()

    if not question:

        return {
            "question": question,
            "repository": repo_name,
            "answer": "Please enter a question.",
            "sources": [],
            "retrieved_context": []
        }

    validate_repository(
        repo_name
    )

    # --------------------------------------------------------
    # RETRIEVE
    # --------------------------------------------------------

    retrieved = retrieve_code(
        question,
        repo_name
    )

    # --------------------------------------------------------
    # GENERATE
    # --------------------------------------------------------

    answer = generate_answer(
        question,
        repo_name,
        retrieved
    )

    # --------------------------------------------------------
    # SOURCES
    # --------------------------------------------------------

    sources = []

    for item in retrieved:

        file_name = item.get(
            "file"
        )

        if (
            file_name
            and file_name not in sources
        ):

            sources.append(
                file_name
            )

    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

    return {
        "question": question,
        "repository": repo_name,
        "answer": answer,
        "model": LLM_MODEL,
        "sources": sources,
        "retrieved_context": retrieved
    }
