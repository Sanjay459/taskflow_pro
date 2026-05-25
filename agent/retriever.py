"""
agent/retriever.py
------------------
Builds and returns a LangChain retriever backed by Pinecone (primary).
ChromaDB path is kept as a commented-out fallback.

Pinecone index is created automatically on first run if it does not exist.
Set force_rebuild=True to re-upsert all documents (e.g. after doc updates).
"""

import os
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Path helpers — resolve relative paths from .env against project root
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _abs(env_key: str, default: str) -> str:
    p = os.environ.get(env_key, default)
    return p if os.path.isabs(p) else os.path.join(_PROJECT_ROOT, p)

DOCS_PATH        = _abs("DOCS_PATH", "data/product_docs")
VECTOR_STORE_PATH = _abs("VECTOR_STORE_PATH", "data/vectorstore")  # ChromaDB fallback

# ---------------------------------------------------------------------------
# Pinecone config
# ---------------------------------------------------------------------------
PINECONE_API_KEY    = os.environ.get("PINECONE_API_KEY", "")
PINECONE_INDEX_NAME = os.environ.get("PINECONE_INDEX_NAME", "taskflow-kb")
PINECONE_ENVIRONMENT = os.environ.get("PINECONE_ENVIRONMENT", "us-east-1")
EMBEDDING_MODEL     = "text-embedding-3-small"
EMBEDDING_DIM       = 1536   # dimensions for text-embedding-3-small


def _get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(model=EMBEDDING_MODEL)


def _ensure_index(pc: Pinecone) -> None:
    """Create the Pinecone serverless index if it does not already exist."""
    existing = [idx.name for idx in pc.list_indexes()]
    if PINECONE_INDEX_NAME not in existing:
        print(f"Creating Pinecone index '{PINECONE_INDEX_NAME}' ...")
        pc.create_index(
            name=PINECONE_INDEX_NAME,
            dimension=EMBEDDING_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region=PINECONE_ENVIRONMENT),
        )
        print("Index created.")
    else:
        print(f"Pinecone index '{PINECONE_INDEX_NAME}' already exists.")


def _load_and_chunk() -> list:
    """Load .txt product docs and split into chunks."""
    print(f"Loading documents from '{DOCS_PATH}' ...")
    loader = DirectoryLoader(DOCS_PATH, glob="*.txt", loader_cls=TextLoader, show_progress=True)
    docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(docs)
    print(f"Loaded {len(docs)} documents → {len(chunks)} chunks.")
    return chunks


def build_vectorstore(force_rebuild: bool = False) -> PineconeVectorStore:
    """
    Connect to (or build) the Pinecone vector store.

    - If the index exists and has vectors, skip upserting unless force_rebuild=True.
    - If the index is empty or force_rebuild=True, load docs → chunk → embed → upsert.

    Returns a PineconeVectorStore instance ready for similarity search.
    """
    if not PINECONE_API_KEY:
        raise EnvironmentError(
            "PINECONE_API_KEY is not set. Add it to your .env file."
        )

    embeddings = _get_embeddings()
    pc = Pinecone(api_key=PINECONE_API_KEY)
    _ensure_index(pc)

    index = pc.Index(PINECONE_INDEX_NAME)
    stats = index.describe_index_stats()
    vector_count = stats.get("total_vector_count", 0)

    if vector_count > 0 and not force_rebuild:
        print(f"Index '{PINECONE_INDEX_NAME}' has {vector_count} vectors — skipping upsert.")
        return PineconeVectorStore(index=index, embedding=embeddings)

    if force_rebuild and vector_count > 0:
        print(f"force_rebuild=True — deleting {vector_count} existing vectors ...")
        index.delete(delete_all=True)

    chunks = _load_and_chunk()
    print("Upserting chunks to Pinecone ...")
    vectorstore = PineconeVectorStore.from_documents(
        chunks,
        embeddings,
        index_name=PINECONE_INDEX_NAME,
    )
    print(f"Upserted {len(chunks)} chunks to index '{PINECONE_INDEX_NAME}'.")
    return vectorstore


def get_retriever(k: int = 4):
    """Return a retriever that fetches the top-k most relevant chunks."""
    vs = build_vectorstore()
    return vs.as_retriever(search_type="similarity", search_kwargs={"k": k})


# ---------------------------------------------------------------------------
# ChromaDB fallback (commented out — uncomment if Pinecone is unavailable)
# ---------------------------------------------------------------------------
# from langchain_community.vectorstores import Chroma
#
# def build_vectorstore_chroma(force_rebuild: bool = False) -> Chroma:
#     embeddings = _get_embeddings()
#     if os.path.exists(VECTOR_STORE_PATH) and not force_rebuild:
#         return Chroma(persist_directory=VECTOR_STORE_PATH, embedding_function=embeddings)
#     chunks = _load_and_chunk()
#     return Chroma.from_documents(chunks, embeddings, persist_directory=VECTOR_STORE_PATH)

