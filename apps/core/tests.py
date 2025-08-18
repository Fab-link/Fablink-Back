"""
Core app tests for CI/CD pipeline
"""
from django.test import TestCase, Client
from django.urls import reverse
import json


class HealthCheckTests(TestCase):
    """헬스체크 엔드포인트 테스트"""
    
    def setUp(self):
        self.client = Client()
    
    def test_health_endpoint(self):
        """Health 엔드포인트 테스트"""
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'healthy')
        self.assertEqual(data['service'], 'fablink-backend')
    
    def test_ready_endpoint(self):
        """Ready 엔드포인트 테스트"""
        response = self.client.get('/ready/')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'ready')
        self.assertIn('checks', data)
        self.assertIn('database', data['checks'])
    
    def test_api_root(self):
        """API 루트 엔드포인트 테스트"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['message'], 'FabLink API Server')
        self.assertEqual(data['version'], '1.0.0')
        self.assertIn('documentation', data)


class APIDocumentationTests(TestCase):
    """API 문서화 엔드포인트 테스트"""
    
    def setUp(self):
        self.client = Client()
    
    def test_swagger_ui(self):
        """Swagger UI 접근 테스트"""
        response = self.client.get('/api/docs/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'FabLink API')
    
    def test_redoc(self):
        """ReDoc 접근 테스트"""
        response = self.client.get('/api/redoc/')
        self.assertEqual(response.status_code, 200)
    
    def test_openapi_schema(self):
        """OpenAPI 스키마 테스트"""
        response = self.client.get('/api/schema/')
        self.assertEqual(response.status_code, 200)
        
        # JSON 형식 확인
        data = json.loads(response.content)
        self.assertIn('openapi', data)
        self.assertIn('info', data)
        self.assertEqual(data['info']['title'], 'FabLink API')
