"""
SQLite database module for the QR Attendance System.
Provides ACID-compliant storage for students, sessions, and attendance records.
"""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Generator

from config import EXCEL_DIR, DATABASE_PATH


def get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory for dict-like rows."""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for database connections (auto-commit/rollback)."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create all tables if they don't exist."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_number TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                course TEXT,
                year TEXT,
                section TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_students_number ON students(student_number)")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                subject TEXT,
                teacher TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                required_course TEXT,
                required_year TEXT,
                required_section TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_session_id ON sessions(session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions(is_active)")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS session_scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                student_number TEXT NOT NULL,
                status TEXT NOT NULL,
                time_in TEXT NOT NULL,
                time_out TEXT,
                fine INTEGER DEFAULT 0,
                fine_reason TEXT,
                UNIQUE(session_id, student_number),
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_session_scans_session ON session_scans(session_id)")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS attendance_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at TEXT NOT NULL,
                name TEXT,
                student_number TEXT NOT NULL,
                course TEXT,
                year TEXT,
                section TEXT,
                session_id TEXT NOT NULL,
                status TEXT NOT NULL,
                fine INTEGER DEFAULT 0,
                fine_reason TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_attendance_session ON attendance_records(session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance_records(student_number)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_attendance_recorded ON attendance_records(recorded_at)")


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert sqlite3.Row to plain dict."""
    return dict(row) if row else {}
