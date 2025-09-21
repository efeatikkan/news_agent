from sentence_transformers import SentenceTransformer
from typing import List, Optional
import numpy as np


class EmbeddingService:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()

    def create_embedding(self, text: str) -> List[float]:
        embedding = self.model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def create_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def compute_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        arr1 = np.array(embedding1)
        arr2 = np.array(embedding2)
        return float(np.dot(arr1, arr2))

    def create_article_embedding(self, title: str, content: str) -> List[float]:
        # Combine title and content with title weighted more heavily
        combined_text = f"{title} {title} {content}"
        return self.create_embedding(combined_text)

    def find_most_similar(
        self, 
        query_embedding: List[float], 
        candidate_embeddings: List[List[float]], 
        threshold: float = 0.7
    ) -> List[tuple]:
        """
        Find most similar embeddings to query
        Returns list of (index, similarity_score) tuples
        """
        similarities = []
        query_arr = np.array(query_embedding)
        
        for i, candidate in enumerate(candidate_embeddings):
            candidate_arr = np.array(candidate)
            similarity = float(np.dot(query_arr, candidate_arr))
            
            if similarity >= threshold:
                similarities.append((i, similarity))
        
        # Sort by similarity score descending
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities


# Global embedding service instance
embedding_service = EmbeddingService()