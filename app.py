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
                    ATTENDANCE_LOG_FILE, SESSIONS_FILE)
from crypto_utils import decrypt_qr_data
from qr_generator import generate_single_qr, batch_generate_from_excel
from session_manager import (create_session, get_session, get_active_sessions,
                              get_all_sessions, validate_session,
                              record_student_scan, close_session)
from excel_logger import (log_attendance, generate_summary_sheet,
                           get_attendance_records, get_session_stats,
                           create_sample_master_list)

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
    return render_template('index.html',
                           active_sessions=active_sessions,
                           total_sessions=len(all_sessions))


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
    return render_template('sessions.html',
                           active_sessions=active_sessions,
                           all_sessions=all_sessions)


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


# ─── API ENDPOINTS ──────────────────────────────────────────────────────

@app.route('/api/session/create', methods=['POST'])
def api_create_session():
    """Create a new attendance session."""
    data = request.get_json()
    subject = data.get('subject', '')
    teacher = data.get('teacher', '')
    notes = data.get('notes', '')
    duration_hours = data.get('duration_hours')

    session = create_session(
        subject=subject,
        teacher=teacher,
        notes=notes,
        duration_hours=duration_hours
    )
    return jsonify({'success': True, 'session': session})


@app.route('/api/session/<session_id>/close', methods=['POST'])
def api_close_session(session_id):
    """Close an attendance session."""
    success, message = close_session(session_id)
    return jsonify({'success': success, 'message': message})


@app.route('/api/session/clear-history', methods=['DELETE'])
def api_clear_session_history():
    """Clear all session history."""
    try:
        if os.path.exists(SESSIONS_FILE):
            os.remove(SESSIONS_FILE)
            return jsonify({'success': True, 'message': 'Session history cleared successfully.'})
        return jsonify({'success': True, 'message': 'No session history to clear.'})
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

    # Record scan (Time In / Time Out logic)
    success, scan_msg, scan_type = record_student_scan(session_id, student_data['student_number'])
    if not success:
        return jsonify({
            'success': False,
            'error': 'duplicate',
            'message': f"⚠️ {student_data['name']} ({student_data['student_number']}) - {scan_msg}",
            'student': student_data
        })

    # Determine status label
    status = 'Time In' if scan_type == 'time_in' else 'Time Out'

    # Log to Excel
    log_success = log_attendance(student_data, session_id, status=status)

    if not log_success:
        return jsonify({
            'success': False,
            'error': 'log_error',
            'message': 'Failed to log attendance to Excel file.'
        })

    # Get updated session stats
    session = get_session(session_id)

    emoji = '📥' if scan_type == 'time_in' else '📤'
    return jsonify({
        'success': True,
        'message': f"{emoji} {student_data['name']} - {status} recorded!",
        'student': student_data,
        'scan_type': scan_type,
        'status': status,
        'attendance_count': session['attendance_count'] if session else 0
    })


@app.route('/api/generate/single', methods=['POST'])
def api_generate_single():
    """Generate a single QR code."""
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
    """Generate QR codes from an uploaded Excel file."""
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

        return jsonify({
            'success': True,
            'message': f"Generated {results['success']} QR codes with {results['errors']} errors.",
            'results': {
                'success': results['success'],
                'errors': results['errors'],
                'error_details': results['error_details']
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
    """Download the attendance Excel file."""
    if os.path.exists(ATTENDANCE_LOG_FILE):
        return send_file(ATTENDANCE_LOG_FILE, as_attachment=True,
                         download_name='attendance_records.xlsx')
    return jsonify({'success': False, 'message': 'No attendance records found.'})


@app.route('/api/records/reset', methods=['DELETE'])
def api_reset_records():
    """Reset all attendance records by deleting the Excel log."""
    import gc
    import time
    
    try:
        if not os.path.exists(ATTENDANCE_LOG_FILE):
            return jsonify({'success': True, 'message': 'No records to reset.'})
        
        # 1. Force Garbage Collection to release any hanging file handles
        gc.collect()
        
        # 2. Try to delete with a small retry loop
        max_retries = 3
        for i in range(max_retries):
            try:
                # Try to rename first (sometimes works when direct delete fails on Windows)
                temp_name = f"{ATTENDANCE_LOG_FILE}.old"
                if os.path.exists(temp_name):
                    os.remove(temp_name)
                
                os.rename(ATTENDANCE_LOG_FILE, temp_name)
                os.remove(temp_name)
                return jsonify({'success': True, 'message': 'Attendance records reset successfully.'})
            except (PermissionError, OSError):
                if i < max_retries - 1:
                    time.sleep(0.5)
                    gc.collect()
                    continue
                else:
                    raise
                    
    except PermissionError:
        return jsonify({
            'success': False, 
            'message': 'Permission Denied: The Excel file is locked by another process. Please close any open Excel windows and restart the app if the issue persists.'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error details: {str(e)}'})


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

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("  📋 QR Attendance System")
    print("  🌐 Open http://127.0.0.1:5000 in your browser")
    print("=" * 60 + "\n")
    # FOR MOBILE ACCESS
    app.run(debug=True, host='0.0.0.0', port=5000)

    # FOR LOCAL ACCESS
    #app.run(debug=True, host='127.0.0.1', port=5000)


