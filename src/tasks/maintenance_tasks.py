from celery import current_app as celery_app
from celery.utils.log import get_task_logger
from datetime import datetime, timedelta
import asyncio

from src.database.client import db_client

logger = get_task_logger(__name__)


@celery_app.task(bind=True, name='src.tasks.maintenance_tasks.cleanup_old_articles')
def cleanup_old_articles(self, days_old: int = 30):
    """
    Clean up articles older than specified days
    """
    logger.info(f"🧹 Starting cleanup of articles older than {days_old} days")
    
    try:
        result = asyncio.run(_cleanup_old_articles_async(days_old))
        
        logger.info(f"✅ Cleanup completed. Removed {result['deleted_count']} articles")
        return {
            'status': 'success',
            'deleted_count': result['deleted_count'],
            'cutoff_date': result['cutoff_date'],
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as exc:
        logger.error(f"❌ Cleanup failed: {str(exc)}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


async def _cleanup_old_articles_async(days_old: int):
    """
    Async helper for cleanup
    """
    cutoff_date = datetime.now() - timedelta(days=days_old)
    deleted_count = 0
    
    async with db_client:
        # This would need to be implemented in the database client
        # For now, we'll just log the intent
        logger.info(f"🗑️  Would delete articles older than {cutoff_date}")
        # deleted_count = await db_client.delete_old_articles(cutoff_date)
    
    return {
        'deleted_count': deleted_count,
        'cutoff_date': cutoff_date.isoformat()
    }


@celery_app.task(bind=True, name='src.tasks.maintenance_tasks.health_check')
def health_check(self):
    """
    Perform system health check
    """
    logger.info("🏥 Performing system health check")
    
    try:
        result = asyncio.run(_health_check_async())
        
        logger.info(f"✅ Health check completed. Status: {result['status']}")
        return result
        
    except Exception as exc:
        logger.error(f"❌ Health check failed: {str(exc)}")
        return {
            'status': 'unhealthy',
            'error': str(exc),
            'timestamp': datetime.now().isoformat()
        }


async def _health_check_async():
    """
    Async helper for health check
    """
    checks = {
        'database': False,
        'embedding_service': False,
        'redis': False
    }
    
    # Test database connection
    try:
        async with db_client:
            checks['database'] = True
            logger.info("✅ Database connection: OK")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
    
    # Test embedding service
    try:
        from src.services.embeddings import embedding_service
        test_embedding = embedding_service.create_embedding("test")
        if test_embedding:
            checks['embedding_service'] = True
            logger.info("✅ Embedding service: OK")
    except Exception as e:
        logger.error(f"❌ Embedding service failed: {e}")
    
    # Test Redis connection
    try:
        from celery import current_app
        current_app.broker_connection().ensure_connection(max_retries=3)
        checks['redis'] = True
        logger.info("✅ Redis connection: OK")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
    
    overall_status = 'healthy' if all(checks.values()) else 'degraded'
    
    return {
        'status': overall_status,
        'checks': checks,
        'timestamp': datetime.now().isoformat()
    }
