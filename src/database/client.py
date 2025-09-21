import chromadb
from chromadb.config import Settings
from typing import List, Dict, Optional, Any
import uuid
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


class ChromaDBClient:
    def __init__(self, persist_directory: str = "./chroma_db"):
        """
        Initialize ChromaDB client with persistent storage
        """
        self.persist_directory = persist_directory
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Create collections for different data types
        self.news_collection = self.client.get_or_create_collection(
            name="news_articles",
            metadata={"description": "French news articles with embeddings"}
        )
        
        self.conversations_collection = self.client.get_or_create_collection(
            name="conversations",
            metadata={"description": "Chat conversations with metadata"}
        )

    async def connect(self):
        """Connect to database - no-op for ChromaDB but kept for compatibility"""
        pass

    async def disconnect(self):
        """Disconnect from database - no-op for ChromaDB but kept for compatibility"""
        pass

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

    # News Article Methods
    async def create_news_article(
        self,
        title: str,
        content: str,
        url: str,
        published_at: datetime,
        title_fr: Optional[str] = None,
        content_fr: Optional[str] = None,
        embedding: Optional[List[float]] = None
    ) -> Dict[str, Any]:
        """
        Create a news article in ChromaDB
        """
        article_id = str(uuid.uuid4())
        
        # Prepare document content (French version for better search in French)
        document_text = title_fr or title
        if content_fr:
            document_text += " " + content_fr
        elif content:
            document_text += " " + content

        # Prepare metadata
        metadata = {
            "title": title,
            "title_fr": title_fr or "",
            "content": content[:1000],  # Truncate for metadata storage
            "content_fr": (content_fr or "")[:1000],
            "url": url,
            "published_at": published_at.isoformat(),
            "created_at": datetime.now().isoformat()
        }

        # Add to collection
        self.news_collection.add(
            documents=[document_text],
            metadatas=[metadata],
            ids=[article_id],
            embeddings=[embedding] if embedding else None
        )

        return {
            "id": article_id,
            "title": title,
            "titleFr": title_fr,
            "content": content,
            "contentFr": content_fr,
            "url": url,
            "publishedAt": published_at,
            "embedding": embedding
        }

    async def get_news_article_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Find a news article by URL
        """
        try:
            results = self.news_collection.get(
                where={"url": url},
                include=["documents", "metadatas", "embeddings"]
            )
            
            if not results["ids"]:
                return None
                
            # Return first match
            idx = 0
            metadata = results["metadatas"][idx]
            
            return {
                "id": results["ids"][idx],
                "title": metadata["title"],
                "titleFr": metadata["title_fr"],
                "content": metadata["content"],
                "contentFr": metadata["content_fr"],
                "url": metadata["url"],
                "publishedAt": datetime.fromisoformat(metadata["published_at"]),
                "embedding": results["embeddings"][idx] if results["embeddings"] else None
            }
        except Exception:
            return None

    async def get_recent_news_articles(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get recent news articles (ChromaDB doesn't have built-in ordering, so we'll get all and sort)
        """
        try:
            results = self.news_collection.get(
                include=["documents", "metadatas", "embeddings"],
                limit=limit * 2  # Get more to sort
            )

            
            if not results["ids"]:
                return []

            articles = []
            for i, article_id in enumerate(results["ids"]):
                metadata = results["metadatas"][i]
                articles.append({
                    "id": article_id,
                    "title": metadata["title"],
                    "titleFr": metadata["title_fr"],
                    "content": metadata["content"],
                    "contentFr": metadata["content_fr"],
                    "url": metadata["url"],
                    "publishedAt": datetime.fromisoformat(metadata["published_at"]),
                    "embedding": results["embeddings"][i]
                })

            # Sort by published date (most recent first)

            articles.sort(key=lambda x: x["publishedAt"], reverse=True)

            return articles[:limit]
        except Exception as e :
            print(f"Error in get_recent_news_articles: {e}")
            raise e
            

    async def search_articles_by_similarity(
        self, 
        query_text: str = None,
        query_embedding: List[float] = None, 
        limit: int = 5,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search articles by semantic similarity using ChromaDB's built-in vector search
        """
        try:
            if query_embedding:
                # Use provided embedding
                results = self.news_collection.query(
                    query_embeddings=[query_embedding],
                    n_results=limit,
                    include=["documents", "metadatas", "distances", "embeddings"]
                )
            elif query_text:
                # Let ChromaDB handle embedding
                results = self.news_collection.query(
                    query_texts=[query_text],
                    n_results=limit,
                    include=["documents", "metadatas", "distances", "embeddings"]
                )
            else:
                return []

            if not results["ids"]:
                return []

            articles = []
            for i, article_id in enumerate(results["ids"][0]):  # Query returns nested lists
                metadata = results["metadatas"][0][i]
                distance = results["distances"][0][i]
                similarity = 1 - distance  # Convert distance to similarity
                
                if similarity >= similarity_threshold:
                    articles.append({
                        "id": article_id,
                        "title": metadata["title"],
                        "titleFr": metadata["title_fr"],
                        "content": metadata["content"],
                        "contentFr": metadata["content_fr"],
                        "url": metadata["url"],
                        "publishedAt": datetime.fromisoformat(metadata["published_at"]),
                        "similarity": similarity,
                        "embedding": results["embeddings"][0][i] if results["embeddings"] else None
                    })

            return articles
        except Exception as e:
            print(f"Error in similarity search: {e}")
            return []

    def search_articles_by_similarity_sync(
        self, 
        query_text: str = None,
        query_embedding: List[float] = None, 
        limit: int = 5,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Synchronous version of search articles by semantic similarity using ChromaDB's built-in vector search
        """
        try:

            if query_embedding:
                # Use provided embedding
                results = self.news_collection.query(
                    query_embeddings=[query_embedding],
                    n_results=limit,
                    include=["documents", "metadatas", "distances", "embeddings"]
                )
            elif query_text:
                # Let ChromaDB handle embedding
                results = self.news_collection.query(
                    query_texts=[query_text],
                    n_results=limit,
                    include=["documents", "metadatas", "distances", "embeddings"]
                )
            else:
                return []

            if not results["ids"]:
                return []


            return results
        except Exception as e:
            print(f"Error in sync similarity search: {e}")
            return []

    # Conversation Methods (simplified - storing as documents)
    async def create_conversation(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new conversation
        """
        conversation_id = str(uuid.uuid4())
        
        metadata = {
            "user_id": user_id or "",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        # Store conversation metadata
        self.conversations_collection.add(
            documents=[f"Conversation {conversation_id}"],
            metadatas=[metadata],
            ids=[conversation_id]
        )

        return {
            "id": conversation_id,
            "userId": user_id,
            "messages": []
        }

    async def add_message_to_conversation(
        self,
        conversation_id: str,
        role: str,
        content: str
    ) -> Dict[str, Any]:
        """
        Add a message to a conversation (stored as separate document)
        """
        message_id = str(uuid.uuid4())
        
        metadata = {
            "conversation_id": conversation_id,
            "role": role.upper(),
            "created_at": datetime.now().isoformat()
        }

        # Store message
        self.conversations_collection.add(
            documents=[content],
            metadatas=[metadata],
            ids=[message_id]
        )

        return {
            "id": message_id,
            "conversationId": conversation_id,
            "role": role.upper(),
            "content": content,
            "createdAt": datetime.now()
        }

    async def get_conversation_with_messages(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get conversation with all its messages
        """
        try:
            # First, check if the conversation exists by trying to get conversation metadata
            try:
                conversation_results = self.conversations_collection.get(
                    ids=[conversation_id],
                    include=["metadatas"]
                )
                if not conversation_results["ids"]:
                    return None
            except:
                return None

            # Get all messages for this conversation
            results = self.conversations_collection.get(
                where={"conversation_id": conversation_id},
                include=["documents", "metadatas"]
            )
            
            messages = []
            if results["ids"]:
                for i, message_id in enumerate(results["ids"]):
                    metadata = results["metadatas"][i]
                    if "role" in metadata:  # This is a message, not conversation metadata
                        messages.append({
                            "id": message_id,
                            "role": metadata["role"],
                            "content": results["documents"][i],
                            "createdAt": datetime.fromisoformat(metadata["created_at"])
                        })

            # Sort messages by creation time
            messages.sort(key=lambda x: x["createdAt"])

            return {
                "id": conversation_id,
                "messages": messages
            }
        except Exception as e:
            print(f"Error getting conversation: {e}")
            return None

    # Legacy methods for compatibility
    async def update_article_french_translation(
        self,
        article_id: str,
        title_fr: str,
        content_fr: str
    ):
        """Update French translation - would need to re-add to ChromaDB"""
        # ChromaDB doesn't support updates, would need to delete and re-add
        pass

    async def update_article_embedding(
        self,
        article_id: str,
        embedding: List[float]
    ):
        """Update embedding - would need to re-add to ChromaDB"""
        # ChromaDB doesn't support updates, would need to delete and re-add
        pass


# Global database client instance
db_client = ChromaDBClient()