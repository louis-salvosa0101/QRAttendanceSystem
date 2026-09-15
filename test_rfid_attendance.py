"""
Tests for RFID Attendance Scan (Issue 8)

Seams under test:
1. POST /api/scan/rfid
   - Unauthenticated request -> 401 JSON
   - Missing session_id or rfid_uid -> error JSON
   - Unregistered RFID UID -> error JSON ("Card not recognized. Please register your RFID card with an officer.")
   - Session not active / expired -> error JSON
   - Student fails session filter -> error JSON
   - Valid UID first scan -> Time In
   - Valid UID second scan -> Time Out
2. Mixed Scan Methods
   - First scan via QR (Time In), second scan via RFID (Time Out)
   - First scan via RFID (Time In), second scan via QR (Time Out)
3. Scan Records
   - POST /api/scan records scan_method: 'qr'
   - POST /api/scan/rfid records scan_method: 'rfid'
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
    'rfid_uid': 'CARD-12345',
}

_FAKE_SESSION_ACTIVE = {
    'session_id': 'SESS001',
    'subject': 'CS101',
    'is_active': 1,
    'expires_at': '2099-01-01T00:00:00',
    'created_at': '2026-01-01T00:00:00',
    'required_course': '',
    'required_year': [],
    'required_section': '',
}

_FAKE_SESSION_FILTERED = {
    'session_id': 'SESS002',
    'subject': 'CS101',
    'is_active': 1,
    'expires_at': '2099-01-01T00:00:00',
    'created_at': '2026-01-01T00:00:00',
    'required_course': 'BSIT',  # Student is BSCS -> should fail
    'required_year': [],
    'required_section': '',
}

_FAKE_SESSION_CLOSED = {
    'session_id': 'SESS003',
    'subject': 'CS101',
    'is_active': 0,
    'expires_at': '2099-01-01T00:00:00',
    'created_at': '2026-01-01T00:00:00',
    'required_course': '',
    'required_year': [],
    'required_section': '',
}


class TestRfidAttendance(unittest.TestCase):

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

    def test_scan_rfid_unauthenticated_returns_401(self):
        """POST /api/scan/rfid without auth returns 401 JSON."""
        response = self.client.post('/api/scan/rfid', json={
            'session_id': 'SESS001',
            'rfid_uid': 'CARD-12345',
        })
        self.assertEqual(response.status_code, 401)
        data = response.get_json()
        self.assertFalse(data['success'])

    # -- 2. Missing fields ---------------------------------------------------

    @patch('flask_login.utils._get_user')
    def test_scan_rfid_missing_session_id_returns_error(self, mock_get_user):
        """Missing session_id returns error JSON."""
        mock_get_user.return_value = self._mock_officer()
        self._login()

        response = self.client.post('/api/scan/rfid', json={
            'rfid_uid': 'CARD-12345',
        })
        data = response.get_json()
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'no_session')

    @patch('flask_login.utils._get_user')
    def test_scan_rfid_missing_uid_returns_error(self, mock_get_user):
        """Missing rfid_uid returns error JSON."""
        mock_get_user.return_value = self._mock_officer()
        self._login()

        response = self.client.post('/api/scan/rfid', json={
            'session_id': 'SESS001',
        })
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data['success'])

    # -- 3. Unregistered RFID UID -------------------------------------------

    @patch('app.get_student_by_rfid', return_value=None)
    @patch('app.get_session_row', return_value=_FAKE_SESSION_ACTIVE)
    @patch('app.get_db')
    @patch('flask_login.utils._get_user')
    def test_scan_rfid_unregistered_uid_returns_error_message(self, mock_get_user, mock_get_db, mock_get_session, mock_get_student):
        """Tapping unregistered RFID UID returns error JSON with clear message."""
        mock_get_user.return_value = self._mock_officer()
        self._login()

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_get_db.return_value.__enter__.return_value = mock_conn

        response = self.client.post('/api/scan/rfid', json={
            'session_id': 'SESS001',
            'rfid_uid': 'UNKNOWN-CARD',
        })
        data = response.get_json()
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'unregistered_rfid')
        self.assertEqual(data['message'], 'Card not recognized. Please register your RFID card with an officer.')

    # -- 4. Session inactive / closed ----------------------------------------

    @patch('app.get_session_row', return_value=_FAKE_SESSION_CLOSED)
    @patch('app.get_db')
    @patch('flask_login.utils._get_user')
    def test_scan_rfid_session_inactive_returns_error(self, mock_get_user, mock_get_db, mock_get_session):
        """Inactive session returns error JSON."""
        mock_get_user.return_value = self._mock_officer()
        self._login()

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = _FAKE_STUDENT
        mock_conn.cursor.return_value = mock_cur
        mock_get_db.return_value.__enter__.return_value = mock_conn

        response = self.client.post('/api/scan/rfid', json={
            'session_id': 'SESS003',
            'rfid_uid': 'CARD-12345',
        })
        data = response.get_json()
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'invalid_session')

    # -- 5. Session filter failure ------------------------------------------

    @patch('app.get_session_row', return_value=_FAKE_SESSION_FILTERED)
    @patch('app.get_db')
    @patch('flask_login.utils._get_user')
    def test_scan_rfid_student_fails_session_filter(self, mock_get_user, mock_get_db, mock_get_session):
        """Student failing course filter returns error JSON."""
        mock_get_user.return_value = self._mock_officer()
        self._login()

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = _FAKE_STUDENT
        mock_conn.cursor.return_value = mock_cur
        mock_get_db.return_value.__enter__.return_value = mock_conn

        response = self.client.post('/api/scan/rfid', json={
            'session_id': 'SESS002',
            'rfid_uid': 'CARD-12345',
        })
        data = response.get_json()
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'not_included')

    # -- 6. Successful scans ------------------------------------------------

    @patch('app.log_attendance', return_value=True)
    @patch('app.process_scan', return_value=(True, 'Time In recorded.', 'time_in', 0, '', 1, None))
    @patch('app.get_session_row', return_value=_FAKE_SESSION_ACTIVE)
    @patch('app.get_db')
    @patch('flask_login.utils._get_user')
    def test_scan_rfid_first_scan_records_time_in(
        self, mock_get_user, mock_get_db, mock_get_session, mock_process_scan, mock_log_attendance
    ):
        """First valid RFID scan records Time In with scan_method 'rfid'."""
        mock_get_user.return_value = self._mock_officer()
        self._login()

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = _FAKE_STUDENT
        mock_conn.cursor.return_value = mock_cur
        mock_get_db.return_value.__enter__.return_value = mock_conn

        response = self.client.post('/api/scan/rfid', json={
            'session_id': 'SESS001',
            'rfid_uid': 'CARD-12345',
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['scan_type'], 'time_in')
        self.assertEqual(data['status'], 'Time In')
        self.assertEqual(data['scan_method'], 'rfid')
        mock_process_scan.assert_called_once_with(mock_conn, 'SESS001', '2023-00001', scan_method='rfid')
        mock_log_attendance.assert_called_once_with(
            _FAKE_STUDENT, 'SESS001', status='Time In', fine=0, fine_reason='', conn=mock_conn, scan_method='rfid'
        )

    @patch('app.log_attendance', return_value=True)
    @patch('app.process_scan', return_value=(True, 'Time Out recorded.', 'time_out', 0, '', 1, None))
    @patch('app.get_session_row', return_value=_FAKE_SESSION_ACTIVE)
    @patch('app.get_db')
    @patch('flask_login.utils._get_user')
    def test_scan_rfid_second_scan_records_time_out(
        self, mock_get_user, mock_get_db, mock_get_session, mock_process_scan, mock_log_attendance
    ):
        """Second valid RFID scan records Time Out with scan_method 'rfid'."""
        mock_get_user.return_value = self._mock_officer()
        self._login()

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = _FAKE_STUDENT
        mock_conn.cursor.return_value = mock_cur
        mock_get_db.return_value.__enter__.return_value = mock_conn

        response = self.client.post('/api/scan/rfid', json={
            'session_id': 'SESS001',
            'rfid_uid': 'CARD-12345',
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['scan_type'], 'time_out')
        self.assertEqual(data['status'], 'Time Out')
        self.assertEqual(data['scan_method'], 'rfid')
        mock_process_scan.assert_called_once_with(mock_conn, 'SESS001', '2023-00001', scan_method='rfid')
        mock_log_attendance.assert_called_once_with(
            _FAKE_STUDENT, 'SESS001', status='Time Out', fine=0, fine_reason='', conn=mock_conn, scan_method='rfid'
        )


    # -- 7. QR Scan records scan_method 'qr' --------------------------------

    @patch('app.log_attendance', return_value=True)
    @patch('app.process_scan', return_value=(True, 'Time In recorded.', 'time_in', 0, '', 1, None))
    @patch('app.register_student')
    @patch('app.get_session_row', return_value=_FAKE_SESSION_ACTIVE)
    @patch('app.decrypt_qr_data', return_value=_FAKE_STUDENT)
    @patch('app.get_db')
    @patch('flask_login.utils._get_user')
    def test_qr_scan_records_scan_method_qr(
        self, mock_get_user, mock_get_db, mock_decrypt, mock_get_session,
        mock_register_student, mock_process_scan, mock_log_attendance
    ):
        """QR scan endpoint records scan_method 'qr'."""
        mock_get_user.return_value = self._mock_officer()
        self._login()

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur
        mock_get_db.return_value.__enter__.return_value = mock_conn

        response = self.client.post('/api/scan', json={
            'session_id': 'SESS001',
            'qr_data': 'encrypted_payload_bytes',
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['scan_method'], 'qr')
        mock_process_scan.assert_called_once_with(mock_conn, 'SESS001', '2023-00001', scan_method='qr')
        mock_log_attendance.assert_called_once_with(
            _FAKE_STUDENT, 'SESS001', status='Time In', fine=0, fine_reason='', conn=mock_conn, scan_method='qr'
        )

    # -- 8. Mixed scan methods: QR (Time In) then RFID (Time Out) -------------

    @patch('app.log_attendance', return_value=True)
    @patch('app.process_scan')
    @patch('app.register_student')
    @patch('app.get_session_row', return_value=_FAKE_SESSION_ACTIVE)
    @patch('app.decrypt_qr_data', return_value=_FAKE_STUDENT)
    @patch('app.get_db')
    @patch('flask_login.utils._get_user')
    def test_mixed_scan_qr_time_in_rfid_time_out(
        self, mock_get_user, mock_get_db, mock_decrypt, mock_get_session,
        mock_register_student, mock_process_scan, mock_log_attendance
    ):
        """QR Time In followed by RFID Time Out succeeds seamlessly."""
        mock_get_user.return_value = self._mock_officer()
        self._login()

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = _FAKE_STUDENT
        mock_conn.cursor.return_value = mock_cur
        mock_get_db.return_value.__enter__.return_value = mock_conn

        # 1st scan: QR -> Time In
        mock_process_scan.return_value = (True, 'Time In recorded.', 'time_in', 0, '', 1, None)
        res1 = self.client.post('/api/scan', json={
            'session_id': 'SESS001',
            'qr_data': 'encrypted_payload',
        })
        d1 = res1.get_json()
        self.assertTrue(d1['success'])
        self.assertEqual(d1['status'], 'Time In')
        self.assertEqual(d1['scan_method'], 'qr')

        # 2nd scan: RFID -> Time Out
        mock_process_scan.return_value = (True, 'Time Out recorded.', 'time_out', 0, '', 1, None)
        res2 = self.client.post('/api/scan/rfid', json={
            'session_id': 'SESS001',
            'rfid_uid': 'CARD-12345',
        })
        d2 = res2.get_json()
        self.assertTrue(d2['success'])
        self.assertEqual(d2['status'], 'Time Out')
        self.assertEqual(d2['scan_method'], 'rfid')

    # -- 9. Mixed scan methods: RFID (Time In) then QR (Time Out) -------------

    @patch('app.log_attendance', return_value=True)
    @patch('app.process_scan')
    @patch('app.register_student')
    @patch('app.get_session_row', return_value=_FAKE_SESSION_ACTIVE)
    @patch('app.decrypt_qr_data', return_value=_FAKE_STUDENT)
    @patch('app.get_db')
    @patch('flask_login.utils._get_user')
    def test_mixed_scan_rfid_time_in_qr_time_out(
        self, mock_get_user, mock_get_db, mock_decrypt, mock_get_session,
        mock_register_student, mock_process_scan, mock_log_attendance
    ):
        """RFID Time In followed by QR Time Out succeeds seamlessly."""
        mock_get_user.return_value = self._mock_officer()
        self._login()

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = _FAKE_STUDENT
        mock_conn.cursor.return_value = mock_cur
        mock_get_db.return_value.__enter__.return_value = mock_conn

        # 1st scan: RFID -> Time In
        mock_process_scan.return_value = (True, 'Time In recorded.', 'time_in', 0, '', 1, None)
        res1 = self.client.post('/api/scan/rfid', json={
            'session_id': 'SESS001',
            'rfid_uid': 'CARD-12345',
        })
        d1 = res1.get_json()
        self.assertTrue(d1['success'])
        self.assertEqual(d1['status'], 'Time In')
        self.assertEqual(d1['scan_method'], 'rfid')

        # 2nd scan: QR -> Time Out
        mock_process_scan.return_value = (True, 'Time Out recorded.', 'time_out', 0, '', 1, None)
        res2 = self.client.post('/api/scan', json={
            'session_id': 'SESS001',
            'qr_data': 'encrypted_payload',
        })
        d2 = res2.get_json()
        self.assertTrue(d2['success'])
        self.assertEqual(d2['status'], 'Time Out')
        self.assertEqual(d2['scan_method'], 'qr')


if __name__ == '__main__':
    unittest.main()


