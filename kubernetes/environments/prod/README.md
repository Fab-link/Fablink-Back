# 운영 환경 (Production) 설정

FabLink Backend 운영 환경의 Kubernetes 배포 설정입니다.

> ⚠️ **주의**: 현재 운영 환경 인프라는 구축되지 않았습니다. 이 문서는 향후 구축 예정인 운영 환경의 설계 문서입니다.

## 🎯 환경 개요 (예정)

| 항목 | 값 |
|------|-----|
| **AWS 계정** | `853963783084` |
| **네임스페이스** | `fablink-prod` |
| **도메인** | `api.fablink.com` |
| **클러스터** | `fablink-cluster-prod` |
| **리전** | `ap-northeast-2` |
| **환경 타입** | Production |

## 🌐 네트워크 아키텍처 (설계)

### 트래픽 흐름
```
Client Request
    ↓
API Gateway (fablink-prod-api)
    ↓ VPC Link
Network Load Balancer (fablink-prod-nlb)
    ↓ Target Group (Multi-AZ)
EKS Service (ClusterIP)
    ↓ Pod Network (Multi-AZ)
Pod (fablink-backend) x3+ replicas
    ↓ Database Connections
Aurora DB (Multi-AZ) / DynamoDB (Global Tables)
```

### API Gateway 설정 (예정)
```yaml
API Gateway:
  Name: fablink-prod-api
  Type: REGIONAL
  Custom Domain: api.fablink.com
  SSL Certificate: AWS Certificate Manager
  
Features:
  - API Key 인증
  - Rate Limiting (1000 req/min)
  - Request/Response 로깅
  - WAF 통합
```

### Network Load Balancer (예정)
```yaml
Load Balancer:
  Name: fablink-prod-nlb
  Type: network
  Scheme: internet-facing
  Cross-Zone Load Balancing: Enabled
  
Network:
  VPC: fablink-prod-vpc
  Availability Zones: 3개 (2a, 2b, 2d)
  Target Groups: Health check enabled
```

## 🏗️ EKS 클러스터 설정 (예정)

### 클러스터 정보
```yaml
Cluster:
  Name: fablink-cluster-prod
  Version: 1.30+
  Node Groups: 3개 (각 AZ별)
  Instance Types: m5.large, m5.xlarge
  
Network Configuration:
  VPC: fablink-prod-vpc (별도 VPC)
  Private Subnets: 3개
  Public Subnets: 3개 (NAT Gateway용)
  Service CIDR: 172.20.0.0/16

Security:
  Private API Endpoint: Enabled
  Public Access: Restricted (관리자 IP만)
  Pod Security Standards: Restricted
  Network Policies: Enabled
```

## 🔧 리소스 설정 (운영 환경)

### Pod 리소스
```yaml
resources:
  requests:
    memory: "1Gi"
    cpu: "500m"
  limits:
    memory: "2Gi" 
    cpu: "1000m"
```

### 레플리카 설정
- **최소 레플리카**: 3개 (고가용성)
- **최대 레플리카**: 20개
- **HPA 타겟 CPU**: 60%
- **HPA 타겟 메모리**: 70%
- **PDB**: 최소 2개 Pod 유지

## 🗄️ 데이터베이스 연결 (예정)

### Aurora PostgreSQL Cluster (운영)
```yaml
Cluster Configuration:
  Engine: aurora-postgresql
  Version: 15.x (latest stable)
  Multi-AZ: true
  Instance Class: db.r6g.large (최소)
  
High Availability:
  Writer: 1개 (Primary)
  Readers: 2개 (Multi-AZ)
  Auto Failover: Enabled
  Backup Retention: 30 days
  
Security:
  Encryption at Rest: Enabled
  Encryption in Transit: Required
  VPC Security Groups: Restricted
  IAM Database Authentication: Enabled
  
Performance:
  Performance Insights: Enabled
  Enhanced Monitoring: Enabled
  Slow Query Logging: Enabled
```

### DynamoDB Tables (운영)
```yaml
Table Configuration:
  Billing Mode: ON_DEMAND
  Point-in-time Recovery: Enabled
  Deletion Protection: Enabled
  
Tables:
  - fablink-prod-sessions
  - fablink-prod-user-activities  
  - fablink-prod-cache
  - fablink-prod-ai-requests
  - fablink-prod-notifications
  - fablink-prod-analytics

Security:
  Encryption: Customer Managed KMS
  VPC Endpoints: Enabled
  Access Control: IAM + Resource Policies

Performance:
  Global Secondary Indexes: As needed
  DynamoDB Accelerator (DAX): Consider for cache tables
  Auto Scaling: Enabled (if provisioned mode)
```

## 📊 모니터링 & 로깅 (운영 환경)

### 헬스체크 & 프로브
```yaml
Probes:
  Liveness: /health/
  Readiness: /ready/
  Startup: /startup/ (초기 구동 시간 고려)
  
Configuration:
  Initial Delay: 60s
  Period: 15s
  Timeout: 5s
  Failure Threshold: 2
```

### 로깅 & 모니터링
```yaml
Logging:
  Level: INFO (운영 환경)
  Format: JSON (구조화된 로깅)
  Retention: 90 days
  
EKS Cluster Logging:
  Control Plane Logs: All types enabled
  Audit Logs: Enabled
  
Monitoring Stack:
  - CloudWatch Container Insights
  - Prometheus + Grafana (선택)
  - AWS X-Ray (분산 추적)
  - Custom Dashboards
```

### 알림 설정
```yaml
CloudWatch Alarms:
  - CPU > 80% (5분 지속)
  - Memory > 85% (5분 지속)
  - Response Time > 2s (3분 지속)
  - Error Rate > 1% (2분 지속)
  - Pod Restart > 3회 (10분 내)
  - Database Connection Failures
  - DynamoDB Throttling

Notification Channels:
  - SNS → Slack
  - PagerDuty (Critical alerts)
  - Email (Non-critical)
```

## 🔐 보안 설정 (운영 환경)

### 네트워크 보안
```yaml
Network Policies:
  - Namespace isolation
  - Ingress/Egress rules
  - Database access restrictions
  
VPC Security:
  - Private subnets for EKS nodes
  - NAT Gateway for outbound traffic
  - VPC Flow Logs enabled
  - AWS WAF on API Gateway
```

### 인증 & 권한
```yaml
RBAC:
  - Service Account per application
  - Least privilege principle
  - Pod Security Standards

AWS IAM:
  - IRSA (IAM Roles for Service Accounts)
  - Cross-account access (if needed)
  - Regular access review
```

## 🚀 배포 전략 (운영 환경)

### Blue-Green 배포
```yaml
Strategy:
  Type: Blue-Green
  Traffic Shifting: Gradual (10% → 50% → 100%)
  Rollback: Automatic on failure
  
Validation:
  - Health checks
  - Integration tests
  - Performance benchmarks
  - Manual approval gate
```

### 배포 파이프라인
```yaml
Stages:
  1. Security Scan
  2. Unit Tests
  3. Integration Tests
  4. Staging Deployment
  5. Production Approval
  6. Production Deployment
  7. Post-deployment Verification
  8. Monitoring & Alerting
```

## 📈 성능 목표 (운영 환경)

### SLA 목표
```yaml
Availability: 99.9% (월 43분 다운타임)
Response Time: 
  - 95th percentile < 500ms
  - 99th percentile < 1s
Throughput: 5,000 RPS (peak)
Error Rate: < 0.1%
```

### 용량 계획
```yaml
Expected Load:
  - Daily Active Users: 10,000+
  - Peak RPS: 5,000
  - Database Connections: 100+
  - Storage Growth: 10GB/month
```

## ⚠️ 운영 환경 구축 시 고려사항

1. **인프라 구축 순서**:
   - VPC 및 네트워크 설정
   - EKS 클러스터 구축
   - Aurora DB 클러스터 생성
   - DynamoDB 테이블 생성
   - API Gateway 및 NLB 설정

2. **보안 검토**:
   - 네트워크 보안 그룹
   - IAM 권한 최소화
   - 암호화 설정
   - 감사 로깅

3. **성능 테스트**:
   - 부하 테스트
   - 장애 복구 테스트
   - 백업/복원 테스트

4. **운영 준비**:
   - 모니터링 대시보드
   - 알림 설정
   - 장애 대응 절차
   - 백업 전략

5. **비용 최적화**:
   - Reserved Instances
   - Spot Instances (적절한 워크로드)
   - 리소스 사용량 모니터링
