import json
import os
import sys
import requests
import chromadb


# ============================================================
# CONFIGURATION
# ============================================================

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://localhost:11434"
)
EMBEDDING_MODEL = "nomic-embed-text"
COLLECTION_NAME = "archlens_code"
BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

# ============================================================
# GET EMBEDDING FROM OLLAMA
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
# LOAD CODE CHUNKS
# ============================================================

def get_repository_paths(repo_name):

    imported_dir = os.path.join(
        BASE_DIR,
        "imported_repositories",
        "generated",
        repo_name
    )

    imported_chunks = os.path.join(
        imported_dir,
        "code_chunks.json"
    )

    if os.path.isfile(imported_chunks):
        return (
            imported_chunks,
            os.path.join(imported_dir, "vector_db")
        )

    sample_chunks = os.path.join(
        BASE_DIR,
        f"code_chunks_{repo_name}.json"
    )

    if os.path.isfile(sample_chunks):
        return (
            sample_chunks,
            os.path.join(BASE_DIR, "vector_db", repo_name)
        )

    raise FileNotFoundError(
        f"No generated chunks found for repository: {repo_name}"
    )

def load_chunks(repo_name):

    chunks_file, _ = get_repository_paths(repo_name)

    with open(
        chunks_file,
        "r",
        encoding="utf-8"
    ) as f:

        chunks = json.load(f)

    return chunks

# ============================================================
# CREATE / OPEN REPOSITORY-SPECIFIC CHROMA DATABASE
# ============================================================

def get_collection(repo_name):

    _, vector_db_path = get_repository_paths(repo_name)

    os.makedirs(
        vector_db_path,
        exist_ok=True
    )

    client = chromadb.PersistentClient(
        path=vector_db_path
    )

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={
            "repository": repo_name,
            "description": "ArchLens repository-specific code index"
        }
    )

    return collection

# ============================================================
# INDEX REPOSITORY
# ============================================================

def index_repository(repo_name):

    print("=" * 60)
    print("ARCHLENS CODE INDEXING")
    print("=" * 60)

    print(f"Repository: {repo_name}")

    # --------------------------------------------------------
    # LOAD CHUNKS
    # --------------------------------------------------------

    chunks = load_chunks(repo_name)

    print(f"Chunks loaded: {len(chunks)}")

    if not chunks:
        print("No chunks found.")
        return

    # --------------------------------------------------------
    # CHROMA COLLECTION
    # --------------------------------------------------------

    collection = get_collection(repo_name)

    print(
        f"Collection: {COLLECTION_NAME}"
    )

    print(
        f"Existing chunks: {collection.count()}"
    )

    # --------------------------------------------------------
    # CLEAR OLD INDEX
    # --------------------------------------------------------

    existing = collection.get()

    if existing["ids"]:

        collection.delete(
            ids=existing["ids"]
        )

        print(
            f"Removed old chunks: {len(existing['ids'])}"
        )

    # --------------------------------------------------------
    # EMBEDDING + INDEXING
    # --------------------------------------------------------

    batch_size = 10

    total = len(chunks)

    for start in range(
        0,
        total,
        batch_size
    ):

        batch = chunks[
            start:start + batch_size
        ]

        documents = []
        embeddings = []
        metadatas = []
        ids = []

        for index, chunk in enumerate(batch):

            document = chunk["document"]

            metadata = chunk["metadata"]

            # ------------------------------------------------
            # ENSURE REPOSITORY METADATA EXISTS
            # ------------------------------------------------

            metadata["repository"] = repo_name
            metadata = {
                key: value
                for key, value in metadata.items()
                if value is not None
            }
            # ------------------------------------------------
            # CREATE UNIQUE ID
            # ------------------------------------------------

            chunk_id = (
                f"{repo_name}_"
                f"{start + index}"
            )

            # ------------------------------------------------
            # CREATE EMBEDDING
            # ------------------------------------------------

            print(
                f"Embedding "
                f"{start + index + 1}/{total}: "
                f"{metadata.get('file')} "
                f"({metadata.get('type')})"
            )

            embedding = get_embedding(
                document
            )

            documents.append(
                document
            )

            embeddings.append(
                embedding
            )

            metadatas.append(
                metadata
            )

            ids.append(
                chunk_id
            )

        # ----------------------------------------------------
        # ADD BATCH TO CHROMA
        # ----------------------------------------------------

        collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )

        print(
            f"Indexed {min(start + batch_size, total)}/{total}"
        )

    # --------------------------------------------------------
    # FINAL RESULT
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("INDEXING COMPLETED")
    print("=" * 60)

    print(
        f"Repository: {repo_name}"
    )

    print(
        f"Total chunks indexed: {collection.count()}"
    )

    _, vector_db_path = get_repository_paths(repo_name)
    print(
        f"Vector DB: {vector_db_path}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if len(sys.argv) != 2:

        print(
            "Usage:"
        )

        print(
            "python3 analyzer/index_code.py <repository_name>"
        )

        print()
        print(
            "Examples:"
        )

        print(
            "python3 analyzer/index_code.py ecommerce"
        )

        print(
            "python3 analyzer/index_code.py auth_system"
        )

        print(
            "python3 analyzer/index_code.py task_manager"
        )

        sys.exit(1)

    repo_name = sys.argv[1]

    index_repository(
        repo_name
    )


if __name__ == "__main__":
    main()
