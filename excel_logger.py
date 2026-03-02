"""
Excel logging module for attendance records.
Creates organized spreadsheets with daily/session sheets and summary statistics.
"""
import os
from datetime import datetime
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from config import ATTENDANCE_LOG_FILE, EXCEL_DIR


# Style constants
HEADER_FONT = Font(name='Calibri', bold=True, size=12, color='FFFFFF')
HEADER_FILL = PatternFill(start_color='1a1a2e', end_color='1a1a2e', fill_type='solid')
ACCENT_FILL = PatternFill(start_color='16213e', end_color='16213e', fill_type='solid')
SUCCESS_FILL = PatternFill(start_color='d4edda', end_color='d4edda', fill_type='solid')
TIMEOUT_FILL = PatternFill(start_color='cce5ff', end_color='cce5ff', fill_type='solid')
HEADER_ALIGNMENT = Alignment(horizontal='center', vertical='center', wrap_text=True)
THIN_BORDER = Border(
    left=Side(style='thin', color='cccccc'),
    right=Side(style='thin', color='cccccc'),
    top=Side(style='thin', color='cccccc'),
    bottom=Side(style='thin', color='cccccc'),
)

ATTENDANCE_HEADERS = [
    'Date & Time',
    'Student Name',
    'Student Number',
    'Course',
    'Year',
    'Section',
    'Session ID',
    'Status'
]

COLUMN_WIDTHS = [22, 30, 20, 15, 8, 10, 15, 15]


def _get_or_create_workbook(filepath: str = None) -> tuple:
    """Get existing workbook or create a new one."""
    if filepath is None:
        filepath = ATTENDANCE_LOG_FILE

    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    if os.path.exists(filepath):
        wb = load_workbook(filepath)
    else:
        wb = Workbook()
        # Remove default sheet
        if 'Sheet' in wb.sheetnames:
            del wb['Sheet']

    return wb, filepath


def _style_header_row(ws, headers, widths):
    """Apply styling to the header row."""
    for col_idx, (header, width) in enumerate(zip(headers, widths), 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = HEADER_ALIGNMENT
        cell.border = THIN_BORDER
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"


def _get_session_sheet_name(session_id: str) -> str:
    """Generate a sheet name for a session."""
    today = datetime.now().strftime('%Y-%m-%d')
    name = f"{today}_{session_id}"
    # Excel sheet names max 31 chars
    return name[:31]


def log_attendance(student_data: dict, session_id: str, status: str = "Present") -> bool:
    """
    Log a single attendance record.
    Creates a new sheet for each session automatically.
    """
    wb, filepath = _get_or_create_workbook()
    try:
        sheet_name = _get_session_sheet_name(session_id)

        # Create or get session sheet
        if sheet_name not in wb.sheetnames:
            ws = wb.create_sheet(title=sheet_name)
            _style_header_row(ws, ATTENDANCE_HEADERS, COLUMN_WIDTHS)
        else:
            ws = wb[sheet_name]

        # Add record
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        row_data = [
            now,
            student_data.get('name', ''),
            student_data.get('student_number', ''),
            student_data.get('course', ''),
            student_data.get('year', ''),
            student_data.get('section', ''),
            session_id,
            status
        ]

        next_row = ws.max_row + 1
        for col_idx, value in enumerate(row_data, 1):
            cell = ws.cell(row=next_row, column=col_idx, value=value)
            cell.border = THIN_BORDER
            cell.alignment = Alignment(horizontal='center', vertical='center')
            if status == "Time In":
                cell.fill = SUCCESS_FILL
            elif status == "Time Out":
                cell.fill = TIMEOUT_FILL

        wb.save(filepath)
        return True

    except Exception as e:
        print(f"Error logging attendance: {e}")
        return False
    finally:
        wb.close()


def generate_summary_sheet(filepath: str = None) -> bool:
    """
    Generate or update a summary sheet with total attendance per student.
    """
    wb, filepath = _get_or_create_workbook(filepath)
    try:
        # Collect all attendance data
        student_records = {}

        for sheet_name in wb.sheetnames:
            if sheet_name == 'Summary':
                continue
            ws = wb[sheet_name]
            for row in ws.iter_rows(min_row=2, values_only=True):
                if row and row[2]:  # Student Number exists
                    student_num = str(row[2])
                    if student_num not in student_records:
                        student_records[student_num] = {
                            'name': row[1],
                            'student_number': student_num,
                            'course': row[3],
                            'year': row[4],
                            'section': row[5],
                            'total_sessions': 0,
                            'sessions_attended': []
                        }
                    if row[6] not in student_records[student_num]['sessions_attended']:
                        student_records[student_num]['sessions_attended'].append(row[6])
                        student_records[student_num]['total_sessions'] += 1

        # Create or recreate summary sheet
        if 'Summary' in wb.sheetnames:
            del wb['Summary']

        ws = wb.create_sheet(title='Summary', index=0)

        summary_headers = [
            'Student Name', 'Student Number', 'Course', 'Year', 'Section',
            'Total Sessions Attended', 'Sessions List'
        ]
        summary_widths = [30, 20, 15, 8, 10, 22, 50]
        _style_header_row(ws, summary_headers, summary_widths)

        for idx, (student_num, data) in enumerate(sorted(student_records.items()), 2):
            row_data = [
                data['name'],
                data['student_number'],
                data['course'],
                data['year'],
                data['section'],
                data['total_sessions'],
                ', '.join(str(s) for s in data['sessions_attended'])
            ]
            for col_idx, value in enumerate(row_data, 1):
                cell = ws.cell(row=idx, column=col_idx, value=value)
                cell.border = THIN_BORDER
                cell.alignment = Alignment(horizontal='center', vertical='center')

        wb.save(filepath)
        return True

    except Exception as e:
        print(f"Error generating summary: {e}")
        return False
    finally:
        wb.close()


def get_attendance_records(session_id: str = None, student_number: str = None,
                           date_from: str = None, date_to: str = None) -> list:
    """
    Retrieve attendance records with optional filters.
    """
    records = []
    if not os.path.exists(ATTENDANCE_LOG_FILE):
        return records

    wb = load_workbook(ATTENDANCE_LOG_FILE)
    try:
        for sheet_name in wb.sheetnames:
            if sheet_name == 'Summary':
                continue
            ws = wb[sheet_name]
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row or not row[0]:
                    continue

                record = {
                    'datetime': str(row[0]),
                    'name': row[1],
                    'student_number': str(row[2]) if row[2] else '',
                    'course': row[3],
                    'year': row[4],
                    'section': row[5],
                    'session_id': row[6],
                    'status': row[7]
                }

                # Apply filters
                if session_id and record['session_id'] != session_id:
                    continue
                if student_number and record['student_number'] != student_number:
                    continue
                if date_from:
                    rec_date = record['datetime'][:10]
                    if rec_date < date_from:
                        continue
                if date_to:
                    rec_date = record['datetime'][:10]
                    if rec_date > date_to:
                        continue

                records.append(record)
    except Exception as e:
        print(f"Error retrieving records: {e}")
    finally:
        wb.close()

    return records


def get_session_stats(session_id: str) -> dict:
    """Get attendance statistics for a specific session."""
    records = get_attendance_records(session_id=session_id)
    courses = {}
    time_in_count = 0
    time_out_count = 0
    for r in records:
        key = f"{r['course']} {r['year']}-{r['section']}"
        courses[key] = courses.get(key, 0) + 1
        if r.get('status') == 'Time In':
            time_in_count += 1
        elif r.get('status') == 'Time Out':
            time_out_count += 1

    return {
        'total_present': len(records),
        'time_in_count': time_in_count,
        'time_out_count': time_out_count,
        'by_course': courses,
        'records': records
    }


def create_sample_master_list(filepath: str = None) -> str:
    """
    Create a sample Excel master list with student data for testing.
    """
    if filepath is None:
        filepath = os.path.join(EXCEL_DIR, 'sample_master_list.xlsx')

    wb = Workbook()
    ws = wb.active
    ws.title = "Students"

    headers = ['Name', 'Student Number', 'Course', 'Year', 'Section']
    widths = [30, 20, 15, 8, 10]
    _style_header_row(ws, headers, widths)
    try:
        ws = wb.active
        ws.title = "Students"

        headers = ['Name', 'Student Number', 'Course', 'Year', 'Section']
        widths = [30, 20, 15, 8, 10]
        _style_header_row(ws, headers, widths)

        sample_students = [
            ['Juan Dela Cruz', '2024-00001', 'BSCS', '3', 'A'],
            ['Maria Santos', '2024-00002', 'BSCS', '3', 'A'],
            ['Jose Rizal Jr.', '2024-00003', 'BSIT', '2', 'B'],
            ['Ana Reyes', '2024-00004', 'BSIT', '2', 'B'],
            ['Carlos Garcia', '2024-00005', 'BSCS', '1', 'A'],
            ['Elena Cruz', '2024-00006', 'BSCE', '4', 'A'],
            ['Miguel Torres', '2024-00007', 'BSCS', '3', 'B'],
            ['Sofia Bautista', '2024-00008', 'BSIT', '1', 'A'],
            ['Rafael Mendoza', '2024-00009', 'BSCS', '2', 'A'],
            ['Isabella Flores', '2024-00010', 'BSCE', '3', 'A'],
        ]

        for row_idx, student in enumerate(sample_students, 2):
            for col_idx, value in enumerate(student, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.border = THIN_BORDER
                cell.alignment = Alignment(horizontal='center', vertical='center')

        wb.save(filepath)
    finally:
        wb.close()
    return filepath
