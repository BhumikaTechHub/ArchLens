import sys
import requests
import chromadb


CHROMA_FOLDER = "vector_db"
COLLECTION_NAME = "archlens_code"

OLLAMA_URL = "http://localhost:11434/api/embed"
EMBEDDING_MODEL = "nomic-embed-text"


def get_query_embedding(question):

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": EMBEDDING_MODEL,
            "input": [question]
        },
        timeout=120
    )

    response.raise_for_status()

    data = response.json()

    return data["embeddings"][0]


def search(question):

    client = chromadb.PersistentClient(
        path=CHROMA_FOLDER
    )

    collection = client.get_collection(
        name=COLLECTION_NAME
    )

    embedding = get_query_embedding(question)

    results = collection.query(
        query_embeddings=[embedding],
        n_results=3
    )

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    print()
    print("ARCHLENS SEMANTIC SEARCH")
    print("=" * 50)

    for i, document in enumerate(documents):

        print()
        print(f"Result {i + 1}")
        print("-" * 50)

        print(
            "File:",
            metadatas[i].get("file")
        )

        print(
            "Type:",
            metadatas[i].get("type")
        )

        print(
            "Name:",
            metadatas[i].get("name")
        )

        print(
            "Distance:",
            distances[i]
        )

        print()
        print(document[:1000])


def main():

    if len(sys.argv) < 2:

        print(
            'Usage: python search_code.py "your question"'
        )

        sys.exit(1)

    question = " ".join(sys.argv[1:])

    search(question)


if __name__ == "__main__":
    main()
