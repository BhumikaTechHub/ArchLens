import sys
import requests
import chromadb


# ============================================================
# CONFIGURATION
# ============================================================

OLLAMA_URL = "http://localhost:11434"
EMBEDDING_MODEL = "nomic-embed-text"
COLLECTION_NAME = "archlens_code"


# ============================================================
# GET QUERY EMBEDDING
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
            f"Ollama response does not contain embeddings: {data}"
        )

    return data["embeddings"][0]


# ============================================================
# SEARCH REPOSITORY
# ============================================================

def search_repository(repo_name, query, top_k=3):

    vector_db_path = f"vector_db/{repo_name}"

    # --------------------------------------------------------
    # CONNECT TO REPOSITORY-SPECIFIC CHROMA DB
    # --------------------------------------------------------

    client = chromadb.PersistentClient(
        path=vector_db_path
    )

    try:
        collection = client.get_collection(
            name=COLLECTION_NAME
        )
    except Exception:
        print(
            f"ERROR: Repository index not found for '{repo_name}'."
        )
        print(
            f"Expected: {vector_db_path}"
        )
        print()
        print(
            "Run:"
        )
        print(
            f"python3 analyzer/index_code.py {repo_name}"
        )
        return

    # --------------------------------------------------------
    # QUERY EMBEDDING
    # --------------------------------------------------------

    query_embedding = get_embedding(query)

    # --------------------------------------------------------
    # CHROMA SEARCH
    # --------------------------------------------------------

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    # --------------------------------------------------------
    # DISPLAY RESULTS
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("ARCHLENS CODE SEARCH")
    print("=" * 70)

    print(f"Repository : {repo_name}")
    print(f"Query      : {query}")
    print(f"Results    : {len(documents)}")

    print()

    if not documents:

        print("No matching code found.")

        return

    for i, (document, metadata, distance) in enumerate(
        zip(
            documents,
            metadatas,
            distances
        ),
        start=1
    ):

        print("-" * 70)

        print(
            f"RESULT {i}"
        )

        print(
            f"Repository : "
            f"{metadata.get('repository', repo_name)}"
        )

        print(
            f"File       : "
            f"{metadata.get('file', 'unknown')}"
        )

        print(
            f"Type       : "
            f"{metadata.get('type', 'unknown')}"
        )

        print(
            f"Name       : "
            f"{metadata.get('name', 'unknown')}"
        )

        print(
            f"Line       : "
            f"{metadata.get('line', 'unknown')}"
        )

        print(
            f"Distance   : "
            f"{distance:.4f}"
        )

        print()

        print("CODE:")

        print(document)

        print()

    print("=" * 70)


# ============================================================
# MAIN
# ============================================================

def main():

    if len(sys.argv) < 3:

        print(
            "Usage:"
        )

        print(
            "python3 analyzer/search_code.py "
            "<repository_name> \"<query>\""
        )

        print()

        print("Examples:")

        print(
            'python3 analyzer/search_code.py '
            'ecommerce "payment processing"'
        )

        print(
            'python3 analyzer/search_code.py '
            'auth_system "user authentication"'
        )

        print(
            'python3 analyzer/search_code.py '
            'task_manager "creating a task"'
        )

        sys.exit(1)

    repo_name = sys.argv[1]

    query = " ".join(
        sys.argv[2:]
    )

    search_repository(
        repo_name,
        query
    )


if __name__ == "__main__":
    main()
