from rest_framework import serializers
from django.conf import settings
import jwt
from datetime import datetime, timedelta
import uuid
from .models import User, Designer, Factory

class TokenRefreshSerializer(serializers.Serializer):
    """JWT 토큰 갱신 Serializer"""
    refresh = serializers.CharField()

    def validate(self, attrs):
        refresh_token = attrs.get('refresh')
        
        if not refresh_token:
            raise serializers.ValidationError('Refresh 토큰이 필요합니다.')
        
        try:
            # 커스텀 refresh 토큰 디코드 및 유효성 확인
            payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=['HS256'])
            if payload.get('token_type') != 'refresh':
                raise serializers.ValidationError('리프레시 토큰이 아닙니다.')

            # 사용자 클레임 추출
            user_claims = {k: payload.get(k) for k in ['designer_id', 'factory_id', 'user_id', 'name'] if payload.get(k) is not None}
            user_type = 'designer' if payload.get('designer_id') else ('factory' if payload.get('factory_id') else None)

            # 새 액세스 토큰
            access_payload = {
                **user_claims,
                'user_type': user_type,
                'exp': datetime.utcnow() + timedelta(hours=24),
                'iat': datetime.utcnow(),
            }
            new_access = jwt.encode(access_payload, settings.SECRET_KEY, algorithm='HS256')

            # 새 리프레시 토큰
            refresh_payload = {
                **user_claims,
                'token_type': 'refresh',
                'jti': str(uuid.uuid4()),
                'exp': datetime.utcnow() + timedelta(days=7),
                'iat': datetime.utcnow(),
            }
            new_refresh = jwt.encode(refresh_payload, settings.SECRET_KEY, algorithm='HS256')

            attrs['access'] = new_access
            attrs['refresh'] = new_refresh
            return attrs
        except jwt.ExpiredSignatureError:
            raise serializers.ValidationError('리프레시 토큰이 만료되었습니다.')
        except jwt.InvalidTokenError as e:
            raise serializers.ValidationError(f'유효하지 않은 토큰입니다: {str(e)}')


class UserSerializer(serializers.ModelSerializer):
    """사용자 정보 조회/수정 Serializer"""
    user_type = serializers.ReadOnlyField()
    
    class Meta:
        model = User
        fields = ['id', 'user_id', 'name', 'user_type', 'contact', 'address', 
                 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user_id', 'user_type', 'created_at', 'updated_at']


class DesignerSerializer(serializers.ModelSerializer):
    """디자이너 Serializer"""
    
    class Meta:
        model = Designer
        fields = ['id', 'user_id', 'name', 'profile_image', 'contact', 'address']
        read_only_fields = ['id']


class FactorySerializer(serializers.ModelSerializer):
    """공장 Serializer"""
    
    class Meta:
        model = Factory
        fields = ['id', 'user_id', 'name', 'profile_image', 'contact', 'address']
        read_only_fields = ['id']


class DesignerLoginSerializer(serializers.Serializer):
    """디자이너 로그인 Serializer"""
    user_id = serializers.CharField(max_length=50)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user_id = attrs.get('user_id')
        password = attrs.get('password')

        if not user_id or not password:
            raise serializers.ValidationError('사용자 ID와 비밀번호를 모두 입력해주세요.')

        try:
            designer = Designer.objects.get(user_id=user_id)
            
            if not designer.check_password(password):
                raise serializers.ValidationError("비밀번호가 올바르지 않습니다.")
            
            attrs['designer'] = designer
            return attrs
                
        except Designer.DoesNotExist:
            raise serializers.ValidationError("존재하지 않는 디자이너입니다.")


class FactoryLoginSerializer(serializers.Serializer):
    """공장 로그인 Serializer"""
    user_id = serializers.CharField(max_length=50)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user_id = attrs.get('user_id')
        password = attrs.get('password')

        if not user_id or not password:
            raise serializers.ValidationError('사용자 ID와 비밀번호를 모두 입력해주세요.')

        try:
            factory = Factory.objects.get(user_id=user_id)
            
            if not factory.check_password(password):
                raise serializers.ValidationError("비밀번호가 올바르지 않습니다.")
            
            attrs['factory'] = factory
            return attrs
                
        except Factory.DoesNotExist:
            raise serializers.ValidationError("존재하지 않는 공장입니다.")