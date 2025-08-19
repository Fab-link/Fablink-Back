# 개발 환경 (Development) 설정

FabLink Backend 개발 환경의 Kubernetes 배포 설정입니다.

## 🎯 환경 개요

| 항목 | 값 |
|------|-----|
| **AWS 계정** | `853963783084` |
| **네임스페이스** | `fablink-dev` |
| **도메인** | `dev-api.fablink.com` |
| **클러스터** | `fablink-cluster-dev` |
| **리전** | `ap-northeast-2` |
| **환경 타입** | Development |

## 🌐 네트워크 아키텍처

### 트래픽 흐름
```
fab-link-dev.org (Frontend - S3)
    ↓ API 호출
API Gateway (8wwdg03sr6)
    ↓ VPC Link
Network Load Balancer (fablink-dev-nlb)
    ↓ Target Group (Port 30080)
EKS Service (NodePort)
    ↓ Pod Network
Pod (fablink-backend)
    ↓ Database Connections
Aurora DB (fablink) + DynamoDB (fablink-dynamodb-dev)
```

### API Gateway 설정
```yaml
API Gateway:
  ID: 8wwdg03sr6
  Name: fablink-dev-api
  Type: REGIONAL
  Endpoint: https://8wwdg03sr6.execute-api.ap-northeast-2.amazonaws.com/
  Description: API Gateway for fablink-dev-api
  Stage: dev
  
Resources:
  - / (ANY method)
  - /{proxy+} (ANY method)
  
Logging:
  Access Logs: Enabled
  CloudWatch Log Group: /aws/apigateway/fablink-dev-api
  X-Ray Tracing: Enabled
  
Tags:
  Environment: dev
  Project: fablink
  Owner: devops
  ManagedBy: terraform
```

### Network Load Balancer
```yaml
Load Balancer:
  Name: fablink-dev-nlb
  DNS: fablink-dev-nlb-25ff572334e995e4.elb.ap-northeast-2.amazonaws.com
  Type: network
  Scheme: internet-facing
  Status: active
  
Network:
  VPC: vpc-021d5e5565bdbfc41
  Availability Zones:
    - ap-northeast-2a (subnet-0e2345ac1e61cab69)
    - ap-northeast-2b (subnet-0e2e05d8053b31d2f)

Target Group:
  Name: fablink-dev-nlb-eks-nodeport
  Protocol: TCP
  Port: 30080
  Health Check:
    Protocol: HTTP
    Path: /health
    Port: 30080
    Interval: 30s
    Timeout: 5s
    Healthy Threshold: 2
    Unhealthy Threshold: 2
```

## 🏗️ EKS 클러스터 설정

### 클러스터 정보
```yaml
Cluster:
  Name: fablink-cluster-dev
  Version: 1.30
  Platform: eks.41
  Status: ACTIVE
  Endpoint: https://743470B9ABE82C1195F8756A902F64AB.gr7.ap-northeast-2.eks.amazonaws.com

Network Configuration:
  VPC: vpc-021d5e5565bdbfc41
  Subnets:
    - subnet-04040c957cdae7e0d (Private)
    - subnet-0441ca8259a71550c (Private)
  Service CIDR: 172.20.0.0/16
  IP Family: ipv4

Security:
  Cluster Security Group: sg-07e908112779b5516
  Additional Security Groups: sg-059494f123e809462
  Public Access: Enabled
  Private Access: Disabled
  Authentication Mode: CONFIG_MAP
```

## 🗄️ 데이터베이스 연결

### Aurora PostgreSQL Cluster
```yaml
Cluster Information:
  Identifier: fablink-aurora-cluster
  Engine: aurora-postgresql
  Version: 15.10
  Status: available
  Multi-AZ: true
  Database Name: fablink

Endpoints:
  Writer: fablink-aurora-cluster.cluster-cr2c0e2q6qeb.ap-northeast-2.rds.amazonaws.com
  Reader: fablink-aurora-cluster.cluster-ro-cr2c0e2q6qeb.ap-northeast-2.rds.amazonaws.com
  Port: 5432
  Master Username: fablinkadmin

Instances:
  Primary: fablink-aurora-1 (Writer)
  Replica: fablink-aurora-2 (Reader)

Security & Backup:
  VPC Security Group: sg-0ddc7d288f4655acc
  Encryption: Enabled (KMS)
  KMS Key: arn:aws:kms:ap-northeast-2:853963783084:key/51a26103-957e-49f0-bc02-cf29757c58ad
  Backup Retention: 7 days
  Backup Window: 03:00-04:00 UTC
  Maintenance Window: sun:04:00-sun:05:00 UTC
  CloudWatch Logs: postgresql logs enabled
```

### DynamoDB Table
```yaml
Table Information:
  Name: fablink-dynamodb-dev
  Status: ACTIVE
  Partition Key: id (String)
  
Billing & Performance:
  Billing Mode: PAY_PER_REQUEST (On-Demand)
  Warm Throughput:
    Read Units: 12,000/sec
    Write Units: 4,000/sec
  
Security:
  Encryption: Enabled (SSE-KMS)
  KMS Key: arn:aws:kms:ap-northeast-2:853963783084:key/c454d1a1-59ef-40d9-ac8f-23d97d5d3c2d
  Deletion Protection: Disabled (Dev Environment)

Usage Patterns:
  - User sessions and temporary data
  - Cache data for API responses
  - AI request logs and analytics
  - Real-time notifications
```

## 🚨 현재 인프라 상태

### ✅ **구축 완료된 자원들**
- [x] **API Gateway**: `8wwdg03sr6` (fablink-dev-api) - 정상 동작
- [x] **NLB**: `fablink-dev-nlb` - 정상 동작
- [x] **EKS Cluster**: `fablink-cluster-dev` - 정상 동작
- [x] **Aurora DB**: `fablink-aurora-cluster` - 정상 동작
- [x] **DynamoDB**: `fablink-dynamodb-dev` - 정상 동작

### ❌ **해결해야 할 문제점들**

#### 1. **NLB Target Group 헬스체크 실패**
```yaml
문제: Target Group의 모든 타겟이 unhealthy 상태
원인: EKS NodePort 30080에서 응답하는 서비스가 없음
상태: 
  - Target 1 (i-0ee5f23c4566adcae:30080): unhealthy
  - Target 2 (i-090b42d2699727b0d:30080): unhealthy
해결 필요: Kubernetes에 백엔드 애플리케이션 배포
```

#### 2. **EKS에 백엔드 애플리케이션 미배포**
```yaml
문제: fablink-backend 애플리케이션이 EKS에 배포되지 않음
필요 작업:
  - ECR 리포지토리 생성
  - Docker 이미지 빌드 및 푸시
  - Kubernetes 매니페스트 작성 및 배포
  - NodePort 30080 서비스 생성
```

#### 3. **API Gateway → NLB 연결 미설정**
```yaml
문제: API Gateway에서 NLB로 라우팅하는 VPC Link 미설정
현재: API Gateway 리소스만 생성됨 (/{proxy+} ANY)
필요 작업: VPC Link 생성 및 Integration 설정
```

#### 4. **Django 헬스체크 엔드포인트 미구현**
```yaml
문제: /health 엔드포인트가 구현되지 않음
필요 작업: 
  - Django에서 /health, /ready 엔드포인트 구현
  - Aurora DB 연결 상태 체크
  - DynamoDB 연결 상태 체크
```

## 🔧 **해결 로드맵**

### **Phase 1: Kubernetes 매니페스트 완성**
- [ ] `namespace.yaml` - fablink-dev 네임스페이스
- [ ] `configmap.yaml` - 환경 설정 (DB 연결 정보 등)
- [ ] `secret.yaml` - 민감 정보 (DB 패스워드, AWS 키)
- [ ] `deployment.yaml` - Django 애플리케이션
- [ ] `service.yaml` - NodePort 30080 서비스
- [ ] `serviceaccount.yaml` - IAM 권한 설정

### **Phase 2: ECR 및 Docker 설정**
- [ ] ECR 리포지토리 생성
- [ ] Dockerfile 작성
- [ ] Docker 이미지 빌드 및 푸시
- [ ] 이미지 태그 관리 전략

### **Phase 3: Django 애플리케이션 준비**
- [ ] `/health` 엔드포인트 구현
- [ ] `/ready` 엔드포인트 구현
- [ ] Aurora DB 연결 설정
- [ ] DynamoDB 연결 설정
- [ ] 환경별 settings 파일 구성

### **Phase 4: API Gateway 연결**
- [ ] VPC Link 생성
- [ ] API Gateway Integration 설정
- [ ] 라우팅 규칙 설정
- [ ] CORS 설정

### **Phase 5: CI/CD 파이프라인**
- [ ] GitHub Actions 워크플로우
- [ ] 자동 빌드 및 배포
- [ ] 테스트 자동화
- [ ] 롤백 전략

## 🚀 배포 명령어

### 기본 배포 (준비 중)
```bash
# 개발 환경 배포 (Phase 1 완료 후)
kubectl apply -k kubernetes/environments/dev/

# 배포 상태 확인
kubectl get pods -n fablink-dev
kubectl describe deployment fablink-backend -n fablink-dev
```

### 헬스체크 테스트 (준비 중)
```bash
# NLB 헬스체크 테스트
curl -X GET http://fablink-dev-nlb-25ff572334e995e4.elb.ap-northeast-2.amazonaws.com/health/

# API Gateway 테스트 (VPC Link 설정 후)
curl -X GET https://8wwdg03sr6.execute-api.ap-northeast-2.amazonaws.com/health/
```

## 📈 성능 모니터링

### 메트릭 목표 (개발 환경)
```yaml
Performance Targets:
  - 응답 시간: 95% < 1s
  - 가용성: 95% (개발 환경)
  - 처리량: 100 RPS
  - 에러율: < 5%

Resource Utilization:
  - CPU: 평균 30-50%
  - 메모리: 평균 200-300MB
  - Aurora DB: 최대 10개 동시 연결
  - DynamoDB: On-demand scaling
```

## ⚠️ 개발 환경 주의사항

1. **비용 최적화**: 개발 환경이므로 최소 리소스로 구성
2. **데이터 보존**: 개발 데이터는 언제든 초기화될 수 있음
3. **Aurora DB**: Multi-AZ이지만 개발용 인스턴스 클래스 사용
4. **DynamoDB**: Pay-per-request 모드로 사용량에 따른 과금
5. **EKS 로깅**: 비용 절약을 위해 컨트롤 플레인 로그 비활성화
6. **보안**: 개발 환경이지만 실제 AWS 자원이므로 보안 주의

## 📞 다음 단계

현재 **Phase 1: Kubernetes 매니페스트 완성** 단계입니다.
다음 작업을 진행하시겠습니까?

1. **Kubernetes 매니페스트 파일 작성**
2. **ECR 리포지토리 생성 및 Docker 설정**
3. **Django 헬스체크 엔드포인트 구현**
4. **CI/CD 파이프라인 구성**
