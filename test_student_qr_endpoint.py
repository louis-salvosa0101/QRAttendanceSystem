"""
Tests for GET /api/students/<student_number>/qr

Seams under test:
1. Unauthenticated request -> 401 JSON
2. Student not found in registry -> 404 JSON
3. QR PNG already cached on disk -> served without calling generate_single_qr
4. QR PNG absent -> generate_single_qr is called, then PNG is served
"""
import os
import base64
import unittest
from unittest.mock import patch, MagicMock
from flask import Response

# Set required test environment variables before importing app/config
os.environ['SECRET_KEY'] = 'test-secret-key-1234567890'
os.environ['AES_KEY'] = base64.b64encode(b'01234567890123456789012345678901').decode('utf-8')
os.environ['AES_IV'] = base64.b64encode(b'0123456789012345').decode('utf-8')
os.environ['DATABASE_URL'] = 'postgresql://dummy:dummy@localhost:5432/dummy'

# Patch DB init before app loads
with patch('db.init_db'), patch('auth.seed_default_admin'), patch('db.get_db'):
    from app import app
from auth import Officer


_FAKE_STUDENT = {
    'student_number': '2023-00001',
    'name': 'Juan Dela Cruz',
    'course': 'BSCS',
    'year': '3',
    'section': 'A',
}

_FAKE_PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 16  # minimal fake PNG bytes


class TestStudentQrEndpoint(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    def _login(self):
        """Helper: inject a session as an authenticated officer."""
        with self.client.session_transaction() as sess:
            sess['_user_id'] = '1'
            sess['_fresh'] = True

    def _mock_officer(self):
        """Return a mock Officer for flask_login."""
        return Officer(
            id=1, username='admin', name='Admin',
            created_at='2026-01-01', is_admin=True,
        )

    # -- Seam 1: unauthenticated --------------------------------------------

    def test_unauthenticated_returns_401(self):
        """Unauthenticated request to the QR endpoint returns 401 JSON."""
        response = self.client.get('/api/students/2023-00001/qr')
        self.assertEqual(response.status_code, 401)
        data = response.get_json()
        self.assertFalse(data['success'])

    # -- Seam 2: student not found ------------------------------------------

    @patch('app.get_student', return_value={})
    @patch('flask_login.utils._get_user')
    def test_unknown_student_returns_404(self, mock_get_user, mock_get_student):
        """Unknown student number returns 404 with JSON body."""
        mock_get_user.return_value = self._mock_officer()
        self._login()

        response = self.client.get('/api/students/UNKNOWN-999/qr')

        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertFalse(data['success'])
        mock_get_student.assert_called_once_with('UNKNOWN-999')

    # -- Seam 3: QR cached on disk ------------------------------------------

    @patch('app.send_file', return_value=Response(_FAKE_PNG, mimetype='image/png'))
    @patch('app.os.path.exists', return_value=True)
    @patch('app.generate_single_qr')
    @patch('app.get_student', return_value=_FAKE_STUDENT)
    @patch('flask_login.utils._get_user')
    def test_cached_qr_served_without_regenerating(
        self, mock_get_user, mock_get_student,
        mock_generate, mock_exists, mock_send_file,
    ):
        """When the QR PNG already exists on disk it is served without regenerating."""
        mock_get_user.return_value = self._mock_officer()
        self._login()

        response = self.client.get('/api/students/2023-00001/qr')

        self.assertEqual(response.status_code, 200)
        self.assertIn('image/png', response.content_type)
        mock_generate.assert_not_called()
        mock_send_file.assert_called_once()

    # -- Seam 4: QR absent -> generate then serve ---------------------------

    @patch('app.send_file', return_value=Response(_FAKE_PNG, mimetype='image/png'))
    @patch('app.os.path.exists', return_value=False)
    @patch('app.generate_single_qr')
    @patch('app.get_student', return_value=_FAKE_STUDENT)
    @patch('flask_login.utils._get_user')
    def test_missing_qr_is_generated_then_served(
        self, mock_get_user, mock_get_student,
        mock_generate, mock_exists, mock_send_file,
    ):
        """When the QR PNG is absent, generate_single_qr is called before serving."""
        mock_get_user.return_value = self._mock_officer()
        self._login()

        response = self.client.get('/api/students/2023-00001/qr')

        self.assertEqual(response.status_code, 200)
        self.assertIn('image/png', response.content_type)
        mock_generate.assert_called_once_with(_FAKE_STUDENT)
        mock_send_file.assert_called_once()


if __name__ == '__main__':
    unittest.main()
