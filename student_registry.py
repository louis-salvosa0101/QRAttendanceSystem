"""
Student Registry module.
Stores all registered students in PostgreSQL (Supabase) so the system can:
  - Mark absent students when a session closes
  - Apply fines correctly
  - Filter required school year / courses per session
"""
from db import get_db, _cur


def register_student(student_data: dict, conn=None) -> bool:
    """
    Add or update a student in the registry.
    student_data must have: name, student_number, course, year, section
    If *conn* is provided the caller's connection is reused (no new pool checkout).
    Returns True if new, False if updated.
    """
    student_number = str(student_data.get('student_number', '')).strip()
    if not student_number:
        return False

    def _do(c):
        cur = _cur(c)
        cur.execute(
            "SELECT student_number FROM students WHERE student_number = %s",
            (student_number,)
        )
        existing = cur.fetchone()
        cur.execute(
            """
            INSERT INTO students (student_number, name, course, year, section)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT(student_number) DO UPDATE SET
                name = EXCLUDED.name,
                course = EXCLUDED.course,
                year = EXCLUDED.year,
                section = EXCLUDED.section
            """,
            (
                student_number,
                str(student_data.get('name', '')).strip(),
                str(student_data.get('course', '')).strip(),
                str(student_data.get('year', '')).strip(),
                str(student_data.get('section', '')).strip(),
            ),
        )
        return existing is None

    if conn is not None:
        return _do(conn)

    with get_db() as c:
        return _do(c)


def register_students_bulk(students: list) -> dict:
    """
    Register multiple students at once using a single DB connection.
    Returns dict with 'added' and 'updated' counts.
    """
    counts = {'added': 0, 'updated': 0}
    with get_db() as conn:
        for student in students:
            is_new = register_student(student, conn=conn)
            if is_new:
                counts['added'] += 1
            else:
                counts['updated'] += 1
    return counts


def get_all_students() -> list:
    """Return all registered students as a list of dicts."""
    with get_db() as conn:
        cur = _cur(conn)
        cur.execute(
            "SELECT student_number, name, course, year, section FROM students ORDER BY student_number"
        )
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_student(student_number: str) -> dict | None:
    """Get a single student by student number."""
    with get_db() as conn:
        cur = _cur(conn)
        cur.execute(
            "SELECT student_number, name, course, year, section FROM students WHERE student_number = %s",
            (str(student_number),)
        )
        row = cur.fetchone()
    return dict(row) if row else {}


def get_students_by_filter(course: str = None,
                            year: list = None, section: str = None) -> list:
    """
    Return students matching optional filters via SQL WHERE clause.
    Used to determine who should attend a session.
    `year` should be a list of year strings, e.g. ['1', '2']
    """
    conditions, params = [], []
    if course:
        conditions.append("course = %s")
        params.append(course)
    if year and isinstance(year, list) and len(year) > 0:
        conditions.append("year = ANY(%s)")
        params.append(year)
    if section:
        conditions.append("section = %s")
        params.append(section)
    where = " AND ".join(conditions) if conditions else "1=1"
    with get_db() as conn:
        cur = _cur(conn)
        cur.execute(
            f"SELECT student_number, name, course, year, section FROM students WHERE {where} ORDER BY student_number",
            params,
        )
        return [dict(r) for r in cur.fetchall()]


def search_students_by_last_name(
    query: str,
    limit: int = 25,
    *,
    allowed_numbers: list[str] | None = None,
    exclude_numbers: list[str] | None = None,
) -> list[dict]:
    """
    Search registry by last name (last whitespace-separated token in *name*)
    or by substring anywhere in the full name. Optional *allowed_numbers* restricts
    to that student_number set; *exclude_numbers* omits those numbers.
    """
    q = (query or '').strip()
    if not q:
        return []
    limit = max(1, min(int(limit or 25), 50))
    if allowed_numbers is not None and len(allowed_numbers) == 0:
        return []

    pattern = f'%{q.lower()}%'
    conditions = [
        "trim(COALESCE(name, '')) <> ''",
        """(
            lower(
                (string_to_array(trim(name), ' '))[
                    cardinality(string_to_array(trim(name), ' '))
                ]
            ) LIKE %s
            OR lower(trim(name)) LIKE %s
        )""",
    ]
    params = [pattern, pattern]

    if allowed_numbers is not None:
        conditions.append("student_number = ANY(%s)")
        params.append(allowed_numbers)
    if exclude_numbers:
        conditions.append("NOT (student_number = ANY(%s))")
        params.append(exclude_numbers)

    where_sql = " AND ".join(conditions)
    with get_db() as conn:
        cur = _cur(conn)
        cur.execute(
            f"""SELECT student_number, name, course, year, section
                FROM students WHERE {where_sql}
                ORDER BY name
                LIMIT %s""",
            (*params, limit),
        )
        return [dict(r) for r in cur.fetchall()]


def update_student(student_number: str, name: str = None, course: str = None,
                   year: str = None, section: str = None,
                   new_student_number: str = None) -> tuple:
    """
    Update a student's profile fields.  When *new_student_number* differs from
    the current one, cascade the change to every related table.
    Returns (success: bool, message: str).
    """
    with get_db() as conn:
        cur = _cur(conn)
        cur.execute("SELECT * FROM students WHERE student_number = %s",
                    (student_number,))
        existing = cur.fetchone()
        if not existing:
            return False, "Student not found."

        upd_name = name.strip() if name is not None else existing['name']
        upd_course = course.strip() if course is not None else existing['course']
        upd_year = year.strip() if year is not None else existing['year']
        upd_section = section.strip() if section is not None else existing['section']

        sn_changed = (new_student_number
                      and new_student_number.strip() != student_number)
        target_sn = new_student_number.strip() if sn_changed else student_number

        if sn_changed:
            cur.execute("SELECT 1 FROM students WHERE student_number = %s",
                        (target_sn,))
            if cur.fetchone():
                return False, f"Student number {target_sn} already exists."

            for tbl, col in [('attendance_records', 'student_number'),
                             ('session_scans', 'student_number'),
                             ('manual_fines', 'student_number'),
                             ('fine_payments', 'student_number')]:
                cur.execute(
                    f"UPDATE {tbl} SET {col} = %s WHERE {col} = %s",
                    (target_sn, student_number),
                )

        cur.execute(
            """UPDATE students
               SET student_number = %s, name = %s, course = %s,
                   year = %s, section = %s
               WHERE student_number = %s""",
            (target_sn, upd_name, upd_course, upd_year, upd_section,
             student_number),
        )

    return True, "Student profile updated."


def delete_student(student_number: str) -> bool:
    """Delete a student from the registry."""
    with get_db() as conn:
        cur = _cur(conn)
        cur.execute(
            "DELETE FROM students WHERE student_number = %s",
            (str(student_number),)
        )
        return cur.rowcount > 0


def clear_registry() -> int:
    """Delete all students from registry. Returns count deleted."""
    with get_db() as conn:
        cur = _cur(conn)
        cur.execute("SELECT COUNT(*) AS cnt FROM students")
        count = cur.fetchone()['cnt']
        cur.execute("DELETE FROM students")
    return count


def get_registry_stats() -> dict:
    """Get summary statistics of the registry using SQL aggregation."""
    with get_db() as conn:
        cur = _cur(conn)
        cur.execute("SELECT COUNT(*) AS total FROM students")
        total = cur.fetchone()['total']
        cur.execute(
            "SELECT COALESCE(NULLIF(course, ''), 'Unknown') AS course, COUNT(*) AS cnt "
            "FROM students GROUP BY COALESCE(NULLIF(course, ''), 'Unknown')"
        )
        by_course = {r['course']: r['cnt'] for r in cur.fetchall()}
    return {'total': total, 'by_course': by_course}
