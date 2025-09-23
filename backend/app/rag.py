# app/rag.py

import chromadb  # Vector database client
from app.cli import COLLECTION_NAME, CHROMA_HOST  # Shared config (from ingestion CLI)

# -----------------------------------------------------------------------------
# QUERY RAG FUNCTION
# -----------------------------------------------------------------------------

def query_rag(query_text: str, top_k: int = 5):
    """
    Query ChildSafe ChromaDB collection for relevant documents.
    - Uses Chroma’s internal embeddings (no external LLM).
    - Returns top_k most relevant chunks with metadata + similarity scores.

    Args:
        query_text (str): Natural language query
        top_k (int): Number of documents to retrieve (default=5)

    Returns:
        dict: {
            "query": str,
            "results": [list of retrieved texts],
            "metadatas": [list of metadata per chunk],
            "scores": [float similarity scores],
            "ids": [list of chunk IDs],
            "total_docs": int total docs in collection,
            "error": str (if any)
        }
    """
    try:
        # Connect to ChromaDB server
        client = chromadb.HttpClient(host=CHROMA_HOST)

        # Access ChildSafe reports collection
        collection = client.get_collection(COLLECTION_NAME)

        # Safety check: collection might be empty
        count = collection.count()
        if count == 0:
            return {
                "query": query_text,
                "results": [],
                "metadatas": [],
                "scores": [],
                "ids": [],
                "error": "No documents in collection",
            }

        # Query ChromaDB using internal embeddings
        results = collection.query(query_texts=[query_text], n_results=top_k)

        # Extract structured results safely
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        ids = results.get("ids", [[]])[0]

        # Convert distances → similarity scores (closer = higher score)
        scores = [1.0 - min(float(d), 1.0) for d in distances] if distances else []

        # Return structured response
        return {
            "query": query_text,
            "results": documents,
            "metadatas": metadatas,
            "scores": scores,
            "ids": ids,
            "total_docs": count,
        }

    except Exception as e:
        # Gracefully handle connection/query errors
        return {
            "query": query_text,
            "results": [],
            "metadatas": [],
            "scores": [],
            "ids": [],
            "error": str(e),
        }
