import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import faiss  # type: ignore
import numpy as np
from sentence_transformers import SentenceTransformer


class MemoryStore:
	"""FAISS-backed memory store with JSON metadata persistence.

	- Stores text memories with optional image path and custom metadata.
	- Uses cosine similarity over SentenceTransformer embeddings.
	- Persists FAISS index and metadata to local disk.
	"""

	def __init__(
		self,
		index_path: str,
		metadata_path: str,
		model_name: str = "all-MiniLM-L6-v2",
	):
		self.index_path = index_path
		self.metadata_path = metadata_path
		self.model_name = model_name

		# Ensure parent directories exist
		os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
		os.makedirs(os.path.dirname(self.metadata_path), exist_ok=True)

		self.model = SentenceTransformer(model_name)
		self.embedding_dim = int(self.model.get_sentence_embedding_dimension())

		# Cosine similarity via inner product on L2-normalized vectors
		base_index = faiss.IndexFlatIP(self.embedding_dim)
		self.index = faiss.IndexIDMap(base_index)

		self._metadata: Dict[str, Dict[str, Any]] = {}
		self._next_id: int = 1

		self._load()

	def _normalize(self, vectors: np.ndarray) -> np.ndarray:
		# Avoid division by zero; add small epsilon
		norms = np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-12
		return vectors / norms

	def _load(self) -> None:
		# Load metadata
		if os.path.exists(self.metadata_path):
			try:
				with open(self.metadata_path, "r", encoding="utf-8") as f:
					data = json.load(f)
					self._metadata = {str(item["id"]): item for item in data.get("items", [])}
					self._next_id = int(data.get("next_id", 1))
			except Exception:
				# Fallback to empty if corrupted
				self._metadata = {}
				self._next_id = 1

		# Load FAISS index
		if os.path.exists(self.index_path):
			try:
				self.index = faiss.read_index(self.index_path)
				# Ensure wrapped with IDMap for stable ids
				if not isinstance(self.index, faiss.IndexIDMap):
					self.index = faiss.IndexIDMap(self.index)
			except Exception:
				base_index = faiss.IndexFlatIP(self.embedding_dim)
				self.index = faiss.IndexIDMap(base_index)

	def _save(self) -> None:
		# Persist index and metadata
		faiss.write_index(self.index, self.index_path)
		payload = {
			"next_id": self._next_id,
			"items": list(self._metadata.values()),
		}
		with open(self.metadata_path, "w", encoding="utf-8") as f:
			json.dump(payload, f, ensure_ascii=False, indent=2)

	def add_memory(
		self,
		text: str,
		image_path: Optional[str] = None,
		extra: Optional[Dict[str, Any]] = None,
	) -> int:
		text = (text or "").strip()
		if not text:
			raise ValueError("Memory text must not be empty")

		vector = self.model.encode([text], convert_to_numpy=True)
		vector = self._normalize(vector.astype(np.float32))

		memory_id = int(self._next_id)
		self._next_id += 1

		self.index.add_with_ids(vector, np.array([memory_id], dtype=np.int64))

		record: Dict[str, Any] = {
			"id": memory_id,
			"text": text,
			"image_path": image_path,
			"created_at": int(time.time()),
		}
		if extra:
			record.update(extra)

		self._metadata[str(memory_id)] = record
		self._save()
		return memory_id

	def search(
		self,
		query: str,
		k: int = 5,
	) -> List[Tuple[Dict[str, Any], float]]:
		query = (query or "").strip()
		if not query or self.index.ntotal == 0:
			return []

		vector = self.model.encode([query], convert_to_numpy=True)
		vector = self._normalize(vector.astype(np.float32))

		scores, ids = self.index.search(vector, k)
		scores = scores.flatten().tolist()
		ids = ids.flatten().tolist()

		results: List[Tuple[Dict[str, Any], float]] = []
		for id_val, score in zip(ids, scores):
			if id_val == -1:
				continue
			meta = self._metadata.get(str(int(id_val)))
			if not meta:
				continue
			results.append((meta, float(score)))

		# Sort by score desc (redundant but safe)
		results.sort(key=lambda x: x[1], reverse=True)
		return results

	def all_memories(self) -> List[Dict[str, Any]]:
		return sorted(self._metadata.values(), key=lambda r: r.get("created_at", 0), reverse=True)
