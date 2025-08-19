FROM python:3.11-slim

WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# 로그 디렉토리 생성
RUN mkdir -p /var/log/fablink && chmod 755 /var/log/fablink

# Python 의존성 설치
COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/production.txt

# 애플리케이션 코드 복사
COPY . .

# 환경 변수 설정
ENV DJANGO_ENV=prod
ENV DJANGO_SETTINGS_MODULE=fablink_project.settings
ENV DEBUG=False
ENV PYTHONPATH=/app

# 포트 노출
EXPOSE 8000

# 애플리케이션 실행
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "fablink_project.wsgi:application"]
