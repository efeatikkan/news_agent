from celery import Celery
from celery.schedules import crontab
import os
from dotenv import load_dotenv

load_dotenv()

# Create Celery app
celery_app = Celery(
    'news_discuss',
    broker=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    include=[
        'src.tasks.news_tasks',
        'src.tasks.maintenance_tasks',
    ]
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Task routing
    task_routes={
        'src.tasks.news_tasks.*': {'queue': 'news_processing'},
        'src.tasks.maintenance_tasks.*': {'queue': 'maintenance'},
    },
    
    # Worker settings
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    
    # Retry settings
    task_default_retry_delay=60,
    task_max_retries=3,
    
    # Result backend settings
    result_expires=3600,  # 1 hour
    
    # Beat schedule for periodic tasks
    beat_schedule={
        'fetch-news-every-30-seconds': {
            'task': 'src.tasks.news_tasks.fetch_and_process_news',
            'schedule': 300.0,  # Every 5 minutes
            'options': {'queue': 'news_processing'}
        },
        'cleanup-old-articles-daily': {
            'task': 'src.tasks.maintenance_tasks.cleanup_old_articles',
            'schedule': crontab(hour=3, minute=0),  # Daily at 3 AM
            'options': {'queue': 'maintenance'}
        },
        'health-check-every-5-minutes': {
            'task': 'src.tasks.maintenance_tasks.health_check',
            'schedule': 300.0,  # Every 5 minutes
            'options': {'queue': 'maintenance'}
        },
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks()
