import json
import os
import requests
import chromadb


# ============================================================
# CONFIGURATION
# ============================================================

OLLAMA_URL = "http://localhost:11434"

EMBEDDING_MODEL = "nomic-embed-text"

# Change this if you want another installed model.
# Example:
# LLM_MODEL = "smollm2:360m"
LLM_MODEL = os.getenv(
    "LLM_MODEL",
    "qwen2.5:1.5b"
)

COLLECTION_NAME = "archlens_code"

VECTOR_DB_FOLDER = "vector_db"

TOP_K = 3

ALLOWED_REPOSITORIES = {
    "ecommerce",
    "auth_system",
    "task_manager"
}


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

    if repo_name not in ALLOWED_REPOSITORIES:
        raise ValueError(
            f"Unknown repository '{repo_name}'. "
            f"Available repositories: "
            f"{', '.join(sorted(ALLOWED_REPOSITORIES))}"
        )


# ============================================================
# GET REPOSITORY CHROMA COLLECTION
# ============================================================

def get_collection(repo_name):

    validate_repository(repo_name)

    vector_db_path = os.path.join(
        VECTOR_DB_FOLDER,
        repo_name
    )

    if not os.path.exists(vector_db_path):
        raise RuntimeError(
            f"Vector database not found for repository "
            f"'{repo_name}'. "
            f"Expected: {vector_db_path}"
        )

    client = chromadb.PersistentClient(
        path=vector_db_path
    )

    try:

        collection = client.get_collection(
            name=COLLECTION_NAME
        )

    except Exception as e:

        raise RuntimeError(
            f"Chroma collection '{COLLECTION_NAME}' "
            f"not found for repository '{repo_name}'. "
            f"Run the indexing step first."
        ) from e

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

    query_embedding = get_embedding(question)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )

    documents = results.get(
        "documents",
        [[]]
    )[0]

    metadatas = results.get(
        "metadatas",
        [[]]
    )[0]

    distances = results.get(
        "distances",
        [[]]
    )[0]

    retrieved = []

    for document, metadata, distance in zip(
        documents,
        metadatas,
        distances
    ):

        # Extra safety:
        # Ignore a chunk if it belongs to another repository.
        if metadata.get("repository") != repo_name:
            continue

        retrieved.append(
            {
                "document": document,
                "file": metadata.get(
                    "file",
                    "unknown"
                ),
                "type": metadata.get(
                    "type",
                    "unknown"
                ),
                "name": metadata.get(
                    "name",
                    "unknown"
                ),
                "line": metadata.get(
                    "line",
                    "unknown"
                ),
                "repository": metadata.get(
                    "repository",
                    repo_name
                ),
                "distance": distance
            }
        )

    return retrieved


# ============================================================
# LOAD ARCHITECTURE GRAPH
# ============================================================

def load_architecture_graph(repo_name):

    validate_repository(repo_name)

    graph_file = (
        f"architecture_graph_{repo_name}.json"
    )

    if not os.path.exists(graph_file):
        return {
            "nodes": [],
            "edges": []
        }

    try:

        with open(
            graph_file,
            "r",
            encoding="utf-8"
        ) as f:

            graph = json.load(f)

        return graph

    except Exception:

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

    architecture_context = (
        format_architecture_context(
            repo_name
        )
    )

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
   function names.

8. Keep the answer concise but complete.

ARCHITECTURE RELATIONSHIPS:
{architecture_context}

REPOSITORY CODE:
{code_context}

USER QUESTION:
{question}

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
                "num_predict": 180
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
