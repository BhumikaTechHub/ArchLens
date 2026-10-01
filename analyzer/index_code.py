import json
import requests
import chromadb


CHUNKS_FILE = "code_chunks.json"
CHROMA_FOLDER = "vector_db"
COLLECTION_NAME = "archlens_code"

OLLAMA_URL = "http://localhost:11434/api/embed"
EMBEDDING_MODEL = "nomic-embed-text"


def get_embeddings(texts):

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": EMBEDDING_MODEL,
            "input": texts
        },
        timeout=120
    )

    response.raise_for_status()

    data = response.json()

    if "embeddings" not in data:
        raise RuntimeError(
            f"Embedding response missing embeddings: {data}"
        )

    return data["embeddings"]


def main():

    with open(
        CHUNKS_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        chunks = json.load(file)

    if not chunks:
        print("No chunks found.")
        return

    client = chromadb.PersistentClient(
        path=CHROMA_FOLDER
    )

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME
    )

    # Rebuild this project collection cleanly
    existing = collection.get()

    if existing["ids"]:
        collection.delete(ids=existing["ids"])

    batch_size = 10

    for i in range(
        0,
        len(chunks),
        batch_size
    ):

        batch = chunks[i:i + batch_size]

        texts = [
            item["text"]
            for item in batch
        ]

        embeddings = get_embeddings(texts)

        collection.add(
            ids=[
                item["id"]
                for item in batch
            ],
            documents=texts,
            embeddings=embeddings,
            metadatas=[
                item["metadata"]
                for item in batch
            ]
        )

        print(
            f"Indexed {min(i + batch_size, len(chunks))}"
            f"/{len(chunks)} chunks"
        )

    print()
    print("Indexing completed.")
    print("Collection:", COLLECTION_NAME)
    print("Total chunks:", collection.count())


if __name__ == "__main__":
    main()
