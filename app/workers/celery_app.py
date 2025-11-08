"""
Celery application configuration.
"""

import os
from celery import Celery
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "chat_with_pdf",
    broker=redis_url,
    backend=redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

