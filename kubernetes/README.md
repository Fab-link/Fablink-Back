# Kubernetes 배포 관리

FabLink Backend의 Kubernetes 배포를 위한 매니페스트와 환경별 설정을 관리합니다.

## 📁 디렉토리 구조

```
kubernetes/
├── README.md                    # 이 파일
├── base/                        # 공통 매니페스트
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   └── ingress.yaml
├── environments/
│   ├── dev/                     # 개발 환경
│   │   ├── README.md
│   │   ├── kustomization.yaml
│   │   ├── deployment-patch.yaml
│   │   ├── configmap-patch.yaml
│   │   └── ingress-patch.yaml
│   └── prod/                    # 운영 환경
│       ├── README.md
│       ├── kustomization.yaml
│       ├── deployment-patch.yaml
│       ├── configmap-patch.yaml
│       └── ingress-patch.yaml
└── scripts/
    ├── deploy.sh                # 배포 스크립트
    ├── rollback.sh              # 롤백 스크립트
    └── health-check.sh          # 헬스체크 스크립트
```

## 🚀 배포 방법

### 개발 환경 배포
```bash
# 개발 환경 배포
kubectl apply -k kubernetes/environments/dev/

# 배포 상태 확인
kubectl get pods -n fablink-dev
kubectl get svc -n fablink-dev
```

### 운영 환경 배포
```bash
# 운영 환경 배포
kubectl apply -k kubernetes/environments/prod/

# 배포 상태 확인
kubectl get pods -n fablink-prod
kubectl get svc -n fablink-prod
```

## 🔧 환경별 설정

각 환경별 세부 설정은 해당 환경 디렉토리의 README.md를 참조하세요:

- [개발 환경 설정](./environments/dev/README.md)
- [운영 환경 설정](./environments/prod/README.md)

## 📋 주요 컴포넌트

### Base 매니페스트
- **Deployment**: Django 애플리케이션 컨테이너 배포
- **Service**: 내부 서비스 노출
- **ConfigMap**: 환경변수 및 설정 파일
- **Secret**: 민감한 정보 (DB 패스워드, API 키 등)
- **Ingress**: 외부 트래픽 라우팅

### 환경별 패치
- **Deployment Patch**: 리소스 할당, 레플리카 수 조정
- **ConfigMap Patch**: 환경별 설정값 오버라이드
- **Ingress Patch**: 도메인 및 SSL 설정

## 🔄 CI/CD 통합

GitHub Actions에서 다음과 같이 사용됩니다:

```yaml
# .github/workflows/deploy.yml 예시
- name: Deploy to Dev
  if: github.ref == 'refs/heads/dev'
  run: |
    kubectl apply -k kubernetes/environments/dev/

- name: Deploy to Prod  
  if: github.ref == 'refs/heads/main'
  run: |
    kubectl apply -k kubernetes/environments/prod/
```

## 🛠️ 유용한 명령어

```bash
# 특정 환경의 리소스 확인
kubectl get all -n fablink-dev
kubectl get all -n fablink-prod

# 로그 확인
kubectl logs -f deployment/fablink-backend -n fablink-dev

# 포트 포워딩 (로컬 테스트)
kubectl port-forward svc/fablink-backend 8000:80 -n fablink-dev

# 설정 확인
kubectl describe configmap fablink-config -n fablink-dev
```

## ⚠️ 주의사항

1. **Secret 관리**: 민감한 정보는 절대 Git에 커밋하지 마세요
2. **네임스페이스**: 환경별로 다른 네임스페이스를 사용합니다
3. **리소스 제한**: 각 환경에 맞는 적절한 리소스를 할당하세요
4. **백업**: 운영 환경 배포 전 반드시 백업을 수행하세요
