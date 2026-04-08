"""
Advanced QR-Based Attendance System - Main Flask Application
"""
import os
import io
import json
import zipfile
from datetime import datetime
from flask import (Flask, render_template, request, jsonify, redirect,
                   url_for, flash, send_from_directory, send_file)
from flask_login import login_required, login_user, logout_user, current_user
from werkzeug.utils import secure_filename
from config import (SECRET_KEY, QR_CODES_DIR, EXCEL_DIR, MASTER_LIST_DIR,
                    ATTENDANCE_LOG_FILE, FINE_LATE, FINE_ABSENT, FINE_PARTIAL,
                    LATE_THRESHOLD_MINUTES)
from crypto_utils import decrypt_qr_data
from qr_generator import generate_single_qr, batch_generate_from_excel
from session_manager import (create_session, get_session, get_active_sessions,
                              get_all_sessions, validate_session,
                              record_student_scan, close_session, clear_all_sessions,
                              process_scan, get_session_row)
from db import get_db, _cur
from excel_logger import (log_attendance, log_absent_students,
                           generate_summary_sheet,
                           get_attendance_records, get_session_stats,
                           create_sample_master_list, clear_attendance_records)
from student_registry import (register_student, register_students_bulk,
                               get_all_students, get_student,
                               get_students_by_filter, delete_student,
                               clear_registry, get_registry_stats)

from db import init_db
from auth import login_manager, authenticate, seed_default_admin, hash_password

init_db()
seed_default_admin()

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

login_manager.init_app(app)

ALLOWED_EXTENSIONS = {'xlsx', 'xls'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ─── AUTH ROUTES ──────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Officer login page."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        officer = authenticate(username, password)
        if officer:
            login_user(officer)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            error = 'Invalid username or password.'

    return render_template('login.html', error=error)


@app.route('/logout')
@login_required
def logout():
    """Log out the current officer."""
    logout_user()
    return redirect(url_for('login'))


@app.route('/api/change-password', methods=['POST'])
@login_required
def api_change_password():
    """Change the current officer's password."""
    import bcrypt
    data = request.get_json() or {}
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')

    if not current_password or not new_password or not confirm_password:
        return jsonify({'success': False, 'message': 'All fields are required.'}), 400

    if new_password != confirm_password:
        return jsonify({'success': False, 'message': 'New passwords do not match.'}), 400

    if len(new_password) < 6:
        return jsonify({'success': False, 'message': 'New password must be at least 6 characters.'}), 400

    with get_db() as conn:
        cur = _cur(conn)
        cur.execute("SELECT password_hash FROM officers WHERE id = %s", (current_user.id,))
        row = cur.fetchone()

        if not row or not bcrypt.checkpw(current_password.encode('utf-8'),
                                          row['password_hash'].encode('utf-8')):
            return jsonify({'success': False, 'message': 'Current password is incorrect.'}), 403

        new_hash = hash_password(new_password)
        cur.execute("UPDATE officers SET password_hash = %s WHERE id = %s",
                    (new_hash, current_user.id))

    return jsonify({'success': True, 'message': 'Password changed successfully.'})


# ─── PAGES ───────────────────────────────────────────────────────────────

@app.route('/')
@login_required
def index():
    """Dashboard / Home page."""
    active_sessions = get_active_sessions()
    all_sessions = get_all_sessions()
    registry_stats = get_registry_stats()
    return render_template('index.html',
                           active_sessions=active_sessions,
                           total_sessions=len(all_sessions),
                           registry_stats=registry_stats)


@app.route('/scanner')
@login_required
def scanner_page():
    """QR Scanner page for teachers."""
    active_sessions = get_active_sessions()
    return render_template('scanner.html', active_sessions=active_sessions)


@app.route('/sessions')
@login_required
def sessions_page():
    """Session management page."""
    active_sessions = get_active_sessions()
    all_sessions = get_all_sessions()
    all_students = get_all_students()
    courses = sorted(set(s.get('course', '') for s in all_students if s.get('course')))
    return render_template('sessions.html',
                           active_sessions=active_sessions,
                           all_sessions=all_sessions,
                           courses=courses)


@app.route('/generate')
@login_required
def generate_page():
    """QR Code generation page."""
    qr_files = []
    if os.path.exists(QR_CODES_DIR):
        qr_files = [f for f in os.listdir(QR_CODES_DIR) if f.endswith('.png')]
    return render_template('generate.html', qr_files=qr_files)


@app.route('/records')
@login_required
def records_page():
    """Attendance records page."""
    session_id = request.args.get('session_id', '')
    student_number = request.args.get('student_number', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    records = get_attendance_records(
        session_id=session_id or None,
        student_number=student_number or None,
        date_from=date_from or None,
        date_to=date_to or None
    )

    all_sessions = get_all_sessions()

    return render_template('records.html',
                           records=records,
                           all_sessions=all_sessions,
                           filters={
                               'session_id': session_id,
                               'student_number': student_number,
                               'date_from': date_from,
                               'date_to': date_to
                           })


@app.route('/students')
@login_required
def students_page():
    """Student registry management page."""
    students = get_all_students()
    stats = get_registry_stats()
    return render_template('students.html', students=students, stats=stats)


@app.route('/students/<student_number>')
@login_required
def student_detail_page(student_number):
    """Individual student dashboard with attendance records and fines."""
    student = get_student(student_number)
    if not student or not student.get('student_number'):
        return render_template('404.html'), 404

    records = get_attendance_records(student_number=student_number)

    # Compute summary stats
    total_fines = 0
    absent_count = 0
    late_count = 0
    partial_count = 0
    time_in_count = 0
    time_out_count = 0
    sessions_set = set()
    fines_list = []

    for r in records:
        fine = r.get('fine') or 0
        total_fines += fine
        sess_id = r.get('session_id')
        if sess_id:
            sessions_set.add(sess_id)
        status = r.get('status', '')
        if status == 'Absent':
            absent_count += 1
        elif status == 'Time In':
            time_in_count += 1
        elif status == 'Time Out':
            time_out_count += 1
        if 'Partial' in status:
            partial_count += 1
        if fine > 0:
            late_count += 1
            fines_list.append({
                'date': r.get('datetime', ''),
                'session_id': sess_id,
                'status': status,
                'fine': fine,
                'reason': r.get('fine_reason', ''),
            })

    summary = {
        'total_sessions': len(sessions_set),
        'absent_count': absent_count,
        'late_count': late_count,
        'partial_count': partial_count,
        'time_in_count': time_in_count,
        'time_out_count': time_out_count,
        'total_fines': total_fines,
    }

    return render_template('student_detail.html',
                           student=student,
                           records=records,
                           summary=summary,
                           fines_list=fines_list)


# ─── API ENDPOINTS ──────────────────────────────────────────────────────

@app.route('/api/session/create', methods=['POST'])
@login_required
def api_create_session():
    """Create a new attendance session."""
    data = request.get_json()
    subject = data.get('subject', '')
    teacher = data.get('teacher', '')
    notes = data.get('notes', '')
    duration_hours = data.get('duration_hours')
    required_course = data.get('required_course', '')
    required_year = data.get('required_year', [])
    required_section = data.get('required_section', '')

    session = create_session(
        subject=subject,
        teacher=teacher,
        notes=notes,
        duration_hours=duration_hours,
        required_course=required_course,
        required_year=required_year,
        required_section=required_section,
    )
    return jsonify({'success': True, 'session': session})


@app.route('/api/session/<session_id>/close', methods=['POST'])
@login_required
def api_close_session(session_id):
    """
    Close an attendance session.
    After closing, mark absent all registered students who were required but didn't scan.
    """
    session = get_session(session_id)
    if not session:
        return jsonify({'success': False, 'message': 'Session not found.'})

    success, message = close_session(session_id)
    if not success:
        return jsonify({'success': False, 'message': message})

    session = get_session(session_id)

    required_students = get_students_by_filter(
        course=session.get('required_course') or None,
        year=session.get('required_year') or None,
        section=session.get('required_section') or None,
    )

    absent_result = {'absent_logged': 0, 'partial_updated': 0}
    if required_students:
        absent_result = log_absent_students(session_id, session, required_students)

    return jsonify({
        'success': True,
        'message': message,
        'absent_logged': absent_result.get('absent_logged', 0),
        'partial_updated': absent_result.get('partial_updated', 0),
    })


@app.route('/api/session/clear-history', methods=['DELETE'])
@login_required
def api_clear_session_history():
    """Clear all session history from database."""
    try:
        deleted = clear_all_sessions()
        return jsonify({
            'success': True,
            'message': f'Session history cleared ({deleted} sessions removed).' if deleted
            else 'No session history to clear.'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/session/<session_id>/stats')
@login_required
def api_session_stats(session_id):
    """Get statistics for a session."""
    stats = get_session_stats(session_id)
    session = get_session(session_id)
    return jsonify({'success': True, 'stats': stats, 'session': session})


@app.route('/api/scan', methods=['POST'])
@login_required
def api_scan_qr():
    """
    Process a scanned QR code.
    Uses a single pooled DB connection for the entire pipeline:
      validate session -> check filters -> register student -> record scan -> log attendance.
    """
    data = request.get_json()
    qr_content = data.get('qr_data', '')
    session_id = data.get('session_id', '')

    if not session_id:
        return jsonify({
            'success': False,
            'error': 'no_session',
            'message': 'No active session selected. Please select or create a session first.'
        })

    # Decrypt first (CPU-only, no DB needed)
    student_data = decrypt_qr_data(qr_content)
    if not student_data:
        return jsonify({
            'success': False,
            'error': 'invalid_qr',
            'message': 'Invalid or tampered QR code. Could not decrypt data.'
        })

    required_fields = ['name', 'student_number', 'course', 'year', 'section']
    for field in required_fields:
        if field not in student_data:
            return jsonify({
                'success': False,
                'error': 'invalid_qr',
                'message': f'QR code is missing required field: {field}'
            })

    # --- single DB connection for everything below ---
    with get_db() as conn:
        # 1. Lightweight session fetch (no scanned-students load)
        session = get_session_row(conn, session_id)
        if not session:
            return jsonify({
                'success': False,
                'error': 'invalid_session',
                'message': 'Session not found.'
            })

        if not session.get('is_active'):
            return jsonify({
                'success': False,
                'error': 'invalid_session',
                'message': 'Session has been closed.'
            })

        now = datetime.now()
        expires_at = datetime.fromisoformat(session['expires_at'])
        if now >= expires_at:
            _cur(conn).execute(
                "UPDATE sessions SET is_active = 0 WHERE session_id = %s",
                (session_id,),
            )
            return jsonify({
                'success': False,
                'error': 'invalid_session',
                'message': 'Session has expired.'
            })

        # 2. Course / year / section filter check
        req_course = session.get('required_course') or ''
        req_year = session.get('required_year') or []
        req_section = session.get('required_section') or ''
        student_course = str(student_data.get('course', '')).strip()
        student_year = str(student_data.get('year', '')).strip()
        student_section = str(student_data.get('section', '')).strip()

        not_included_reasons = []
        if req_course and student_course != req_course:
            not_included_reasons.append(f"course ({student_course} != {req_course})")
        if req_year and isinstance(req_year, list) and len(req_year) > 0 and student_year not in req_year:
            year_labels = {'1': '1st', '2': '2nd', '3': '3rd', '4': '4th', '5': '5th'}
            allowed = ', '.join(year_labels.get(y, y) + ' year' for y in req_year)
            not_included_reasons.append(
                f"year level (you are {year_labels.get(student_year, student_year)} year; "
                f"session is for {allowed} only)"
            )
        if req_section and student_section != req_section:
            not_included_reasons.append(f"section ({student_section} != {req_section})")

        if not_included_reasons:
            return jsonify({
                'success': False,
                'error': 'not_included',
                'message': f"{student_data['name']} is not included in this session. "
                           f"This session is for {', '.join(not_included_reasons)}.",
                'student': student_data
            })

        # 3. Register / upsert student (reuses conn)
        register_student(student_data, conn=conn)

        # 4. Validate + record scan + get count (reuses conn)
        success, scan_msg, scan_type, fine, fine_reason, attendance_count = \
            process_scan(conn, session_id, student_data['student_number'])

        if not success:
            return jsonify({
                'success': False,
                'error': 'duplicate',
                'message': f"{student_data['name']} ({student_data['student_number']}) - {scan_msg}",
                'student': student_data
            })

        status = 'Time In' if scan_type == 'time_in' else 'Time Out'

        # 5. Log attendance record (reuses conn)
        log_success = log_attendance(student_data, session_id, status=status,
                                     fine=fine, fine_reason=fine_reason, conn=conn)

    if not log_success:
        return jsonify({
            'success': False,
            'error': 'log_error',
            'message': 'Failed to log attendance.'
        })

    fine_msg = f' | Fine: ₱{fine} ({fine_reason})' if fine else ''
    return jsonify({
        'success': True,
        'message': f"{student_data['name']} - {status} recorded!{fine_msg}",
        'student': student_data,
        'scan_type': scan_type,
        'status': status,
        'fine': fine,
        'fine_reason': fine_reason,
        'attendance_count': attendance_count
    })


# ─── STUDENT REGISTRY API ──────────────────────────────────────────────

@app.route('/api/students', methods=['GET'])
@login_required
def api_list_students():
    """List all registered students."""
    students = get_all_students()
    stats = get_registry_stats()
    return jsonify({'success': True, 'students': students, 'stats': stats})


@app.route('/api/students/register', methods=['POST'])
@login_required
def api_register_student():
    """Register a single student manually."""
    data = request.get_json()
    try:
        student_data = {
            'name': data.get('name', '').strip(),
            'student_number': data.get('student_number', '').strip(),
            'course': data.get('course', '').strip(),
            'year': data.get('year', '').strip(),
            'section': data.get('section', '').strip(),
        }
        if not student_data['name'] or not student_data['student_number']:
            return jsonify({'success': False, 'message': 'Name and Student Number are required.'})

        is_new = register_student(student_data)
        return jsonify({
            'success': True,
            'message': f"Student {'registered' if is_new else 'updated'} successfully.",
            'is_new': is_new
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/students/register-qr', methods=['POST'])
@login_required
def api_register_student_qr():
    """
    Register a student by scanning their QR code.
    Decrypts the QR payload and adds the student to the registry.
    No active session is needed -- this is registry-only.
    """
    data = request.get_json()
    qr_content = data.get('qr_data', '').strip()

    if not qr_content:
        return jsonify({'success': False, 'message': 'No QR data provided.'})

    student_data = decrypt_qr_data(qr_content)
    if not student_data:
        return jsonify({
            'success': False,
            'message': 'Invalid or tampered QR code. Could not read student data.'
        })

    required_fields = ['name', 'student_number', 'course', 'year', 'section']
    for field in required_fields:
        if field not in student_data:
            return jsonify({
                'success': False,
                'message': f'QR code is missing field: {field}'
            })

    is_new = register_student(student_data)
    return jsonify({
        'success': True,
        'message': f"{'Registered' if is_new else 'Updated'}: {student_data['name']} ({student_data['student_number']})",
        'student': student_data,
        'is_new': is_new
    })


@app.route('/api/students/import', methods=['POST'])
@login_required
def api_import_students():
    """Import students from an uploaded Excel file into the registry."""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded.'})

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected.'})

    if not allowed_file(file.filename):
        return jsonify({'success': False, 'message': 'Invalid file type. Please upload .xlsx or .xls file.'})

    try:
        from openpyxl import load_workbook
        filename = secure_filename(file.filename)
        upload_path = os.path.join(MASTER_LIST_DIR, filename)
        file.save(upload_path)

        wb = load_workbook(upload_path)
        ws = wb.active

        headers = {}
        for col_idx, cell in enumerate(ws[1], 1):
            if cell.value:
                headers[cell.value.strip().lower()] = col_idx

        col_map = {}
        name_variants = ['name', 'full name', 'student name', 'fullname']
        number_variants = ['student number', 'student_number', 'studentnumber', 'id', 'student id', 'student_id']
        course_variants = ['course', 'program', 'degree']
        year_variants = ['year', 'year level', 'yr']
        section_variants = ['section', 'sec', 'sect']

        for key, variants in [('name', name_variants), ('student_number', number_variants),
                               ('course', course_variants), ('year', year_variants),
                               ('section', section_variants)]:
            for v in variants:
                if v in headers:
                    col_map[key] = headers[v]
                    break

        required = ['name', 'student_number', 'course', 'year', 'section']
        missing = [k for k in required if k not in col_map]
        if missing:
            wb.close()
            return jsonify({
                'success': False,
                'message': f"Missing required columns: {', '.join(missing)}. Found: {list(headers.keys())}"
            })

        students = []
        for row in ws.iter_rows(min_row=2):
            name = str(row[col_map['name'] - 1].value or '').strip()
            student_number = str(row[col_map['student_number'] - 1].value or '').strip()
            if not name or not student_number:
                continue
            students.append({
                'name': name,
                'student_number': student_number,
                'course': str(row[col_map['course'] - 1].value or '').strip(),
                'year': str(row[col_map['year'] - 1].value or '').strip(),
                'section': str(row[col_map['section'] - 1].value or '').strip(),
            })
        wb.close()

        result = register_students_bulk(students)
        return jsonify({
            'success': True,
            'message': f"Import complete: {result['added']} new, {result['updated']} updated.",
            'added': result['added'],
            'updated': result['updated'],
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/students/<student_number>', methods=['DELETE'])
@login_required
def api_delete_student(student_number):
    """Delete a student from the registry."""
    success = delete_student(student_number)
    return jsonify({
        'success': success,
        'message': 'Student deleted.' if success else 'Student not found.'
    })


@app.route('/api/students/clear', methods=['DELETE'])
@login_required
def api_clear_students():
    """Clear entire student registry."""
    count = clear_registry()
    return jsonify({'success': True, 'message': f'{count} students removed from registry.'})


# ─── QR GENERATION API ──────────────────────────────────────────────────

@app.route('/api/generate/single', methods=['POST'])
@login_required
def api_generate_single():
    """Generate a single QR code and auto-register the student."""
    data = request.get_json()
    try:
        student_data = {
            'name': data.get('name', '').strip(),
            'student_number': data.get('student_number', '').strip(),
            'course': data.get('course', '').strip(),
            'year': data.get('year', '').strip(),
            'section': data.get('section', '').strip(),
        }

        if not student_data['name'] or not student_data['student_number']:
            return jsonify({'success': False, 'message': 'Name and Student Number are required.'})

        register_student(student_data)

        filepath = generate_single_qr(student_data)
        filename = os.path.basename(filepath)

        return jsonify({
            'success': True,
            'message': f'QR code generated for {student_data["name"]}',
            'filename': filename,
            'url': url_for('serve_qr', filename=filename)
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/generate/batch', methods=['POST'])
@login_required
def api_generate_batch():
    """Generate QR codes from an uploaded Excel file and register all students."""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded.'})

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected.'})

    if not allowed_file(file.filename):
        return jsonify({'success': False, 'message': 'Invalid file type. Please upload .xlsx or .xls file.'})

    try:
        filename = secure_filename(file.filename)
        upload_path = os.path.join(MASTER_LIST_DIR, filename)
        file.save(upload_path)

        results = batch_generate_from_excel(upload_path)

        from openpyxl import load_workbook as lw
        wb = lw(upload_path)
        ws = wb.active
        headers = {}
        for col_idx, cell in enumerate(ws[1], 1):
            if cell.value:
                headers[cell.value.strip().lower()] = col_idx

        col_map = {}
        for key, variants in [
            ('name', ['name', 'full name', 'student name', 'fullname']),
            ('student_number', ['student number', 'student_number', 'studentnumber', 'id', 'student id']),
            ('course', ['course', 'program', 'degree']),
            ('year', ['year', 'year level', 'yr']),
            ('section', ['section', 'sec', 'sect']),
        ]:
            for v in variants:
                if v in headers:
                    col_map[key] = headers[v]
                    break

        students = []
        if all(k in col_map for k in ['name', 'student_number', 'course', 'year', 'section']):
            for row in ws.iter_rows(min_row=2):
                name = str(row[col_map['name'] - 1].value or '').strip()
                student_number = str(row[col_map['student_number'] - 1].value or '').strip()
                if not name or not student_number:
                    continue
                students.append({
                    'name': name,
                    'student_number': student_number,
                    'course': str(row[col_map['course'] - 1].value or '').strip(),
                    'year': str(row[col_map['year'] - 1].value or '').strip(),
                    'section': str(row[col_map['section'] - 1].value or '').strip(),
                })
        wb.close()

        if students:
            register_students_bulk(students)

        return jsonify({
            'success': True,
            'message': f"Generated {results['success']} QR codes with {results['errors']} errors. {len(students)} students registered.",
            'results': {
                'success': results['success'],
                'errors': results['errors'],
                'error_details': results['error_details'],
                'registered': len(students),
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/generate/sample', methods=['POST'])
@login_required
def api_generate_sample():
    """Generate a sample master list Excel file."""
    try:
        filepath = create_sample_master_list()
        return jsonify({
            'success': True,
            'message': 'Sample master list created.',
            'filepath': filepath
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/records/summary', methods=['POST'])
@login_required
def api_generate_summary():
    """Generate the summary sheet in the attendance log."""
    try:
        success = generate_summary_sheet()
        return jsonify({
            'success': success,
            'message': 'Summary sheet generated successfully.' if success else 'Failed to generate summary.'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/records/download')
@login_required
def api_download_records():
    """Download the attendance records as Excel (supports filters)."""
    session_id = request.args.get('session_id', '')
    student_number = request.args.get('student_number', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    records = get_attendance_records(
        session_id=session_id or None,
        student_number=student_number or None,
        date_from=date_from or None,
        date_to=date_to or None
    )

    if not records:
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Records"
        ws.append(['Date & Time', 'Name', 'Student Number', 'Course', 'Year', 'Section', 'Session ID', 'Status', 'Fine', 'Fine Reason'])
        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        return send_file(out, as_attachment=True, download_name='attendance_export.xlsx',
                        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

    wb = Workbook()
    ws = wb.active
    ws.title = "Filtered Records"

    headers = ['Date & Time', 'Name', 'Student Number', 'Course', 'Year', 'Section', 'Session ID', 'Status', 'Fine', 'Fine Reason']
    ws.append(headers)

    header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center')

    total_fines = 0
    for r in records:
        fine_val = r['fine'] if r['fine'] else 0
        total_fines += fine_val
        ws.append([
            r['datetime'],
            r['name'],
            r['student_number'],
            r['course'],
            r['year'],
            r['section'],
            r['session_id'],
            r['status'],
            fine_val,
            r.get('fine_reason', '')
        ])

    total_row = len(records) + 2
    ws.append([])
    total_row += 1
    ws.cell(row=total_row, column=8, value='TOTAL FINES:').font = Font(bold=True, size=12)
    ws.cell(row=total_row, column=8).alignment = Alignment(horizontal='right')
    ws.cell(row=total_row, column=9, value=total_fines).font = Font(bold=True, size=12, color='C00000')
    ws.cell(row=total_row, column=9).alignment = Alignment(horizontal='center')

    summary_sheet = wb.create_sheet(title="Summary")
    student_data = {}
    for r in records:
        sn = r['student_number']
        if sn not in student_data:
            student_data[sn] = {
                'name': r['name'], 'student_number': sn,
                'course': r['course'], 'year': r['year'], 'section': r['section'],
                'total_fines': 0, 'absent': 0, 'late': 0, 'present': 0,
            }
        fine_val = r['fine'] if r['fine'] else 0
        student_data[sn]['total_fines'] += fine_val
        status = r.get('status', '')
        if status == 'Absent':
            student_data[sn]['absent'] += 1
        elif status in ('Late', 'Partial (No Time Out)') or (status == 'Time In' and fine_val > 0):
            student_data[sn]['late'] += 1
        else:
            student_data[sn]['present'] += 1

    sum_headers = ['Name', 'Student Number', 'Course', 'Year', 'Section',
                   'Present', 'Late', 'Absent', 'Total Fines (PHP)']
    summary_sheet.append(sum_headers)
    sum_fill = PatternFill(start_color="2E75B6", end_color="2E75B6", fill_type="solid")
    sum_font = Font(color="FFFFFF", bold=True)
    for cell in summary_sheet[1]:
        cell.fill = sum_fill
        cell.font = sum_font
        cell.alignment = Alignment(horizontal='center')

    fine_fill = PatternFill(start_color="f8d7da", end_color="f8d7da", fill_type="solid")
    fine_font = Font(bold=True, color='721c24')
    for sd in sorted(student_data.values(), key=lambda x: x['name']):
        summary_sheet.append([
            sd['name'], sd['student_number'], sd['course'], sd['year'], sd['section'],
            sd['present'], sd['late'], sd['absent'], sd['total_fines'],
        ])
        row_num = summary_sheet.max_row
        fine_cell = summary_sheet.cell(row=row_num, column=9)
        if sd['total_fines'] > 0:
            fine_cell.fill = fine_fill
            fine_cell.font = fine_font

    grand_row = summary_sheet.max_row + 2
    summary_sheet.cell(row=grand_row, column=8, value='GRAND TOTAL:').font = Font(bold=True, size=12)
    summary_sheet.cell(row=grand_row, column=8).alignment = Alignment(horizontal='right')
    summary_sheet.cell(row=grand_row, column=9, value=total_fines).font = Font(bold=True, size=13, color='C00000')
    summary_sheet.cell(row=grand_row, column=9).alignment = Alignment(horizontal='center')

    sum_widths = [30, 20, 15, 8, 10, 10, 10, 10, 20]
    for i, w in enumerate(sum_widths, 1):
        summary_sheet.column_dimensions[chr(64 + i)].width = w

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)

    filename = "attendance_export.xlsx"
    if session_id:
        filename = f"session_{session_id}_records.xlsx"

    return send_file(
        out,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@app.route('/api/records/reset', methods=['DELETE'])
@login_required
def api_reset_records():
    """Reset all attendance records by clearing the database."""
    try:
        deleted = clear_attendance_records()
        return jsonify({
            'success': True,
            'message': f'Attendance records reset ({deleted} records removed).' if deleted
            else 'No records to reset.'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/qrcodes/list')
@login_required
def api_list_qrcodes():
    """List all generated QR code files."""
    qr_files = []
    if os.path.exists(QR_CODES_DIR):
        qr_files = [f for f in os.listdir(QR_CODES_DIR) if f.endswith('.png')]
    return jsonify({'success': True, 'files': qr_files})


@app.route('/api/qrcodes/clear', methods=['DELETE'])
@login_required
def api_clear_qrcodes():
    """Delete all generated QR code files."""
    try:
        deleted = 0
        if os.path.exists(QR_CODES_DIR):
            for f in os.listdir(QR_CODES_DIR):
                if f.endswith('.png'):
                    os.remove(os.path.join(QR_CODES_DIR, f))
                    deleted += 1
        return jsonify({
            'success': True,
            'message': f'{deleted} QR code(s) deleted.',
            'deleted': deleted
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/qrcodes/download-all')
@login_required
def api_download_all_qrcodes():
    """Download all generated QR codes as a single ZIP file."""
    try:
        qr_files = []
        if os.path.exists(QR_CODES_DIR):
            qr_files = [f for f in os.listdir(QR_CODES_DIR) if f.endswith('.png')]

        if not qr_files:
            return jsonify({'success': False, 'message': 'No QR codes to download.'}), 404

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for filename in qr_files:
                filepath = os.path.join(QR_CODES_DIR, filename)
                zf.write(filepath, filename)

        zip_buffer.seek(0)
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name='qr_codes_all.zip'
        )
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ─── STATIC FILE SERVING ────────────────────────────────────────────────

@app.route('/qrcodes/<filename>')
@login_required
def serve_qr(filename):
    """Serve generated QR code images."""
    return send_from_directory(QR_CODES_DIR, filename)


# ─── ERROR HANDLERS ─────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Internal server error'}), 500


# ─── RUN ─────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("\n" + "=" * 60)
    print("  QR Attendance System")
    print(f"  Local URL:   http://127.0.0.1:{port}")
    print("=" * 60)

    use_ngrok = os.environ.get('USE_NGROK', '0') == '1'
    if use_ngrok:
        try:
            from pyngrok import ngrok
            public_url = ngrok.connect(port, "http").public_url
            print(f"  Ngrok URL:   {public_url}")
        except Exception as e:
            print(f"  [!] ngrok failed: {e}")

    app.run(debug=True, host='0.0.0.0', port=port, use_reloader=False)
