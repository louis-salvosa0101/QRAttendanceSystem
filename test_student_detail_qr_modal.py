"""
Tests for Student Detail QR viewer modal (Issue #4)
"""
import os
import base64
import unittest
from unittest.mock import patch, MagicMock

# Set required test environment variables before importing app/config
os.environ['SECRET_KEY'] = 'test-secret-key-1234567890'
os.environ['AES_KEY'] = base64.b64encode(b'01234567890123456789012345678901').decode('utf-8')
os.environ['AES_IV'] = base64.b64encode(b'0123456789012345').decode('utf-8')
os.environ['DATABASE_URL'] = 'postgresql://dummy:dummy@localhost:5432/dummy'

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


class TestStudentDetailQrModal(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    def _login(self):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = '1'
            sess['_fresh'] = True

    def _mock_officer(self):
        return Officer(
            id=1, username='admin', name='Admin',
            created_at='2026-01-01', is_admin=True,
        )

    @patch('app.get_db')
    @patch('app.get_attendance_records', return_value=[])
    @patch('app.get_student', return_value=_FAKE_STUDENT)
    @patch('flask_login.utils._get_user')
    def test_student_detail_qr_modal_elements(
        self, mock_get_user, mock_get_student, mock_get_records, mock_get_db
    ):
        """Student Detail page renders QR button, modal, caption, download button, error state, and close handlers."""
        mock_get_user.return_value = self._mock_officer()
        self._login()

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur
        mock_cur.fetchall.return_value = []
        mock_cur.fetchone.return_value = {'total': 0, 'c': 0}

        response = self.client.get('/students/2023-00001')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        # 1. QR button in profile-actions
        self.assertIn('id="btn-view-qr"', html)
        self.assertIn('openQrModal()', html)

        # 2. QR modal overlay & body
        self.assertIn('id="qrModal"', html)
        self.assertIn('id="qrModalImg"', html)

        # 3. Caption with name and student number
        self.assertIn('Juan Dela Cruz', html)
        self.assertIn('2023-00001', html)

        # 4. Download button with exact download filename attribute
        self.assertIn('id="qrModalDownloadBtn"', html)
        self.assertIn('download="QR_2023-00001.png"', html)
        self.assertIn('/api/students/2023-00001/qr', html)

        # 5. Close/dismiss controls
        self.assertIn('closeQrModal()', html)

        # 6. Inline error message container
        self.assertIn('id="qrModalError"', html)
        self.assertIn('onQrModalImageError()', html)


if __name__ == '__main__':
    unittest.main()
