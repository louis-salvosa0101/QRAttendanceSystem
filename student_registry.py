"""
Student Registry module.
Stores all registered students in SQLite so the system can:
  - Mark absent students when a session closes
  - Apply fines correctly
  - Filter required school year / courses per session
"""
from db import get_db, _row_to_dict


def register_student(student_data: dict) -> bool:
    """
    Add or update a student in the registry.
    student_data must have: name, student_number, course, year, section
    Returns True if new, False if updated.
    """
    student_number = str(student_data.get('student_number', '')).strip()
    if not student_number:
        return False

    with get_db() as conn:
        cursor = conn.execute(
            "SELECT student_number FROM students WHERE student_number = ?",
            (student_number,)
        )
        existing = cursor.fetchone()
        is_new = existing is None

        conn.execute(
            """
            INSERT INTO students (student_number, name, course, year, section)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(student_number) DO UPDATE SET
                name = excluded.name,
                course = excluded.course,
                year = excluded.year,
                section = excluded.section
            """,
            (
                student_number,
                str(student_data.get('name', '')).strip(),
                str(student_data.get('course', '')).strip(),
                str(student_data.get('year', '')).strip(),
                str(student_data.get('section', '')).strip(),
            ),
        )
    return is_new


def register_students_bulk(students: list) -> dict:
    """
    Register multiple students at once.
    Returns dict with 'added' and 'updated' counts.
    """
    counts = {'added': 0, 'updated': 0}
    for student in students:
        is_new = register_student(student)
        if is_new:
            counts['added'] += 1
        else:
            counts['updated'] += 1
    return counts


def get_all_students() -> list:
    """Return all registered students as a list of dicts."""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT student_number, name, course, year, section FROM students ORDER BY student_number"
        )
        rows = cursor.fetchall()
    return [dict(r) for r in rows]


def get_student(student_number: str) -> dict | None:
    """Get a single student by student number."""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT student_number, name, course, year, section FROM students WHERE student_number = ?",
            (str(student_number),)
        )
        row = cursor.fetchone()
    return _row_to_dict(row)


def get_students_by_filter(course: str = None,
                            year: list = None, section: str = None) -> list:
    """
    Return students matching optional filters.
    Used to determine who should attend a session.
    `year` should be a list of year strings, e.g. ['1', '2']
    """
    students = get_all_students()
    result = []
    for s in students:
        if course and s.get('course') != course:
            continue
        if year and isinstance(year, list) and len(year) > 0 and s.get('year') not in year:
            continue
        if section and s.get('section') != section:
            continue
        result.append(s)
    return result


def delete_student(student_number: str) -> bool:
    """Delete a student from the registry."""
    with get_db() as conn:
        cursor = conn.execute(
            "DELETE FROM students WHERE student_number = ?",
            (str(student_number),)
        )
        return cursor.rowcount > 0


def clear_registry() -> int:
    """Delete all students from registry. Returns count deleted."""
    with get_db() as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM students")
        count = cursor.fetchone()[0]
        conn.execute("DELETE FROM students")
    return count


def get_registry_stats() -> dict:
    """Get summary statistics of the registry."""
    students = get_all_students()
    courses = {}
    for s in students:
        c = s.get('course') or 'Unknown'
        courses[c] = courses.get(c, 0) + 1
    return {
        'total': len(students),
        'by_course': courses,
    }
