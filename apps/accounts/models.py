from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.contrib.auth.hashers import make_password, check_password
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, user_id, name, password=None, **extra_fields):
        if not user_id:
            raise ValueError('사용자 ID는 필수입니다')
        
        user = self.model(
            user_id=user_id,
            name=name,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, user_id, name, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        return self.create_user(user_id, name, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """기본 사용자 모델"""
    user_id = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=20, default='')
    contact = models.CharField(max_length=20, default='')
    address = models.TextField(default='')
    
    # 권한 관련 필드
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    
    # 타임스탬프
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'user_id'
    REQUIRED_FIELDS = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.user_id})"
    
    @property
    def user_type(self):
        """사용자 타입 반환 (하위 호환성)"""
        if hasattr(self, 'designer'):
            return 'designer'
        elif hasattr(self, 'factory'):
            return 'factory'
        return None
    
    class Meta:
        verbose_name = '사용자'
        verbose_name_plural = '사용자들'


class Designer(models.Model):
    """디자이너 모델"""
    id = models.BigAutoField(primary_key=True)
    user_id = models.CharField(max_length=50, unique=True, verbose_name='디자이너 아이디')
    password = models.CharField(max_length=128, verbose_name='디자이너 패스워드')
    name = models.CharField(max_length=50, verbose_name='디자이너 이름')
    profile_image = models.FileField(upload_to='designer_profiles/', null=True, blank=True, verbose_name='디자이너 프로필 사진')
    contact = models.CharField(max_length=50, default='', verbose_name='디자이너 전화번호')
    address = models.CharField(max_length=100, default='', verbose_name='디자이너 주소')
    
    def set_password(self, raw_password):
        """패스워드 해시화"""
        self.password = make_password(raw_password)
    
    def check_password(self, raw_password):
        """패스워드 검증"""
        return check_password(raw_password, self.password)
    
    def __str__(self):
        return f"디자이너: {self.name}"
    
    class Meta:
        db_table = 'designer'
        verbose_name = '디자이너'
        verbose_name_plural = '디자이너들'


class Factory(models.Model):
    """공장 모델"""
    id = models.BigAutoField(primary_key=True)
    user_id = models.CharField(max_length=50, unique=True, verbose_name='공장 아이디')
    password = models.CharField(max_length=128, verbose_name='공장 패스워드')
    name = models.CharField(max_length=50, verbose_name='공장 이름')
    profile_image = models.FileField(upload_to='factory_profiles/', null=True, blank=True, verbose_name='공장 프로필 사진')
    contact = models.CharField(max_length=50, default='', verbose_name='공장 전화번호')
    address = models.CharField(max_length=100, default='', verbose_name='공장 주소')
    
    def set_password(self, raw_password):
        """패스워드 해시화"""
        self.password = make_password(raw_password)
    
    def check_password(self, raw_password):
        """패스워드 검증"""
        return check_password(raw_password, self.password)
    
    def __str__(self):
        return f"공장: {self.name}"
    
    class Meta:
        db_table = 'factory'
        verbose_name = '공장'
        verbose_name_plural = '공장들'