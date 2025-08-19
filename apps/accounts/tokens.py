from django.conf import settings
import jwt
from datetime import datetime, timedelta
import uuid


class DesignerToken:
    """Designer용 커스텀 JWT 토큰"""
    
    @staticmethod
    def for_designer(designer):
        """Designer 객체로부터 JWT 토큰 생성"""
        payload = {
            'designer_id': designer.id,
            'user_id': designer.user_id,
            'name': designer.name,
            'user_type': 'designer',
            'exp': datetime.utcnow() + timedelta(hours=24),  # 24시간 만료
            'iat': datetime.utcnow(),
        }
        
        access_token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
        
        # Refresh 토큰 (7일 만료)
        refresh_payload = {
            'designer_id': designer.id,
            'user_id': designer.user_id,
            'token_type': 'refresh',
            'jti': str(uuid.uuid4()),
            'exp': datetime.utcnow() + timedelta(days=7),
            'iat': datetime.utcnow(),
        }
        
        refresh_token = jwt.encode(refresh_payload, settings.SECRET_KEY, algorithm='HS256')
        
        return {
            'access': access_token,
            'refresh': refresh_token
        }
    
    @staticmethod
    def verify_token(token):
        """토큰 검증"""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            raise Exception('토큰이 만료되었습니다.')
        except jwt.InvalidTokenError:
            raise Exception('유효하지 않은 토큰입니다.')


class FactoryToken:
    """Factory용 커스텀 JWT 토큰"""
    
    @staticmethod
    def for_factory(factory):
        """Factory 객체로부터 JWT 토큰 생성"""
        payload = {
            'factory_id': factory.id,
            'user_id': factory.user_id,
            'name': factory.name,
            'user_type': 'factory',
            'exp': datetime.utcnow() + timedelta(hours=24),  # 24시간 만료
            'iat': datetime.utcnow(),
        }
        
        access_token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
        
        # Refresh 토큰 (7일 만료)
        refresh_payload = {
            'factory_id': factory.id,
            'user_id': factory.user_id,
            'token_type': 'refresh',
            'jti': str(uuid.uuid4()),
            'exp': datetime.utcnow() + timedelta(days=7),
            'iat': datetime.utcnow(),
        }
        
        refresh_token = jwt.encode(refresh_payload, settings.SECRET_KEY, algorithm='HS256')
        
        return {
            'access': access_token,
            'refresh': refresh_token
        }
    
    @staticmethod
    def verify_token(token):
        """토큰 검증"""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            raise Exception('토큰이 만료되었습니다.')
        except jwt.InvalidTokenError:
            raise Exception('유효하지 않은 토큰입니다.')