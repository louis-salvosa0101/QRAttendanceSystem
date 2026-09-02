"""
Unit tests for qr_generator.py
"""
import os
import unittest
from config import QR_CODES_DIR
from qr_generator import get_qr_filepath


class TestQrGenerator(unittest.TestCase):

    def test_get_qr_filepath_default_dir(self):
        """get_qr_filepath returns expected path using default QR_CODES_DIR."""
        student_number = '2023-00001'
        expected = os.path.join(QR_CODES_DIR, "QR_2023-00001.png")
        self.assertEqual(get_qr_filepath(student_number), expected)

    def test_get_qr_filepath_custom_dir(self):
        """get_qr_filepath respects custom output_dir."""
        student_number = '2023-00002'
        custom_dir = "/tmp/test_qr"
        expected = os.path.join(custom_dir, "QR_2023-00002.png")
        self.assertEqual(get_qr_filepath(student_number, output_dir=custom_dir), expected)

    def test_get_qr_filepath_sanitization(self):
        """get_qr_filepath sanitizes spaces and slashes in student numbers."""
        student_number = '2023 / 00003 test'
        expected = os.path.join(QR_CODES_DIR, "QR_2023_-_00003_test.png")
        self.assertEqual(get_qr_filepath(student_number), expected)


if __name__ == '__main__':
    unittest.main()
