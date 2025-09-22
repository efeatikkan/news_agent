from celery import current_app as celery_app
from celery.utils.log import get_task_logger
from typing import Dict, List
import asyncio
from datetime import datetime

from src.services.news_processor import news_processor
from src.services.news_fetcher import BBCNewsFetcher
from src.services.translator import FrenchB1Translator
from src.services.embeddings import embedding_service
from src.database.client import db_client

logger = get_task_logger(__name__)


@celery_app.task(bind=True, name='src.tasks.news_tasks.fetch_and_process_news')
def fetch_and_process_news(self, limit: int = 5):
    """
    Fetch and process news articles in background
    Runs every 30 seconds to demonstrate Celery scheduling
    """
    logger.info(f"🚀 Starting news processing task - limit: {limit}")
    
    try:
        # Run the async function in a new event loop
        result = asyncio.run(_process_news_async(limit))
        
        logger.info(f"✅ News processing completed successfully. Processed {result['processed_count']} new articles")
        return {
            'status': 'success',
            'processed_count': result['processed_count'],
            'skipped_count': result['skipped_count'],
            'total_fetched': result['total_fetched'],
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"❌ News processing failed: {str(exc)}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


async def _process_news_async(limit: int) -> Dict:
    """
    Async helper function to process news
    """
    news_fetcher = BBCNewsFetcher()
    translator = FrenchB1Translator()
    
    processed_count = 0
    skipped_count = 0
    total_fetched = 0
    
    try:
        logger.info("📰 Fetching latest news from BBC...")
        articles = await news_fetcher.fetch_latest_news(limit)
        total_fetched = len(articles)
        logger.info(f"📥 Fetched {total_fetched} articles from BBC")
        
        async with db_client:
            for i, article in enumerate(articles, 1):
                try:
                    logger.info(f"🔄 Processing article {i}/{total_fetched}: {article.title[:50]}...")
                    
                    # Check if article already exists
                    existing = await db_client.get_news_article_by_url(article.url)
                    if existing:
                        logger.info(f"⏭️  Article already exists, skipping: {article.title[:30]}...")
                        skipped_count += 1
                        continue
                    
                    # Process the article
                    await _process_single_article_async(article, translator)
                    processed_count += 1
                    logger.info(f"✅ Successfully processed: {article.title[:30]}...")
                    
                except Exception as e:
                    logger.error(f"❌ Error processing article {article.title[:30]}: {e}")
                    continue
        
        return {
            'processed_count': processed_count,
            'skipped_count': skipped_count,
            'total_fetched': total_fetched
        }
        
    finally:
        await news_fetcher.close()


async def _process_single_article_async(article, translator):
    """
    Process a single article: translate, create embeddings, and store
    """
    try:
        # Translate to French B1 level
        logger.info(f"🔤 Translating article: {article.title[:30]}...")
        title_fr = await translator.translate_title(article.title)
        content_fr = await translator.translate_content(article.content)
        
        # Create embeddings for the French version
        logger.info(f"🧮 Creating embeddings for: {article.title[:30]}...")
        combined_text = f"{title_fr} {content_fr}"
        embedding = embedding_service.create_embedding(combined_text)
        
        # Store in database
        logger.info(f"💾 Storing article in database: {article.title[:30]}...")
        await db_client.create_news_article(
            title=article.title,
            content=article.content,
            url=article.url,
            published_at=article.published_at,
            title_fr=title_fr,
            content_fr=content_fr,
            embedding=embedding
        )
        
    except Exception as e:
        logger.error(f"❌ Error processing single article: {e}")
        raise


@celery_app.task(bind=True, name='src.tasks.news_tasks.translate_article')
def translate_article(self, article_data: Dict):
    """
    Translate a single article (can be used for parallel processing)
    """
    logger.info(f"🔤 Translating article: {article_data['title'][:50]}...")
    
    try:
        result = asyncio.run(_translate_article_async(article_data))
        logger.info(f"✅ Translation completed for: {article_data['title'][:30]}...")
        return result
        
    except Exception as exc:
        logger.error(f"❌ Translation failed: {str(exc)}")
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))


async def _translate_article_async(article_data: Dict) -> Dict:
    """
    Async helper for article translation
    """
    translator = FrenchB1Translator()
    
    title_fr = await translator.translate_title(article_data['title'])
    content_fr = await translator.translate_content(article_data['content'])
    
    return {
        'title_fr': title_fr,
        'content_fr': content_fr,
        'url': article_data['url']
    }


@celery_app.task(bind=True, name='src.tasks.news_tasks.create_embeddings')
def create_embeddings(self, text_data: Dict):
    """
    Create embeddings for translated content
    """
    logger.info(f"🧮 Creating embeddings for: {text_data['title_fr'][:30]}...")
    
    try:
        combined_text = f"{text_data['title_fr']} {text_data['content_fr']}"
        embedding = embedding_service.create_embedding(combined_text)
        
        return {
            'embedding': embedding,
            'url': text_data['url']
        }
        
    except Exception as exc:
        logger.error(f"❌ Embedding creation failed: {str(exc)}")
        raise self.retry(exc=exc, countdown=15 * (2 ** self.request.retries))
