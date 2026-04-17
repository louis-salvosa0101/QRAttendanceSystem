"""
Authentication module for the QR Attendance System.
Provides Flask-Login integration with bcrypt password hashing.
Only officers can log in -- students are excluded.
"""
import bcrypt
from flask import jsonify, request
from flask_login import LoginManager, UserMixin

from db import get_db, _cur
from config import ph_now

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'


@login_manager.unauthorized_handler
def unauthorized():
    """Return JSON 401 for API requests, redirect for page requests."""
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'message': 'Authentication required.'}), 401
    from flask import redirect, url_for
    return redirect(url_for('login', next=request.url))


class Officer(UserMixin):
    """Flask-Login compatible user model for officers."""

    def __init__(self, id, username, name, created_at, is_admin=False):
        self.id = id
        self.username = username
        self.name = name
        self.created_at = created_at
        self.is_admin = bool(is_admin)


@login_manager.user_loader
def load_user(user_id):
    """Load an officer by their database ID, with Flask-session caching."""
    from flask import session as flask_session
    cached = flask_session.get('_officer_cache')
    if cached and cached.get('id') == int(user_id):
        return Officer(id=cached['id'], username=cached['username'],
                       name=cached['name'], created_at=cached['created_at'],
                       is_admin=cached.get('is_admin', 0))
    with get_db() as conn:
        cur = _cur(conn)
        cur.execute(
            "SELECT id, username, name, created_at, is_admin FROM officers WHERE id = %s",
            (int(user_id),)
        )
        row = cur.fetchone()
    if row:
        flask_session['_officer_cache'] = dict(row)
        return Officer(id=row['id'], username=row['username'],
                       name=row['name'], created_at=row['created_at'],
                       is_admin=row.get('is_admin', 0))
    return None


def authenticate(username: str, password: str) -> Officer | None:
    """
    Verify username and password against the officers table.
    Returns an Officer object on success, None on failure.
    """
    with get_db() as conn:
        cur = _cur(conn)
        cur.execute(
            "SELECT id, username, password_hash, name, created_at, is_admin FROM officers WHERE username = %s",
            (username,)
        )
        row = cur.fetchone()

    if not row:
        return None

    if bcrypt.checkpw(password.encode('utf-8'), row['password_hash'].encode('utf-8')):
        return Officer(id=row['id'], username=row['username'],
                       name=row['name'], created_at=row['created_at'],
                       is_admin=row.get('is_admin', 0))
    return None


def hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def seed_default_admin():
    """
    Create the default admin officer if no officers exist.
    Default credentials: admin / admin123
    Also ensures at least one officer has is_admin = 1.
    """
    with get_db() as conn:
        cur = _cur(conn)
        cur.execute("SELECT COUNT(*) AS cnt FROM officers")
        count = cur.fetchone()['cnt']

        if count == 0:
            pw_hash = hash_password('admin123')
            now = ph_now().isoformat()
            cur.execute(
                """INSERT INTO officers (username, password_hash, name, created_at, is_admin)
                   VALUES (%s, %s, %s, %s, 1)""",
                ('admin', pw_hash, 'Administrator', now)
            )
            print("\n" + "*" * 60)
            print("  DEFAULT ADMIN ACCOUNT CREATED")
            print("  Username: admin")
            print("  Password: admin123")
            print("  ** CHANGE THIS PASSWORD AFTER FIRST LOGIN **")
            print("*" * 60 + "\n")
        else:
            cur.execute("SELECT COUNT(*) AS cnt FROM officers WHERE is_admin = 1")
            if cur.fetchone()['cnt'] == 0:
                cur.execute(
                    "UPDATE officers SET is_admin = 1 WHERE id = (SELECT MIN(id) FROM officers)"
                )
