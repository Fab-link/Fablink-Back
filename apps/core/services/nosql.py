"""
Unified NoSQL service for FabLink project.
Provides unified interface for both MongoDB and DynamoDB based on environment.
- local: MongoDB
- dev, prod: DynamoDB
"""
from django.conf import settings

def get_collection(collection_name: str):
    """
    Get collection/table interface based on environment.
    - local: MongoDB collection
    - dev, prod: DynamoDB wrapper
    """
    django_env = getattr(settings, 'DJANGO_ENV', 'local')
    
    if django_env in ['dev', 'prod']:
        # Use DynamoDB in dev/prod environments
        from .dynamodb import get_collection as get_dynamodb_collection
        return get_dynamodb_collection(collection_name)
    else:
        # Use MongoDB in local environment
        from .mongo import get_collection as get_mongo_collection
        return get_mongo_collection(collection_name)

def now_iso_with_minutes() -> str:
    """Return ISO string with timezone info, minute precision."""
    from django.utils import timezone
    dt = timezone.now().astimezone(timezone.get_current_timezone())
    return dt.isoformat(timespec='minutes')

def ensure_indexes():
    """Ensure required indexes exist on collections/tables."""
    django_env = getattr(settings, 'DJANGO_ENV', 'local')
    
    if django_env in ['dev', 'prod']:
        # DynamoDB indexes are managed at table level
        from .dynamodb import ensure_indexes as ensure_dynamodb_indexes
        ensure_dynamodb_indexes()
    else:
        # MongoDB indexes
        from .mongo import ensure_indexes as ensure_mongo_indexes
        ensure_mongo_indexes()
