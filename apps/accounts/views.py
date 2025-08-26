from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from .tokens import DesignerToken, FactoryToken

from .serializers import (
    UserSerializer,
    TokenRefreshSerializer,
    DesignerLoginSerializer,
    FactoryLoginSerializer,
    DesignerSerializer,
    FactorySerializer
)
from .models import User


# ==================== 루트 ====================

@api_view(['GET'])
@permission_classes([AllowAny])
def accounts_root_view(request):
    """
    Accounts API 루트 엔드포인트
    GET /api/accounts/
    
    사용 가능한 엔드포인트 목록을 반환합니다.
    """
    return Response({
        'message': 'Accounts API',
        'version': '1.0.0',
        'endpoints': {
            'designer_login': '/api/accounts/designer/login/',
            'factory_login': '/api/accounts/factory/login/',
            'logout': '/api/accounts/logout/',
            'token_refresh': '/api/accounts/token/refresh/',
            'profile': '/api/accounts/profile/',
            'user_info': '/api/accounts/user_info/',
        },
        'description': 'FabLink 사용자 계정 관리 API'
    })


# ==================== 로그아웃 ====================

@api_view(['POST'])
@permission_classes([AllowAny])
def logout_view(request):
    """
    통합 로그아웃 API
    POST /api/accounts/logout/
    
    Request Body:
    {
        "refresh": "your-refresh-token"
    }
    """
    try:
        # 커스텀 JWT 토큰은 블랙리스트 처리 없이 단순 성공 응답
        return Response({
            'success': True,
            'message': '로그아웃 성공'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': f'로그아웃 실패: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def token_refresh_view(request):
    """
    JWT 토큰 갱신 API
    POST /api/accounts/token/refresh/
    """
    serializer = TokenRefreshSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'success': False,
            'message': '토큰 갱신 실패',
            'errors': serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)
    
    return Response({
        'success': True,
        'message': '토큰 갱신 성공',
        'tokens': {
            'access': serializer.validated_data['access'],
            'refresh': serializer.validated_data['refresh']
        }
    }, status=status.HTTP_200_OK)

# ==================== 디자이너 관련 ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile_view(request):
    """
    사용자 프로필 조회 API
    GET /api/accounts/profile/
    """
    try:
        user = request.user
        user_serializer = UserSerializer(user, context={'request': request})
        
        response_data = {
            'success': True,
            'user': user_serializer.data,
            'user_type': None
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': f'사용자 정보 조회 실패: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== 디자이너 로그인 ====================

@api_view(['POST'])
@permission_classes([AllowAny])
def designer_login_view(request):
    """
    디자이너 로그인 API
    POST /api/accounts/designer/login/
    
    Request Body:
    {
        "user_id": "designer123",
        "password": "password123"
    }
    """
    serializer = DesignerLoginSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'success': False,
            'message': '로그인 실패',
            'errors': serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        designer = serializer.validated_data['designer']
        
        # 커스텀 JWT 토큰 생성
        tokens = DesignerToken.for_designer(designer)
        
        # 디자이너 정보 직렬화
        designer_data = DesignerSerializer(designer, context={'request': request}).data
        
        return Response({
            'success': True,
            'message': '디자이너 로그인 성공',
            'user_type': 'designer',
            'tokens': tokens,
            'designer': designer_data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': f'로그인 실패: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== 공장 로그인 ====================

@api_view(['POST'])
@permission_classes([AllowAny])
def factory_login_view(request):
    """
    공장 로그인 API
    POST /api/accounts/factory/login/
    
    Request Body:
    {
        "user_id": "factory123",
        "password": "password123"
    }
    """
    serializer = FactoryLoginSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'success': False,
            'message': '로그인 실패',
            'errors': serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        factory = serializer.validated_data['factory']
        
        # 커스텀 JWT 토큰 생성
        tokens = FactoryToken.for_factory(factory)
        
        # 공장 정보 직렬화
        factory_data = FactorySerializer(factory, context={'request': request}).data
        
        return Response({
            'success': True,
            'message': '공장 로그인 성공',
            'user_type': 'factory',
            'tokens': tokens,
            'factory': factory_data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': f'로그인 실패: {str(e)}',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)