from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .tokens import DesignerToken, FactoryToken
from .models import Designer, Factory


class _BaseUserProxy:
    """DRF 권한 체크 호환을 위한 사용자 프록시 베이스."""
    is_authenticated = True
    is_active = True
    is_anonymous = False

    def __init__(self, obj):
        self._obj = obj

    def __str__(self):
        return str(self._obj)


class DesignerUserProxy(_BaseUserProxy):
    def __init__(self, designer: Designer):
        super().__init__(designer)
        # 뷰 로직 호환: request.user.designer 로 접근 가능하게 유지
        self.designer = designer


class FactoryUserProxy(_BaseUserProxy):
    def __init__(self, factory: Factory):
        super().__init__(factory)
        # 뷰 로직 호환: request.user.factory 로 접근 가능하게 유지
        self.factory = factory


class DesignerAuthentication(BaseAuthentication):
    """Designer용 JWT 인증"""
    
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header.split(' ')[1]
        
        try:
            payload = DesignerToken.verify_token(token)
            
            if payload.get('user_type') != 'designer':
                return None
                
            designer = Designer.objects.get(id=payload['designer_id'])
            # DRF 권한 체크 및 뷰 로직 호환을 위한 프록시 반환
            return (DesignerUserProxy(designer), token)
            
        except Designer.DoesNotExist:
            raise AuthenticationFailed('Designer not found')
        except Exception as e:
            raise AuthenticationFailed(str(e))


class FactoryAuthentication(BaseAuthentication):
    """Factory용 JWT 인증"""
    
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header.split(' ')[1]
        
        try:
            payload = FactoryToken.verify_token(token)
            
            if payload.get('user_type') != 'factory':
                return None
                
            factory = Factory.objects.get(id=payload['factory_id'])
            # DRF 권한 체크 및 뷰 로직 호환을 위한 프록시 반환
            return (FactoryUserProxy(factory), token)
            
        except Factory.DoesNotExist:
            raise AuthenticationFailed('Factory not found')
        except Exception as e:
            raise AuthenticationFailed(str(e))