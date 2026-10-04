import json
import os
import re

import chromadb
import requests


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CHROMA_FOLDER = os.path.join(BASE_DIR, "vector_db")
COLLECTION_NAME = "archlens_code"

ARCHITECTURE_FILE = os.path.join(
    BASE_DIR,
    "architecture_graph.json"
)

OLLAMA_URL = "http://localhost:11434"

EMBEDDING_MODEL = "nomic-embed-text"

# Recommended LLM for ArchLens
LLM_MODEL = "qwen2.5:1.5b"

TOP_K = 3

# Project-level retrieval threshold
RETRIEVAL_DISTANCE_THRESHOLD = 0.8


# ============================================================
# EMBEDDING
# ============================================================

def get_embedding(text):
    """
    Generate an embedding for the user's question
    using Ollama's embedding model.
    """

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
            f"Embedding response did not contain embeddings: {data}"
        )

    return data["embeddings"][0]


# ============================================================
# CODE RETRIEVAL
# ============================================================

def retrieve_code(question, top_k=TOP_K):
    """
    Retrieve the most relevant code chunks from ChromaDB.
    """

    client = chromadb.PersistentClient(
        path=CHROMA_FOLDER
    )

    collection = client.get_collection(
        name=COLLECTION_NAME
    )

    embedding = get_embedding(question)

    results = collection.query(
        query_embeddings=[embedding],
        n_results=top_k
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    retrieved = []

    for document, metadata, distance in zip(
        documents,
        metadatas,
        distances
    ):

        retrieved.append({
            "document": document,
            "file": metadata.get("file"),
            "type": metadata.get("type"),
            "name": metadata.get("name"),
            "distance": distance
        })

    return retrieved


# ============================================================
# ARCHITECTURE GRAPH
# ============================================================

def load_architecture_graph():
    """
    Load architecture_graph.json.

    If the graph does not exist, return an empty graph
    instead of crashing the entire RAG pipeline.
    """

    if not os.path.exists(ARCHITECTURE_FILE):
        return {
            "nodes": [],
            "edges": []
        }

    try:

        with open(
            ARCHITECTURE_FILE,
            "r"
        ) as f:

            return json.load(f)

    except Exception as error:

        print(
            f"Warning: Could not load architecture graph: {error}"
        )

        return {
            "nodes": [],
            "edges": []
        }


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(text):
    """
    Convert names such as:

        create_order

    into searchable words:

        create order
    """

    text = text.lower()

    text = text.replace("_", " ")
    text = text.replace("-", " ")
    text = text.replace(".", " ")

    return text


def get_words(text):
    """
    Extract useful words from text.
    """

    normalized = normalize_text(text)

    return set(
        re.findall(
            r"[a-zA-Z0-9]+",
            normalized
        )
    )


# ============================================================
# ARCHITECTURE QUESTION DETECTION
# ============================================================

def is_architecture_question(question):
    """
    Detect whether the question is asking about
    architecture relationships.
    """

    question_lower = question.lower()

    architecture_terms = [
        "call",
        "calls",
        "called",
        "calling",
        "depend",
        "depends",
        "dependency",
        "dependencies",
        "import",
        "imports",
        "module",
        "modules",
        "relationship",
        "relationships",
        "connected",
        "connection",
        "flow",
        "architecture",
        "component",
        "components",
        "function",
        "functions",
        "happens when",
        "what happens",
        "execution",
        "sequence"
    ]

    for term in architecture_terms:

        if term in question_lower:
            return True

    return False


# ============================================================
# ARCHITECTURE CONTEXT
# ============================================================

def get_architecture_context(question):
    """
    Find relevant architecture relationships from
    architecture_graph.json.

    Examples:

        create_order
             |
             +--> save_order
             +--> process_payment
             +--> send_notification

    and:

        order_service.py
             |
             +--> payment
             +--> database
             +--> notification
    """

    graph = load_architecture_graph()

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    if not nodes or not edges:
        return ""

    question_lower = question.lower()
    question_words = get_words(question)

    # --------------------------------------------------------
    # Build node lookup
    # --------------------------------------------------------

    node_lookup = {
        node.get("id"): node
        for node in nodes
    }

    # --------------------------------------------------------
    # Find relevant nodes
    # --------------------------------------------------------

    relevant_node_ids = set()

    for node in nodes:

        node_id = node.get("id", "")
        label = node.get("label", "")

        if not label:
            continue

        label_lower = label.lower()

        # Exact match
        if label_lower in question_lower:
            relevant_node_ids.add(node_id)
            continue

        # Normalized match
        normalized_label = normalize_text(label)

        if normalized_label in question_lower:
            relevant_node_ids.add(node_id)
            continue

        # Word overlap
        label_words = get_words(label)

        meaningful_words = {
            word
            for word in label_words
            if len(word) >= 4
        }

        overlap = meaningful_words.intersection(
            question_words
        )

        if overlap:
            relevant_node_ids.add(node_id)

    # --------------------------------------------------------
    # Special handling for "order is created" questions
    # --------------------------------------------------------

    if (
        "order" in question_words
        and (
            "created" in question_words
            or "create" in question_words
            or "creating" in question_words
            or "creation" in question_words
        )
    ):

        for node in nodes:

            label = node.get(
                "label",
                ""
            ).lower()

            if "create_order" in label:
                relevant_node_ids.add(
                    node["id"]
                )

            elif "order_service" in label:
                relevant_node_ids.add(
                    node["id"]
                )

    # --------------------------------------------------------
    # Special handling for save/notify questions
    # --------------------------------------------------------

    if "order" in question_words:

        for node in nodes:

            label = node.get(
                "label",
                ""
            ).lower()

            if any(
                keyword in label
                for keyword in [
                    "create_order",
                    "save_order",
                    "process_payment",
                    "send_notification",
                    "order_service"
                ]
            ):

                relevant_node_ids.add(
                    node["id"]
                )

    # --------------------------------------------------------
    # If this is an architecture question but no exact node
    # was found, inspect function/call relationships.
    # --------------------------------------------------------

    if (
        is_architecture_question(question)
        and not relevant_node_ids
    ):

        for edge in edges:

            relationship = edge.get(
                "relationship"
            )

            if relationship in [
                "calls",
                "imports",
                "contains"
            ]:

                relevant_node_ids.add(
                    edge["source"]
                )

                relevant_node_ids.add(
                    edge["target"]
                )

    # --------------------------------------------------------
    # Find related edges
    # --------------------------------------------------------

    related_edges = []

    for edge in edges:

        source = edge.get(
            "source"
        )

        target = edge.get(
            "target"
        )

        relationship = edge.get(
            "relationship"
        )

        if (
            source in relevant_node_ids
            or target in relevant_node_ids
        ):

            related_edges.append(
                edge
            )

    # --------------------------------------------------------
    # For architecture questions involving order, include
    # all order-related call relationships.
    # --------------------------------------------------------

    if "order" in question_words:

        for edge in edges:

            if edge.get(
                "relationship"
            ) != "calls":

                continue

            source_node = node_lookup.get(
                edge.get("source")
            )

            target_node = node_lookup.get(
                edge.get("target")
            )

            if not source_node or not target_node:
                continue

            source_label = source_node.get(
                "label",
                ""
            ).lower()

            target_label = target_node.get(
                "label",
                ""
            ).lower()

            if (
                "order" in source_label
                or "order" in target_label
            ):

                related_edges.append(
                    edge
                )

    # --------------------------------------------------------
    # Remove duplicate edges
    # --------------------------------------------------------

    unique_edges = []

    seen = set()

    for edge in related_edges:

        key = (
            edge.get("source"),
            edge.get("target"),
            edge.get("relationship")
        )

        if key not in seen:

            seen.add(key)
            unique_edges.append(edge)

    # --------------------------------------------------------
    # Convert graph relationships into readable text
    # --------------------------------------------------------

    context_lines = []

    for edge in unique_edges:

        source_node = node_lookup.get(
            edge.get("source")
        )

        target_node = node_lookup.get(
            edge.get("target")
        )

        if not source_node or not target_node:
            continue

        source_label = source_node.get(
            "label",
            edge.get("source")
        )

        target_label = target_node.get(
            "label",
            edge.get("target")
        )

        relationship = edge.get(
            "relationship"
        )

        source_file = source_node.get(
            "file"
        )

        target_file = target_node.get(
            "file"
        )

        if source_file and target_file:

            context_lines.append(
                f"{source_label} "
                f"({source_file}) "
                f"--{relationship}--> "
                f"{target_label} "
                f"({target_file})"
            )

        elif source_file:

            context_lines.append(
                f"{source_label} "
                f"({source_file}) "
                f"--{relationship}--> "
                f"{target_label}"
            )

        else:

            context_lines.append(
                f"{source_label} "
                f"--{relationship}--> "
                f"{target_label}"
            )

    # Remove duplicates while preserving order
    context_lines = list(
        dict.fromkeys(
            context_lines
        )
    )

    return "\n".join(
        context_lines
    )


# ============================================================
# LLM GENERATION
# ============================================================

def generate_answer(
    question,
    retrieved,
    architecture_context=""
):
    """
    Generate the final answer using:

    1. Retrieved code
    2. Architecture relationships
    """

    if not retrieved and not architecture_context:

        return (
            "I don't have enough information in "
            "the analyzed repository."
        )

    # --------------------------------------------------------
    # Build code context
    # --------------------------------------------------------

    context_parts = []

    for item in retrieved:

        context_parts.append(
            f"""
FILE: {item['file']}
TYPE: {item['type']}
NAME: {item['name']}
DISTANCE: {item['distance']}

CODE:
{item['document']}
"""
        )

    code_context = "\n".join(
        context_parts
    )

    # --------------------------------------------------------
    # Architecture context
    # --------------------------------------------------------

    if not code_context:
        code_context = (
            "No relevant code chunks were retrieved."
        )

    if not architecture_context:
        architecture_context = (
            "No specific architecture relationships "
            "were found for this question."
        )

    # --------------------------------------------------------
    # RAG prompt
    # --------------------------------------------------------

    prompt = f"""
You are ArchLens, an AI software architecture assistant.

Your job is to explain the analyzed software repository.

Use ONLY the repository information provided below.

You have two sources of repository information:

1. CODE CONTEXT
2. ARCHITECTURE RELATIONSHIPS

The architecture relationships describe actual relationships
between repository components, such as:

- imports
- contains
- calls

IMPORTANT RULES:

1. Do not invent files, functions, classes, modules,
   dependencies, or behavior.

2. Do not use outside knowledge.

3. When the question asks about function calls,
   prioritize the "calls" architecture relationships.

4. When the question asks about dependencies,
   prioritize the "imports" architecture relationships.

5. When explaining what happens during a process,
   use the code context to understand the sequence.

6. If architecture relationships and code context both
   contain the answer, combine them.

7. If the repository does not contain enough information,
   say exactly:

"I don't have enough information in the analyzed repository."

8. Do not replace a missing repository fact with a guess.

9. Keep the answer concise.

10. Mention relevant files, classes, or functions when useful.

11. If several functions are called, list all of them.

12. If the code clearly shows an execution sequence,
    explain the sequence in that order.

============================================================
CODE CONTEXT
============================================================

{code_context}

============================================================
ARCHITECTURE RELATIONSHIPS
============================================================

{architecture_context}

============================================================
USER QUESTION
============================================================

{question}

============================================================
ANSWER
============================================================
"""

    # --------------------------------------------------------
    # Call Ollama
    # --------------------------------------------------------

    response = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": LLM_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0,
                "num_predict": 200
            }
        },
        timeout=240
    )

    response.raise_for_status()

    data = response.json()

    answer = data.get(
        "response",
        ""
    ).strip()

    if not answer:

        return (
            "I don't have enough information in "
            "the analyzed repository."
        )

    return answer


# ============================================================
# MAIN RAG PIPELINE
# ============================================================

def ask(question):
    """
    Complete ArchLens RAG pipeline:

    Question
        ↓
    ChromaDB retrieval
        ↓
    Architecture graph
        ↓
    Relevance check
        ↓
    LLM
        ↓
    Answer + sources
    """

    question = question.strip()

    # --------------------------------------------------------
    # Basic validation
    # --------------------------------------------------------

    if len(question) < 3:

        return {
            "question": question,
            "answer": (
                "Please provide a more specific question."
            ),
            "sources": [],
            "retrieved_context": [],
            "architecture_context": ""
        }

    # --------------------------------------------------------
    # Retrieve code
    # --------------------------------------------------------

    retrieved = retrieve_code(
        question,
        TOP_K
    )

    # --------------------------------------------------------
    # Retrieve architecture relationships
    # --------------------------------------------------------

    architecture_context = (
        get_architecture_context(
            question
        )
    )

    # --------------------------------------------------------
    # Determine whether retrieved code is relevant
    # --------------------------------------------------------

    best_distance = None

    if retrieved:

        best_distance = min(
            item["distance"]
            for item in retrieved
            if item.get("distance") is not None
        )

    code_is_relevant = (
        best_distance is not None
        and best_distance <= RETRIEVAL_DISTANCE_THRESHOLD
    )

    architecture_is_relevant = bool(
        architecture_context.strip()
    )

    # --------------------------------------------------------
    # If neither code nor architecture graph has useful
    # information, refuse before calling the LLM.
    # --------------------------------------------------------

    if not code_is_relevant and not architecture_is_relevant:

        return {
            "question": question,
            "answer": (
                "I don't have enough information in "
                "the analyzed repository."
            ),
            "sources": [],
            "retrieved_context": retrieved,
            "architecture_context": ""
        }

    # --------------------------------------------------------
    # Generate answer
    # --------------------------------------------------------

    answer = generate_answer(
        question,
        retrieved if code_is_relevant else [],
        architecture_context
    )

    # --------------------------------------------------------
    # Build source list
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
    # Return complete response
    # --------------------------------------------------------

    return {
        "question": question,
        "answer": answer,
        "sources": sources,
        "retrieved_context": retrieved,
        "architecture_context": architecture_context
    }
