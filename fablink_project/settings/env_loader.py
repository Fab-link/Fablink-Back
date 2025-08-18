"""
로컬 환경 전용 .env 파일 로더
"""
import os
from pathlib import Path
from dotenv import load_dotenv


def load_environment_variables():
    """
    로컬 환경에서만 .env 파일을 로드합니다.
    
    우선순위:
    1. .env.local
    2. .env
    """
    
    # 프로젝트 루트 디렉토리
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    
    # 로컬 환경용 .env 파일들 (우선순위 순)
    env_files = [
        BASE_DIR / '.env.local',
        BASE_DIR / '.env',
    ]
    
    # 첫 번째로 발견되는 파일 로드
    loaded_file = None
    for env_file in env_files:
        if env_file.exists():
            load_dotenv(env_file, override=True)
            loaded_file = env_file.name
            break
    
    # 로드 결과 출력
    if loaded_file:
        print(f"🔧 환경변수 파일 로드됨: {loaded_file}")
    else:
        print("⚠️  .env 파일을 찾을 수 없습니다")
    
    return loaded_file
