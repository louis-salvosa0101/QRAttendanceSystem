import os
import base64
import unittest
from unittest.mock import patch, MagicMock

# Set required test environment variables before importing app/config
os.environ['SECRET_KEY'] = 'test-secret-key-1234567890'
os.environ['AES_KEY'] = base64.b64encode(b'01234567890123456789012345678901').decode('utf-8')
os.environ['AES_IV'] = base64.b64encode(b'0123456789012345').decode('utf-8')
os.environ['DATABASE_URL'] = 'postgresql://dummy:dummy@localhost:5432/dummy'

# Patch DB init before app loads
with patch('db.init_db'), patch('auth.seed_default_admin'), patch('db.get_db'):
    from app import app
from auth import Officer


class TestClearAllFinesEndpoint(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    def test_clear_all_fines_unauthorized(self):
        """Unauthenticated requests must be rejected with 401."""
        response = self.client.delete('/api/students/fines/clear-all')
        self.assertEqual(response.status_code, 401)
        data = response.get_json()
        self.assertFalse(data['success'])

    @patch('app.get_db')
    @patch('flask_login.utils._get_user')
    def test_clear_all_fines_authenticated_success(self, mock_get_user, mock_get_db):
        """Authenticated officer can clear all fines across all tables atomically."""
        mock_user = Officer(id=1, username='admin', name='Admin User', created_at='2026-01-01', is_admin=True)
        mock_get_user.return_value = mock_user

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cur

        mock_cur.rowcount = 5

        # Perform request with simulated authenticated session
        with self.client.session_transaction() as sess:
            sess['_user_id'] = '1'
            sess['_fresh'] = True

        response = self.client.delete('/api/students/fines/clear-all')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertIn('cleared', data['message'].lower())

        # Verify that all 4 statements were executed
        sql_calls = [call[0][0] for call in mock_cur.execute.call_args_list]
        self.assertTrue(any("attendance_records" in sql and "fine = 0" in sql for sql in sql_calls))
        self.assertTrue(any("session_scans" in sql and "fine = 0" in sql for sql in sql_calls))
        self.assertTrue(any("DELETE FROM manual_fines" in sql for sql in sql_calls))
        self.assertTrue(any("DELETE FROM fine_payments" in sql for sql in sql_calls))

    @patch('app.get_all_students')
    @patch('app.get_registry_stats')
    @patch('flask_login.utils._get_user')
    def test_students_page_renders_clear_all_fines_button(self, mock_get_user, mock_stats, mock_students):
        """The /students template contains the Clear All Fines button and danger zone."""
        mock_user = Officer(id=1, username='admin', name='Admin User', created_at='2026-01-01', is_admin=True)
        mock_get_user.return_value = mock_user
        mock_stats.return_value = {'total': 0, 'by_course': {}}
        mock_students.return_value = []

        with self.client.session_transaction() as sess:
            sess['_user_id'] = '1'
            sess['_fresh'] = True

        response = self.client.get('/students')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('id="btn-clear-all-fines"', html)
        self.assertIn('Clear All Fines', html)
        self.assertIn('clearAllFines()', html)


if __name__ == '__main__':
    unittest.main()
