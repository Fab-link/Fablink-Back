from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()

class AuthenticationTest(TestCase):
    def setUp(self):
        """테스트 데이터 설정"""
        self.client = APIClient()
        self.login_url = reverse('accounts:login')
        self.user_info_url = reverse('accounts:user_info')
        self.logout_url = reverse('accounts:logout')
        
        # 테스트용 사용자 생성
        self.user_data = {
            'user_id': 'testuser',
            'password': 'testpass123',
            'name': '테스트 사용자',
            'user_type': 'designer'
        }
        self.user = User.objects.create_user(**self.user_data)

    def test_login_success(self):
        """로그인 성공 테스트"""
        data = {
            'user_id': self.user_data['user_id'],
            'password': self.user_data['password']
        }
        response = self.client.post(self.login_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['message'], '로그인 성공')
        self.assertIn('tokens', response.data)
        self.assertIn('access', response.data['tokens'])
        self.assertIn('refresh', response.data['tokens'])
        self.assertIn('user', response.data)
        
        # 사용자 정보 확인
        user_data = response.data['user']
        self.assertEqual(user_data['user_id'], self.user_data['user_id'])
        self.assertEqual(user_data['name'], self.user_data['name'])
        self.assertEqual(user_data['user_type'], self.user_data['user_type'])

    def test_login_wrong_password(self):
        """잘못된 비밀번호로 로그인 시도"""
        data = {
            'user_id': self.user_data['user_id'],
            'password': 'wrongpassword'
        }
        response = self.client.post(self.login_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertIn('errors', response.data)

    def test_login_invalid_user(self):
        """존재하지 않는 사용자로 로그인 시도"""
        data = {
            'user_id': 'nonexistentuser',
            'password': 'testpass123'
        }
        response = self.client.post(self.login_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertIn('errors', response.data)

    def test_user_info_with_token(self):
        """토큰을 사용한 사용자 정보 조회"""
        # 먼저 로그인
        login_data = {
            'user_id': self.user_data['user_id'],
            'password': self.user_data['password']
        }
        login_response = self.client.post(self.login_url, login_data)
        token = login_response.data['tokens']['access']
        
        # 토큰으로 사용자 정보 조회
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get(self.user_info_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['user']['user_id'], self.user_data['user_id'])

    def test_user_info_without_token(self):
        """토큰 없이 사용자 정보 조회 시도"""
        response = self.client.get(self.user_info_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout(self):
        """로그아웃 테스트"""
        # 먼저 로그인
        login_data = {
            'user_id': self.user_data['user_id'],
            'password': self.user_data['password']
        }
        login_response = self.client.post(self.login_url, login_data)
        token = login_response.data['tokens']['access']
        refresh_token = login_response.data['tokens']['refresh']
        
        # 토큰으로 로그아웃
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.post(self.logout_url, {'refresh': refresh_token})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['message'], '로그아웃 성공')
        
        # 로그아웃 후 토큰 제거
        self.client.credentials()
        
        # 토큰 없이 사용자 정보 조회 시도
        info_response = self.client.get(self.user_info_url)
        self.assertEqual(info_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_wrong_user_type(self):
        """잘못된 사용자 타입으로 로그인 시도"""
        data = {
            'user_id': self.user_data['user_id'],
            'password': self.user_data['password'],
            'user_type': 'manufacturer'  # 실제는 designer
        }
        response = self.client.post(self.login_url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])
        self.assertIn('errors', response.data)
