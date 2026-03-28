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
from werkzeug.utils import secure_filename
from config import (SECRET_KEY, QR_CODES_DIR, EXCEL_DIR, MASTER_LIST_DIR,
                    ATTENDANCE_LOG_FILE, FINE_LATE, FINE_ABSENT, FINE_PARTIAL,
                    LATE_THRESHOLD_MINUTES)
from crypto_utils import decrypt_qr_data
from qr_generator import generate_single_qr, batch_generate_from_excel
from session_manager import (create_session, get_session, get_active_sessions,
                              get_all_sessions, validate_session,
                              record_student_scan, close_session, clear_all_sessions)
from excel_logger import (log_attendance, log_absent_students,
                           generate_summary_sheet,
                           get_attendance_records, get_session_stats,
                           create_sample_master_list, clear_attendance_records)
from student_registry import (register_student, register_students_bulk,
                               get_all_students, get_student,
                               get_students_by_filter, delete_student,
                               clear_registry, get_registry_stats)

from db import init_db
init_db()

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

ALLOWED_EXTENSIONS = {'xlsx', 'xls'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ─── PAGES ───────────────────────────────────────────────────────────────

@app.route('/')
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
def scanner_page():
    """QR Scanner page for teachers."""
    active_sessions = get_active_sessions()
    return render_template('scanner.html', active_sessions=active_sessions)


@app.route('/sessions')
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
def generate_page():
    """QR Code generation page."""
    # List existing QR codes
    qr_files = []
    if os.path.exists(QR_CODES_DIR):
        qr_files = [f for f in os.listdir(QR_CODES_DIR) if f.endswith('.png')]
    return render_template('generate.html', qr_files=qr_files)


@app.route('/records')
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
def students_page():
    """Student registry management page."""
    students = get_all_students()
    stats = get_registry_stats()
    return render_template('students.html', students=students, stats=stats)


# ─── API ENDPOINTS ──────────────────────────────────────────────────────

@app.route('/api/session/create', methods=['POST'])
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
def api_close_session(session_id):
    """
    Close an attendance session.
    After closing, mark absent all registered students who were required but didn't scan.
    """
    # Get session before closing so we have the filter info
    session = get_session(session_id)
    if not session:
        return jsonify({'success': False, 'message': 'Session not found.'})

    # Close session (sets partial fines for Time-In-only students)
    success, message = close_session(session_id)
    if not success:
        return jsonify({'success': False, 'message': message})

    # Re-fetch session after close to get updated scanned_students
    session = get_session(session_id)

    # Determine required students
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
def api_session_stats(session_id):
    """Get statistics for a session."""
    stats = get_session_stats(session_id)
    session = get_session(session_id)
    return jsonify({'success': True, 'stats': stats, 'session': session})


@app.route('/api/scan', methods=['POST'])
def api_scan_qr():
    """
    Process a scanned QR code.
    Validates session, decrypts QR, checks for duplicates, and logs attendance.
    Applies late fine if scanned > LATE_THRESHOLD_MINUTES after session start.
    """
    data = request.get_json()
    qr_content = data.get('qr_data', '')
    session_id = data.get('session_id', '')

    # Validate session
    if not session_id:
        return jsonify({
            'success': False,
            'error': 'no_session',
            'message': 'No active session selected. Please select or create a session first.'
        })

    is_valid, msg = validate_session(session_id)
    if not is_valid:
        return jsonify({
            'success': False,
            'error': 'invalid_session',
            'message': msg
        })

    # Decrypt QR data
    student_data = decrypt_qr_data(qr_content)
    if not student_data:
        return jsonify({
            'success': False,
            'error': 'invalid_qr',
            'message': 'Invalid or tampered QR code. Could not decrypt data.'
        })

    # Check required fields
    required_fields = ['name', 'student_number', 'course', 'year', 'section']
    for field in required_fields:
        if field not in student_data:
            return jsonify({
                'success': False,
                'error': 'invalid_qr',
                'message': f'QR code is missing required field: {field}'
            })

    # Check if student is included in session (course/year/section filter)
    session = get_session(session_id)
    if session:
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
            not_included_reasons.append(f"year level (you are {year_labels.get(student_year, student_year)} year; session is for {allowed} only)")
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

    # Auto-register student into registry if not already there
    register_student(student_data)

    # Record scan (Time In / Time Out logic) + fine calculation
    success, scan_msg, scan_type, fine, fine_reason = record_student_scan(
        session_id, student_data['student_number']
    )
    if not success:
        return jsonify({
            'success': False,
            'error': 'duplicate',
            'message': f"{student_data['name']} ({student_data['student_number']}) - {scan_msg}",
            'student': student_data
        })

    # Determine status label
    status = 'Time In' if scan_type == 'time_in' else 'Time Out'

    # Log to Excel with fine info
    log_success = log_attendance(student_data, session_id, status=status,
                                 fine=fine, fine_reason=fine_reason)

    if not log_success:
        return jsonify({
            'success': False,
            'error': 'log_error',
            'message': 'Failed to log attendance to Excel file.'
        })

    # Get updated session stats
    session = get_session(session_id)

    fine_msg = f' | Fine: ₱{fine} ({fine_reason})' if fine else ''
    return jsonify({
        'success': True,
        'message': f"{student_data['name']} - {status} recorded!{fine_msg}",
        'student': student_data,
        'scan_type': scan_type,
        'status': status,
        'fine': fine,
        'fine_reason': fine_reason,
        'attendance_count': session['attendance_count'] if session else 0
    })


# ─── STUDENT REGISTRY API ──────────────────────────────────────────────

@app.route('/api/students', methods=['GET'])
def api_list_students():
    """List all registered students."""
    students = get_all_students()
    stats = get_registry_stats()
    return jsonify({'success': True, 'students': students, 'stats': stats})


@app.route('/api/students/register', methods=['POST'])
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
def api_register_student_qr():
    """
    Register a student by scanning their QR code.
    Decrypts the QR payload and adds the student to the registry.
    No active session is needed — this is registry-only.
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

        # Find headers
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
def api_delete_student(student_number):
    """Delete a student from the registry."""
    success = delete_student(student_number)
    return jsonify({
        'success': success,
        'message': 'Student deleted.' if success else 'Student not found.'
    })


@app.route('/api/students/clear', methods=['DELETE'])
def api_clear_students():
    """Clear entire student registry."""
    count = clear_registry()
    return jsonify({'success': True, 'message': f'{count} students removed from registry.'})


# ─── QR GENERATION API ──────────────────────────────────────────────────

@app.route('/api/generate/single', methods=['POST'])
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

        # Auto-register into registry
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

        # Also register all students into registry
        # Read the Excel again for registration
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
        # Create empty Excel export when no records
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
    from openpyxl.styles import Font, Alignment, PatternFill

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

    for r in records:
        # Re-sort 'status' and fine logic to highlight Fines (Late/Absent/Partial) or Presents
        # Actually just dumping what's there
        ws.append([
            r['datetime'],
            r['name'],
            r['student_number'],
            r['course'],
            r['year'],
            r['section'],
            r['session_id'],
            r['status'],
            r['fine'] if r['fine'] else 0,
            r.get('fine_reason', '')
        ])

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
def api_list_qrcodes():
    """List all generated QR code files."""
    qr_files = []
    if os.path.exists(QR_CODES_DIR):
        qr_files = [f for f in os.listdir(QR_CODES_DIR) if f.endswith('.png')]
    return jsonify({'success': True, 'files': qr_files})


@app.route('/api/qrcodes/clear', methods=['DELETE'])
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
def api_download_all_qrcodes():
    """Download all generated QR codes as a single ZIP file."""
    try:
        qr_files = []
        if os.path.exists(QR_CODES_DIR):
            qr_files = [f for f in os.listdir(QR_CODES_DIR) if f.endswith('.png')]

        if not qr_files:
            return jsonify({'success': False, 'message': 'No QR codes to download.'}), 404

        # Create ZIP in memory
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

def start_ngrok(port):
    """Start an ngrok tunnel for mobile access over HTTPS."""
    try:
        from pyngrok import ngrok
        public_url = ngrok.connect(port, "http").public_url
        print("\n" + "*" * 60)
        print("  NGROK TUNNEL ACTIVE")
        print(f"  Public URL: {public_url}")
        https_url = public_url.replace("http://", "https://")
        if public_url != https_url:
            print(f"  HTTPS URL:  {https_url}")
        print("  Use this URL on your phone to access the system")
        print("*" * 60 + "\n")
        return public_url
    except ImportError:
        print("  [!] pyngrok not installed. Run: pip install pyngrok")
        return None
    except Exception as e:
        print(f"  [!] ngrok failed to start: {e}")
        print("  [!] Make sure you've set your authtoken:")
        print("      ngrok config add-authtoken YOUR_TOKEN")
        return None


USE_NGROK = os.environ.get('USE_NGROK', '1') == '1'

if __name__ == '__main__':
    port = 5000
    print("\n" + "=" * 60)
    print("  QR Attendance System")
    print(f"  Local URL:   http://127.0.0.1:{port}")
    print("=" * 60)

    if USE_NGROK:
        start_ngrok(port)
    else:
        print("  Set USE_NGROK=1 to enable ngrok tunnel for mobile\n")

    app.run(debug=True, host='0.0.0.0', port=port, use_reloader=False)
