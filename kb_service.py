"""
ChromaDB 双知识库管理服务
Python 3.10 + ChromaDB 1.5.9
"""
import uuid
import chromadb
from chromadb.utils import embedding_functions as ef
from config import CHROMA_DIR, HISTORY_KB, MATERIAL_KB, TOP_K


class KBManager:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=CHROMA_DIR)
        # ChromaDB 内置 embedding (all-MiniLM-L6-v2, 384维, 轻量)
        # self.embed_fn = ef.DefaultEmbeddingFunction()
        
        # 使用 ChromaDB 内置的 Ollama embedding function
        self.embed_fn = ef.OllamaEmbeddingFunction(
            url="http://localhost:11434/api/embeddings",  # Ollama 默认地址
            model_name="bge-m3:latest"  # 或其他支持 embedding 的模型
        )

        self.history = self.client.get_or_create_collection(
            name=HISTORY_KB, embedding_function=self.embed_fn,
            metadata={"desc": "历史问题知识库"}
        )
        self.material = self.client.get_or_create_collection(
            name=MATERIAL_KB, embedding_function=self.embed_fn,
            metadata={"desc": "材料知识库"}
        )

    def _coll(self, kb_name):
        return self.history if kb_name == HISTORY_KB else self.material

    def add(self, kb_name, text, meta, doc_id=None):
        coll = self._coll(kb_name)
        doc_id = doc_id or str(uuid.uuid4())
        coll.add(ids=[doc_id], documents=[text], metadatas=[meta])
        return doc_id

    def update(self, kb_name, doc_id, text=None, meta=None):
        coll = self._coll(kb_name)
        kw = {"ids": [doc_id]}
        if text: kw["documents"] = [text]
        if meta: kw["metadatas"] = [meta]
        coll.update(**kw)

    def delete(self, kb_name, doc_id):
        self._coll(kb_name).delete(ids=[doc_id])

    def list_entries(self, kb_name, offset=0, limit=50):
        coll = self._coll(kb_name)
        data = coll.get(offset=offset, limit=limit, include=["documents", "metadatas"])
        results = []
        if data["ids"]:
            for i in range(len(data["ids"])):
                results.append({
                    "id": data["ids"][i],
                    "document": data["documents"][i] if data["documents"] else "",
                    "metadata": data["metadatas"][i] if data["metadatas"] else {}
                })
        return results

    def count(self, kb_name):
        return self._coll(kb_name).count()

    def search(self, kb_name, query, top_k=TOP_K):
        """语义检索"""
        coll = self._coll(kb_name)
        if coll.count() == 0:
            return []
        results = coll.query(
            query_texts=[query], n_results=min(top_k, coll.count()),
            include=["documents", "metadatas", "distances"]
        )
        entries = []
        if results["ids"] and results["ids"][0]:
            for i in range(len(results["ids"][0])):
                dist = results["distances"][0][i]
                sim = round(1.0 / (1.0 + dist), 4)
                entries.append({
                    "id": results["ids"][0][i],
                    "document": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "similarity": sim
                })
        return entries


kb = KBManager()
