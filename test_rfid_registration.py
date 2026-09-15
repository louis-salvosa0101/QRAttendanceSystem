"""
Tests for RFID Registration (Issue 7)

Seams under test:
1. POST /api/students/register-rfid
   - Unauthenticated request -> 401 JSON
   - Missing fields / invalid student -> 400 / 404 JSON
   - Register new RFID UID -> 200 JSON
   - Register when RFID UID exists on student without confirm -> 409 JSON with existing UID
   - Register when RFID UID exists on student with confirm=True -> 200 JSON (overwrite)
2. DELETE /api/students/<student_number>/rfid
   - Unauthenticated request -> 401 JSON
   - Student has no RFID UID / Student not found -> 404 JSON
   - Unlink RFID UID -> 200 JSON
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
    'rfid_uid': None,
}

_FAKE_STUDENT_WITH_RFID = {
    'student_number': '2023-00001',
    'name': 'Juan Dela Cruz',
    'course': 'BSCS',
    'year': '3',
    'section': 'A',
    'rfid_uid': 'CARD-12345',
}


class TestRfidRegistration(unittest.TestCase):

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

    # -- 1. Unauthenticated requests return 401 -----------------------------

    def test_register_rfid_unauthenticated_returns_401(self):
        """POST /api/students/register-rfid without auth returns 401 JSON."""
        response = self.client.post('/api/students/register-rfid', json={
            'student_number': '2023-00001',
            'rfid_uid': 'CARD-12345',
        })
        self.assertEqual(response.status_code, 401)
        data = response.get_json()
        self.assertFalse(data['success'])

    def test_unlink_rfid_unauthenticated_returns_401(self):
        """DELETE /api/students/<student_number>/rfid without auth returns 401 JSON."""
        response = self.client.delete('/api/students/2023-00001/rfid')
        self.assertEqual(response.status_code, 401)
        data = response.get_json()
        self.assertFalse(data['success'])

    # -- 2. POST /api/students/register-rfid --------------------------------

    @patch('flask_login.utils._get_user')
    def test_register_rfid_missing_params_returns_400(self, mock_get_user):
        """Missing student_number or rfid_uid returns 400."""
        mock_get_user.return_value = self._mock_officer()
        self._login()

        response = self.client.post('/api/students/register-rfid', json={
            'student_number': '2023-00001',
        })
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data['success'])

    @patch('app.get_student', return_value=None)
    @patch('flask_login.utils._get_user')
    def test_register_rfid_student_not_found_returns_404(self, mock_get_user, mock_get_student):
        """Student not found returns 404."""
        mock_get_user.return_value = self._mock_officer()
        self._login()

        response = self.client.post('/api/students/register-rfid', json={
            'student_number': 'UNKNOWN',
            'rfid_uid': 'CARD-12345',
        })
        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertFalse(data['success'])

    @patch('app.register_rfid_uid')
    @patch('app.get_student', return_value=_FAKE_STUDENT)
    @patch('flask_login.utils._get_user')
    def test_register_rfid_success(self, mock_get_user, mock_get_student, mock_register_rfid):
        """Registering RFID UID on student without existing UID succeeds with 200."""
        mock_get_user.return_value = self._mock_officer()
        self._login()
        mock_register_rfid.return_value = (True, 200, {
            'success': True,
            'message': 'RFID UID linked successfully.',
            'student': _FAKE_STUDENT_WITH_RFID,
        })

        response = self.client.post('/api/students/register-rfid', json={
            'student_number': '2023-00001',
            'rfid_uid': 'CARD-12345',
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['student']['rfid_uid'], 'CARD-12345')

    @patch('app.register_rfid_uid')
    @patch('app.get_student', return_value=_FAKE_STUDENT_WITH_RFID)
    @patch('flask_login.utils._get_user')
    def test_register_rfid_existing_without_confirm_returns_409(self, mock_get_user, mock_get_student, mock_register_rfid):
        """Registering when student already has UID without confirm returns 409 with existing UID."""
        mock_get_user.return_value = self._mock_officer()
        self._login()
        mock_register_rfid.return_value = (False, 409, {
            'success': False,
            'message': 'Student already has an RFID UID registered.',
            'existing_rfid_uid': 'CARD-12345',
        })

        response = self.client.post('/api/students/register-rfid', json={
            'student_number': '2023-00001',
            'rfid_uid': 'CARD-99999',
        })
        self.assertEqual(response.status_code, 409)
        data = response.get_json()
        self.assertFalse(data['success'])
        self.assertEqual(data['existing_rfid_uid'], 'CARD-12345')

    @patch('app.register_rfid_uid')
    @patch('app.get_student', return_value=_FAKE_STUDENT_WITH_RFID)
    @patch('flask_login.utils._get_user')
    def test_register_rfid_existing_with_confirm_overwrites(self, mock_get_user, mock_get_student, mock_register_rfid):
        """Registering when student already has UID with confirm: true overwrites with 200."""
        mock_get_user.return_value = self._mock_officer()
        self._login()
        mock_register_rfid.return_value = (True, 200, {
            'success': True,
            'message': 'RFID UID updated successfully.',
            'student': {**_FAKE_STUDENT, 'rfid_uid': 'CARD-99999'},
        })

        response = self.client.post('/api/students/register-rfid', json={
            'student_number': '2023-00001',
            'rfid_uid': 'CARD-99999',
            'confirm': True,
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['student']['rfid_uid'], 'CARD-99999')

    # -- 3. DELETE /api/students/<student_number>/rfid -----------------------

    @patch('app.unlink_rfid_uid')
    @patch('flask_login.utils._get_user')
    def test_unlink_rfid_no_uid_returns_404(self, mock_get_user, mock_unlink_rfid):
        """Unlinking when student has no RFID UID returns 404."""
        mock_get_user.return_value = self._mock_officer()
        self._login()
        mock_unlink_rfid.return_value = (False, 404, {
            'success': False,
            'message': 'No RFID UID registered for this student.',
        })

        response = self.client.delete('/api/students/2023-00001/rfid')
        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertFalse(data['success'])

    @patch('app.unlink_rfid_uid')
    @patch('flask_login.utils._get_user')
    def test_unlink_rfid_success(self, mock_get_user, mock_unlink_rfid):
        """Unlinking RFID UID from student returns 200."""
        mock_get_user.return_value = self._mock_officer()
        self._login()
        mock_unlink_rfid.return_value = (True, 200, {
            'success': True,
            'message': 'RFID UID unlinked successfully.',
        })

        response = self.client.delete('/api/students/2023-00001/rfid')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])


if __name__ == '__main__':
    unittest.main()
