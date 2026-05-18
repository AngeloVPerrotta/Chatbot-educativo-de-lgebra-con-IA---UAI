import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_collection = None


def _get_collection():
    global _collection
    if _collection is not None:
        return _collection

    import chromadb
    from chromadb.utils import embedding_functions

    persist_dir = '/data/chromadb' if Path('/data').exists() else './chromadb_data'
    client = chromadb.PersistentClient(path=persist_dir)

    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name='paraphrase-multilingual-MiniLM-L12-v2'
    )

    _collection = client.get_or_create_collection(
        name='algebra_chunks',
        embedding_function=ef
    )

    # Si la colección está vacía, indexar los chunks
    if _collection.count() == 0:
        logger.info('Indexando chunks en ChromaDB...')
        chunks_path = Path(__file__).parent.parent / 'knowledge' / 'algebra_chunks.json'
        with open(chunks_path, 'r', encoding='utf-8') as f:
            chunks = json.load(f)

        ids = [c['id'] for c in chunks]
        documents = [c['contenido'] for c in chunks]
        metadatas = [{'topic': c['tema']} for c in chunks]

        _collection.add(ids=ids, documents=documents, metadatas=metadatas)
        logger.info(f'Indexados {len(chunks)} chunks')

    return _collection


def retrieve_context(query: str, top_k: int = 2) -> tuple:
    try:
        collection = _get_collection()
        results = collection.query(query_texts=[query], n_results=top_k)

        if not results['documents'][0]:
            return ('', 0)

        context_parts = []
        total_chars = 0
        for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
            if total_chars + len(doc) > 400:
                break
            context_parts.append(f"[{meta['topic']}] {doc}")
            total_chars += len(doc)

        context = '\n'.join(context_parts)

        # Score: ChromaDB devuelve distances (menor = más similar)
        # Convertir a score positivo para compatibilidad
        distances = results['distances'][0]
        max_score = max(0, 10 - min(distances) * 5) if distances else 0

        return (context, max_score)
    except Exception as e:
        logger.error(f'Error en RAG: {e}')
        return ('', 0)
