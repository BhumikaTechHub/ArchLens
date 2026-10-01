import requests
import chromadb


CHROMA_FOLDER = "vector_db"
COLLECTION_NAME = "archlens_code"

OLLAMA_URL = "http://localhost:11434"

EMBEDDING_MODEL = "nomic-embed-text"
LLM_MODEL = "smollm2:360m"

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

    return data["embeddings"][0]


def retrieve_code(question, top_k=3):

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

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

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


def generate_answer(question, retrieved):

    if not retrieved:
        return "I could not find relevant information in the repository."

    context_parts = []

    for item in retrieved:

        context_parts.append(
            f"""
FILE: {item['file']}
TYPE: {item['type']}
NAME: {item['name']}

CODE:
{item['document']}
"""
        )

    context = "\n".join(context_parts)

    prompt = f"""
You are ArchLens, an AI software architecture assistant.

Answer the user's question using ONLY the repository context provided below.

Rules:
1. Do not invent information.
2. Do not use outside knowledge.
3. If the answer is present in the context, explain it clearly.
4. Mention relevant files, classes, or functions when useful.
5. If the context does not contain enough information, say:
"I don't have enough information in the analyzed repository."
6. Keep the answer concise.

REPOSITORY CONTEXT:
{context}

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
                "num_predict": 150
            }
        },
        timeout=180
    )

    response.raise_for_status()

    data = response.json()

    return data["response"].strip()


def ask(question):
    retrieved = retrieve_code(question)

    if not retrieved:
        return {
            "question": question,
            "answer": "I don't have enough information in the analyzed repository.",
            "sources": [],
            "retrieved_context": []
        }

    best_distance = retrieved[0]["distance"]

    if best_distance > 0.8:
        return {
            "question": question,
            "answer": "I don't have enough information in the analyzed repository.",
            "sources": [],
            "retrieved_context": retrieved
        }

    answer = generate_answer(question, retrieved)

    sources = []
    for item in retrieved:
        file_name = item["file"]
        if file_name not in sources:
            sources.append(file_name)

    return {
        "question": question,
        "answer": answer,
        "sources": sources,
        "retrieved_context": retrieved
    }
