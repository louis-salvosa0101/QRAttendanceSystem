"""
PostgreSQL database module for the QR Attendance System.
Connects to Supabase PostgreSQL for cloud-hosted, ACID-compliant storage.
Uses psycopg 3 with connection pooling to avoid per-request TCP/TLS overhead.
"""
import atexit
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from config import DATABASE_URL

_pool: ConnectionPool | None = None


def _get_pool() -> ConnectionPool:
    """Lazily initialise and return the global connection pool."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            DATABASE_URL,
            min_size=2,
            max_size=10,
            open=True,
        )
    return _pool


def close_pool():
    """Shut down the pool gracefully."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


atexit.register(close_pool)


@contextmanager
def get_db():
    """Context manager that borrows a connection from the pool."""
    pool = _get_pool()
    with pool.connection() as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def _cur(conn):
    """Return a dict-row cursor for the given connection."""
    return conn.cursor(row_factory=dict_row)


def init_db():
    """Create all tables if they don't exist."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS students (
                    id SERIAL PRIMARY KEY,
                    student_number TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    course TEXT,
                    year TEXT,
                    section TEXT
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_students_number ON students(student_number)")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id SERIAL PRIMARY KEY,
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
            cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_session_id ON sessions(session_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions(is_active)")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS session_scans (
                    id SERIAL PRIMARY KEY,
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
            cur.execute("CREATE INDEX IF NOT EXISTS idx_session_scans_session ON session_scans(session_id)")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS attendance_records (
                    id SERIAL PRIMARY KEY,
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
            cur.execute("CREATE INDEX IF NOT EXISTS idx_attendance_session ON attendance_records(session_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance_records(student_number)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_attendance_recorded ON attendance_records(recorded_at)")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS officers (
                    id SERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_officers_username ON officers(username)")
