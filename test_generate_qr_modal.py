"""
Tests for Generate QR modal preview & download action (Issue #6)
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


@patch('app.os.path.exists', return_value=True)
@patch('app.os.listdir', return_value=['QR_2024-00001.png', 'QR_2024-00002.png'])
@patch('flask_login.utils._get_user')
class TestGenerateQrModal(unittest.TestCase):

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

    def test_generate_page_renders_modal_and_controls(self, mock_get_user, mock_listdir, mock_exists):
        """Verify that /generate page renders the modal elements, download link, close controls, overlay click, and key listeners."""
        mock_get_user.return_value = self._mock_officer()
        self._login()

        response = self.client.get('/generate')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        # 1. Modal container element (#generateQrModal)
        self.assertIn('id="generateQrModal"', html)

        # 2. Modal preview elements (#generateQrModalImg, #generateQrModalFilename)
        self.assertIn('id="generateQrModalImg"', html)
        self.assertIn('id="generateQrModalFilename"', html)

        # 3. Modal download button (#generateQrModalDownload)
        self.assertIn('id="generateQrModalDownload"', html)
        self.assertIn('download', html)

        # 4. Modal close controls (.modal-close, background overlay click, and Escape key)
        self.assertIn('class="modal-close"', html)
        self.assertIn('closeGenerateQrModal()', html)
        self.assertIn("document.getElementById('generateQrModal')?.addEventListener('click'", html)
        self.assertIn('Escape', html)

    def test_server_rendered_gallery_items_have_click_bindings(self, mock_get_user, mock_listdir, mock_exists):
        """Verify that server-rendered QR code cards include data-filename attributes for event delegation."""
        mock_get_user.return_value = self._mock_officer()
        self._login()

        response = self.client.get('/generate')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn('data-filename="QR_2024-00001.png"', html)
        self.assertIn("document.getElementById('qrGallery')", html)

    def test_dynamic_gallery_script_has_click_bindings(self, mock_get_user, mock_listdir, mock_exists):
        """Verify that the JavaScript gallery renderer includes openGenerateQrModal and event delegation for dynamic cards."""
        mock_get_user.return_value = self._mock_officer()
        self._login()

        response = self.client.get('/generate')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)

        self.assertIn('openGenerateQrModal', html)
        self.assertIn('data-filename="${file}"', html)
        self.assertIn("document.getElementById('qrGallery')", html)


if __name__ == '__main__':
    unittest.main()
