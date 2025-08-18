"""
Core app views including health check endpoints
"""
import logging
from django.http import JsonResponse
from django.db import connection
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import os

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Basic health check endpoint for liveness probe
    Returns 200 if Django application is running
    """
    return Response({
        'status': 'healthy',
        'service': 'fablink-backend',
        'environment': getattr(settings, 'DJANGO_ENV', 'unknown'),
        'timestamp': request.META.get('HTTP_DATE', 'unknown')
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def readiness_check(request):
    """
    Readiness check endpoint for readiness probe
    Checks database and external service connections
    """
    checks = {
        'database': False,
        'dynamodb': False,
        'overall': False
    }
    
    errors = []
    
    # 1. Database connection check
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            checks['database'] = True
            logger.debug("Database connection: OK")
    except Exception as e:
        error_msg = f"Database connection failed: {str(e)}"
        errors.append(error_msg)
        logger.error(error_msg)
    
    # 2. DynamoDB connection check (if enabled)
    if getattr(settings, 'USE_DYNAMODB', False):
        try:
            # DynamoDB 연결 테스트
            dynamodb = boto3.client(
                'dynamodb',
                region_name=getattr(settings, 'DYNAMODB_REGION', 'ap-northeast-2')
            )
            
            # 테이블 존재 확인
            table_name = getattr(settings, 'DYNAMODB_TABLE_NAME', 'fablink-dynamodb-dev')
            dynamodb.describe_table(TableName=table_name)
            checks['dynamodb'] = True
            logger.debug("DynamoDB connection: OK")
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ResourceNotFoundException':
                error_msg = f"DynamoDB table not found: {table_name}"
            else:
                error_msg = f"DynamoDB error: {error_code}"
            errors.append(error_msg)
            logger.error(error_msg)
        except NoCredentialsError:
            error_msg = "DynamoDB credentials not found"
            errors.append(error_msg)
            logger.error(error_msg)
        except Exception as e:
            error_msg = f"DynamoDB connection failed: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
    else:
        # DynamoDB가 비활성화된 경우 체크 통과
        checks['dynamodb'] = True
        logger.debug("DynamoDB check skipped (disabled)")
    
    # 전체 상태 결정
    checks['overall'] = checks['database'] and checks['dynamodb']
    
    response_data = {
        'status': 'ready' if checks['overall'] else 'not_ready',
        'service': 'fablink-backend',
        'environment': getattr(settings, 'DJANGO_ENV', 'unknown'),
        'checks': checks,
        'timestamp': request.META.get('HTTP_DATE', 'unknown')
    }
    
    if errors:
        response_data['errors'] = errors
    
    # 모든 체크가 통과하면 200, 하나라도 실패하면 503
    response_status = status.HTTP_200_OK if checks['overall'] else status.HTTP_503_SERVICE_UNAVAILABLE
    
    return Response(response_data, status=response_status)


@api_view(['GET'])
@permission_classes([AllowAny])
def startup_check(request):
    """
    Startup check endpoint for startup probe
    Similar to readiness but with more lenient timeouts
    """
    return readiness_check(request)
