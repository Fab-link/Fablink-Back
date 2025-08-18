import os

# Docker 빌드 시 설정된 환경 사용
env = os.getenv('DJANGO_ENV', 'local')
print(f"🌍 Django 환경: {env} (Docker 빌드 시 고정)")

# 로컬 환경에서만 .env 파일 로드
if env == 'local':
    print("💻 로컬 환경 - .env 파일 로드")
    from .env_loader import load_environment_variables
    load_environment_variables()
else:
    print(f"🚀 {env.upper()} 환경 - ConfigMap/Secret 사용")

# 모든 환경에서 base.py 사용
from .base import *
print("📦 설정 로드 완료")
