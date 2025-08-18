# CI/CD 설정 가이드

## 🔐 GitHub Secrets 설정

CI/CD 파이프라인이 정상 동작하려면 다음 Secrets를 GitHub 리포지토리에 설정해야 합니다.

### **필수 Secrets**

#### **1. AWS_ACCESS_KEY_ID**
```
AWS IAM 사용자의 Access Key ID
```

#### **2. AWS_SECRET_ACCESS_KEY**
```
AWS IAM 사용자의 Secret Access Key
```

### **GitHub Secrets 설정 방법**

1. **GitHub 리포지토리로 이동**
2. **Settings** 탭 클릭
3. **Secrets and variables** → **Actions** 클릭
4. **New repository secret** 클릭
5. 각 Secret을 하나씩 추가

### **AWS IAM 권한 설정**

CI/CD용 IAM 사용자에게 다음 권한이 필요합니다:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ecr:GetAuthorizationToken",
                "ecr:BatchCheckLayerAvailability",
                "ecr:GetDownloadUrlForLayer",
                "ecr:BatchGetImage",
                "ecr:InitiateLayerUpload",
                "ecr:UploadLayerPart",
                "ecr:CompleteLayerUpload",
                "ecr:PutImage"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "eks:DescribeCluster",
                "eks:ListClusters"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "sts:GetCallerIdentity"
            ],
            "Resource": "*"
        }
    ]
}
```

## 🚀 CI/CD 워크플로우 동작 방식

### **Dev 환경 배포**

#### **트리거 조건:**
- `develop` 브랜치에 **push** 될 때 (PR 머지 완료 후)
- `develop` 브랜치로의 **PR 생성** 시 (테스트만 실행)

#### **워크플로우 단계:**
1. **테스트 실행**
   - Python 3.11 환경 설정
   - PostgreSQL 15 서비스 시작
   - 의존성 설치 (requirements/dev.txt)
   - 환경변수 설정
   - Django 마이그레이션 실행
   - 단위 테스트 실행
   - 코드 문법 검사

2. **빌드 및 배포** (develop 브랜치 push 시에만)
   - AWS 인증 설정
   - ECR 로그인
   - Docker 이미지 빌드 (linux/amd64)
   - ECR에 이미지 푸시
   - EKS 클러스터 연결
   - Kubernetes 배포 업데이트
   - 배포 상태 확인
   - 헬스체크 실행

#### **배포 결과:**
- ✅ 성공 시: API Gateway URL과 Swagger 링크 출력
- ❌ 실패 시: 디버그 가이드 제공

## 🧪 테스트 실행

### **로컬에서 테스트**
```bash
# 환경변수 설정
export DJANGO_ENV=test
export SECRET_KEY=test-key
export DEBUG=True
export DB_ENGINE=django.db.backends.postgresql
export DB_NAME=test_fablink
export DB_USER=postgres
export DB_PASSWORD=postgres
export DB_HOST=localhost
export DB_PORT=5432

# 테스트 실행
python manage.py test
```

### **커버리지 테스트**
```bash
# 커버리지와 함께 테스트 실행
coverage run --source='.' manage.py test
coverage report
coverage html  # HTML 리포트 생성
```

## 🔄 브랜치 전략

### **현재 설정된 브랜치 전략:**
```
feature/* → develop → (자동 배포) → Dev 환경
```

### **권장 워크플로우:**
1. **기능 개발**: `feature/new-feature` 브랜치에서 작업
2. **PR 생성**: `feature/new-feature` → `develop`
3. **테스트 실행**: PR 생성 시 자동으로 테스트 실행
4. **코드 리뷰**: 팀원들의 리뷰 진행
5. **머지**: `develop` 브랜치로 머지
6. **자동 배포**: Dev 환경에 자동 배포

## 📊 모니터링

### **배포 상태 확인**
```bash
# Pod 상태 확인
kubectl get pods -n fablink-dev

# 배포 히스토리 확인
kubectl rollout history deployment/fablink-backend -n fablink-dev

# 로그 확인
kubectl logs -f deployment/fablink-backend -n fablink-dev
```

### **헬스체크 URL**
- **Health**: https://8wwdg03sr6.execute-api.ap-northeast-2.amazonaws.com/health/
- **Ready**: https://8wwdg03sr6.execute-api.ap-northeast-2.amazonaws.com/ready/
- **Swagger**: https://8wwdg03sr6.execute-api.ap-northeast-2.amazonaws.com/api/docs/

## 🚨 트러블슈팅

### **일반적인 문제들**

#### **1. AWS 인증 실패**
```
Error: The security token included in the request is invalid
```
**해결방법**: GitHub Secrets의 AWS 키 확인

#### **2. ECR 권한 오류**
```
Error: no basic auth credentials
```
**해결방법**: ECR 권한 확인 및 리전 설정 확인

#### **3. EKS 클러스터 접근 실패**
```
Error: You must be logged in to the server
```
**해결방법**: EKS 클러스터 권한 및 클러스터 이름 확인

#### **4. 배포 타임아웃**
```
Error: deployment "fablink-backend" exceeded its progress deadline
```
**해결방법**: 
- 이미지 크기 최적화
- 리소스 할당 확인
- 헬스체크 설정 확인

## 📝 다음 단계

1. **GitHub Secrets 설정** ✅
2. **첫 번째 배포 테스트** 
3. **Production CI/CD 구축**
4. **알림 시스템 추가** (Slack, 이메일)
5. **보안 스캔 추가** (Snyk, SAST)
6. **성능 테스트 추가**
