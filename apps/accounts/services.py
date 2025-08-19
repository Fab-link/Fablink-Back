"""
accounts 앱의 비즈니스 로직을 담당하는 서비스 레이어
"""

from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from .models import User
from .serializers import UserSerializer


class AuthService:
    """
    인증 관련 비즈니스 로직을 처리하는 서비스
    """
    
    
    
    @staticmethod
    def logout_user(refresh_token: str) -> dict:
        """
        사용자 로그아웃 처리
        
        Args:
            refresh_token (str): 리프레시 토큰
            
        Returns:
            dict: 로그아웃 결과
            
        Raises:
            serializers.ValidationError: 로그아웃 실패 시
        """
        if not refresh_token:
            raise serializers.ValidationError('Refresh 토큰이 필요합니다.')
        
        try:
            # 토큰 블랙리스트에 추가
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            return {'success': True, 'message': '로그아웃 성공'}
            
        except TokenError:
            raise serializers.ValidationError('유효하지 않은 토큰입니다.')
        except Exception as e:
            raise serializers.ValidationError(f'로그아웃 실패: {str(e)}')
    
    @staticmethod
    def get_user_info(user: User) -> dict:
        """
        사용자 정보 조회
        
        Args:
            user (User): 조회할 사용자
            
        Returns:
            dict: 사용자 정보
        """
        serializer = UserSerializer(user)
        return serializer.data


class UserService:
    """
    사용자 관리 관련 비즈니스 로직을 처리하는 서비스
    """
    
    @staticmethod
    def create_user(user_data: dict) -> User:
        """
        새 사용자 생성
        
        Args:
            user_data (dict): 사용자 데이터
            
        Returns:
            User: 생성된 사용자
        """
        # 사용자 생성 로직
        user = User.objects.create_user(**user_data)
        return user
    
    @staticmethod
    def update_user(user: User, update_data: dict) -> User:
        """
        사용자 정보 업데이트
        
        Args:
            user (User): 업데이트할 사용자
            update_data (dict): 업데이트 데이터
            
        Returns:
            User: 업데이트된 사용자
        """
        for field, value in update_data.items():
            if hasattr(user, field):
                setattr(user, field, value)
        user.save()
        return user
    
    @staticmethod
    def get_users_by_type(user_type: str) -> list:
        """
        사용자 타입별 사용자 목록 조회
        
        Args:
            user_type (str): 사용자 타입
            
        Returns:
            list: 사용자 목록
        """
        return User.objects.filter(user_type=user_type)
    
    @staticmethod
    def is_user_id_available(user_id: str) -> bool:
        """
        사용자 ID 사용 가능 여부 확인
        
        Args:
            user_id (str): 확인할 사용자 ID
            
        Returns:
            bool: 사용 가능 여부
        """
        return not User.objects.filter(user_id=user_id).exists()
