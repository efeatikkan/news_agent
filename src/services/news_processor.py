from typing import List
import asyncio
import logging
import json
from datetime import datetime, timedelta

from src.services.news_fetcher import BBCNewsFetcher, NewsArticle
from src.services.translator import FrenchB1Translator
from src.services.embeddings import embedding_service
from src.database.client import db_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DailyNewsProcessor:
    def __init__(self):
        self.news_fetcher = BBCNewsFetcher()
        self.translator = FrenchB1Translator()

    async def process_daily_news(self, limit: int = 10) -> List[dict]:
        """
        Fetch, translate, and store daily news articles
        """
        logger.info(f"Starting daily news processing for {limit} articles")
        
        try:
            # Fetch latest news
            logger.info("Fetching latest news from BBC...")
            articles = await self.news_fetcher.fetch_latest_news(limit)
            logger.info(f"Fetched {len(articles)} articles")
            
            processed_articles = []
            
            async with db_client:
                for article in articles:
                    try:
                        # Check if article already exists
                        existing = await db_client.get_news_article_by_url(article.url)
                        if existing:
                            logger.info(f"Article already exists: {article.title[:50]}...")
                            continue
                        
                        # Process the article
                        processed_article = await self._process_single_article(article)
                        if processed_article:
                            processed_articles.append(processed_article)
                            logger.info(f"Processed: {article.title[:50]}...")
                        
                    except Exception as e:
                        logger.error(f"Error processing article {article.title[:50]}: {e}")
                        continue
            
            logger.info(f"Successfully processed {len(processed_articles)} new articles")
            return processed_articles
            
        except Exception as e:
            logger.error(f"Error in daily news processing: {e}")
            raise
        finally:
            await self.news_fetcher.close()

    async def _process_single_article(self, article: NewsArticle) -> dict:
        """
        Process a single article: translate, create embeddings, and store
        """
        try:
            # Translate to French B1 level
            title_fr = await self.translator.translate_title(article.title)
            content_fr = await self.translator.translate_content(article.content)
            
            # Create embeddings for the French version (better for French conversations)
            combined_text = f"{title_fr} {content_fr}"
            embedding = embedding_service.create_embedding(combined_text)
            
            # Store in database
            db_article = await db_client.create_news_article(
                title=article.title,
                content=article.content,
                url=article.url,
                published_at=article.published_at,
                title_fr=title_fr,
                content_fr=content_fr,
                embedding=embedding
            )
            return {
                'id': db_article["id"],
                'title': article.title,
                'title_fr': title_fr,
                'url': article.url,
                'published_at': article.published_at
            }
            
        except Exception as e:
            logger.error(f"Error processing single article: {e}")
            return None

    async def get_articles_for_conversation(self, query: str, limit: int = 3) -> List[dict]:
        """
        Get relevant articles for conversation based on query using ChromaDB's vector search
        """
        try:
            async with db_client:
                # Use ChromaDB's built-in semantic search with query text
                relevant_articles = await db_client.search_articles_by_similarity(
                    query_text=query,
                    limit=limit,
                    similarity_threshold=0.3
                )
                
                return relevant_articles
                
        except Exception as e:
            logger.error(f"Error getting articles for conversation: {e}")
            return []

    def get_articles_for_conversation_sync(self, query: str, limit: int = 3) -> List[dict]:
        """
        Synchronous version for LangGraph nodes - uses ChromaDB's synchronous search
        """
        try:
            logger.info(f"Sync article search for: {query}")
            
            # Use ChromaDB's synchronous query method directly
            # breakpoint()  # Debug point - use 'python debug_news_processor.py' to test
            relevant_articles = db_client.search_articles_by_similarity_sync(
                query_text=query,
                limit=limit,
                similarity_threshold=0.3
            )



            logger.info(f"Found {len(relevant_articles)} relevant articles")
            return relevant_articles
            
        except Exception as e:
            logger.error(f"Error in sync article search: {e}")
            return []

    async def run_daily_processing_task(self):
        """
        Main task for daily processing - can be scheduled
        """
        try:
            await self.process_daily_news()
            logger.info("Daily news processing completed successfully")
        except Exception as e:
            logger.error(f"Daily news processing failed: {e}")


# Global processor instance
news_processor = DailyNewsProcessor()