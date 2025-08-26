FROM python:3.11-slim

# 빌드 인자로 환경 지정 (기본값: prod)
ARG ENV=prod

# 환경변수 설정 (빌드 시 고정)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_ENV=${ENV}

WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 비root 사용자 생성 (보안)
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Python 의존성 설치 (환경별)
COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/${ENV}.txt

# 애플리케이션 코드 복사
COPY . .

# 권한 설정
RUN chown -R appuser:appuser /app
USER appuser

# 헬스체크 추가 (Kubernetes probe와 연동)
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# 포트 노출
EXPOSE 8000

# 애플리케이션 실행 (worker 수 1로 줄임 - 메모리 절약)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--timeout", "120", "fablink_project.wsgi:application"]
