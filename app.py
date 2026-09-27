import os
import uuid
from datetime import datetime
from functools import wraps

from dotenv import load_dotenv

load_dotenv()

import mysql.connector
from mysql.connector import Error
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, send_from_directory
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "stbcet-hostelcare-change-me")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "stbcet_hostel"),
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_ROOT = os.path.join(BASE_DIR, "static", "uploads")
COMPLAINT_UPLOAD = os.path.join(UPLOAD_ROOT, "complaints")
MAINTENANCE_UPLOAD = os.path.join(UPLOAD_ROOT, "maintenance")
os.makedirs(COMPLAINT_UPLOAD, exist_ok=True)
os.makedirs(MAINTENANCE_UPLOAD, exist_ok=True)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE


def db():
    return mysql.connector.connect(**DB_CONFIG)


def query(sql, params=(), fetchone=False, commit=False):
    conn = db()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, params)
        result = cur.fetchone() if fetchone else cur.fetchall()
        if commit:
            conn.commit()
        return result
    finally:
        cur.close()
        conn.close()


def execute(sql, params=()):
    conn = db()
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        conn.commit()
        return cur.lastrowid
    finally:
        cur.close()
        conn.close()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(file_obj, folder):
    if not file_obj or not file_obj.filename:
        return None
    if not allowed_file(file_obj.filename):
        raise ValueError("Only JPG, JPEG, PNG and WEBP images are allowed.")
    filename = secure_filename(file_obj.filename)
    ext = filename.rsplit(".", 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    path = os.path.join(folder, unique_name)
    file_obj.save(path)
    return unique_name


def login_required(role=None):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in first.", "warning")
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                flash("You are not authorized to access this page.", "danger")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


def add_history(complaint_id, new_status, remarks=""):
    complaint = query(
        "SELECT status FROM complaints WHERE id=%s",
        (complaint_id,), fetchone=True
    )
    old_status = complaint["status"] if complaint else None
    execute(
        """INSERT INTO complaint_history
           (complaint_id, changed_by, old_status, new_status, remarks)
           VALUES (%s,%s,%s,%s,%s)""",
        (complaint_id, session.get("user_id"), old_status, new_status, remarks)
    )


def ensure_user_profile_columns():
    """Ensure existing databases also have hostel and room fields."""
    conn = None
    cur = None
    try:
        conn = db()
        cur = conn.cursor()
        for column, definition in (("hostel_block", "VARCHAR(80) NULL"), ("room_number", "VARCHAR(30) NULL")):
            cur.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA=%s AND TABLE_NAME='users' AND COLUMN_NAME=%s
            """, (DB_CONFIG["database"], column))
            if cur.fetchone()[0] == 0:
                cur.execute(f"ALTER TABLE users ADD COLUMN {column} {definition}")
        conn.commit()
    except Error as e:
        print("User profile schema warning:", e)
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def ensure_default_admin():
    try:
        existing = query(
            "SELECT id FROM users WHERE role='admin' LIMIT 1",
            fetchone=True
        )
        if not existing:
            execute(
                """INSERT INTO users
                   (full_name,email,password_hash,role,approved)
                   VALUES (%s,%s,%s,'admin',1)""",
                (
                    "STBCET Administrator",
                    "admin@stbcet.edu.in",
                    generate_password_hash("Admin@STBCET2026")
                )
            )
            print("Default admin created:")
            print("Email: admin@stbcet.edu.in")
            print("Password: Admin@STBCET2026")
    except Error as e:
        print("Database initialization warning:", e)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        hostel = request.form.get("hostel_block", "").strip()
        room = request.form.get("room_number", "").strip()
        password = request.form.get("password", "")

        if not all([name, email, hostel, room, password]):
            flash("Please fill all required fields.", "danger")
            return render_template("register.html")

        exists = query("SELECT id FROM users WHERE email=%s", (email,), fetchone=True)
        if exists:
            flash("Email is already registered.", "warning")
            return render_template("register.html")

        execute(
            """INSERT INTO users
               (full_name,email,password_hash,role,approved,phone,hostel_block,room_number)
               VALUES (%s,%s,%s,'student',0,%s,%s,%s)""",
            (name, email, generate_password_hash(password), phone, hostel, room)
        )
        flash("Registration submitted. Wait for admin approval before logging in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = query("SELECT * FROM users WHERE email=%s", (email,), fetchone=True)
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "danger")
            return render_template("login.html")

        if user["role"] == "student" and not user["approved"]:
            flash("Your student account is waiting for admin approval.", "warning")
            return render_template("login.html")

        session.clear()
        session["user_id"] = user["id"]
        session["name"] = user["full_name"]
        session["role"] = user["role"]

        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required()
def dashboard():
    role = session["role"]
    if role == "student":
        return redirect(url_for("student_dashboard"))
    if role == "admin":
        return redirect(url_for("admin_dashboard"))
    return redirect(url_for("staff_dashboard"))


@app.route("/student/dashboard")
@login_required("student")
def student_dashboard():
    complaints = query(
        """SELECT c.*, s.full_name AS staff_name
           FROM complaints c
           LEFT JOIN users s ON c.assigned_staff_id=s.id
           WHERE c.student_id=%s
           ORDER BY c.created_at DESC""",
        (session["user_id"],)
    )
    return render_template("student_dashboard.html", complaints=complaints)


@app.route("/student/complaint/new", methods=["GET", "POST"])
@login_required("student")
def new_complaint():
    if request.method == "POST":
        category = request.form.get("category", "").strip()
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        block = request.form.get("hostel_block", "").strip()
        room = request.form.get("room_number", "").strip()
        priority = request.form.get("priority", "Medium")
        photo = request.files.get("complaint_photo")

        if not all([category, title, description, block, room]):
            flash("Please fill all required fields.", "danger")
            return render_template("new_complaint.html")

        try:
            filename = save_upload(photo, COMPLAINT_UPLOAD)
        except ValueError as e:
            flash(str(e), "danger")
            return render_template("new_complaint.html")

        complaint_id = execute(
            """INSERT INTO complaints
               (student_id,category,title,description,hostel_block,room_number,
                priority,complaint_photo,status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'Pending')""",
            (
                session["user_id"], category, title, description,
                block, room, priority, filename
            )
        )
        add_history(complaint_id, "Pending", "Complaint submitted by student.")
        flash(f"Complaint #{complaint_id} submitted successfully.", "success")
        return redirect(url_for("student_dashboard"))

    return render_template("new_complaint.html")


@app.route("/student/complaint/<int:complaint_id>")
@login_required("student")
def student_complaint_detail(complaint_id):
    complaint = query(
        """SELECT c.*, s.full_name AS staff_name
           FROM complaints c
           LEFT JOIN users s ON c.assigned_staff_id=s.id
           WHERE c.id=%s AND c.student_id=%s""",
        (complaint_id, session["user_id"]), fetchone=True
    )
    if not complaint:
        flash("Complaint not found.", "danger")
        return redirect(url_for("student_dashboard"))

    history = query(
        """SELECT h.*, u.full_name AS changed_by_name
           FROM complaint_history h
           LEFT JOIN users u ON h.changed_by=u.id
           WHERE h.complaint_id=%s
           ORDER BY h.created_at ASC""",
        (complaint_id,)
    )
    return render_template(
        "student_complaint_detail.html",
        complaint=complaint,
        history=history
    )


@app.route("/admin")
@login_required("admin")
def admin_dashboard():
    # Summary cards
    # Keep these as separate variables as well as inside the stats dictionary.
    # This makes the values explicit and avoids template-key mismatches.
    students_total = query(
        "SELECT COUNT(*) AS n FROM users WHERE role='student'",
        fetchone=True
    )["n"] or 0

    students_approved = query(
        "SELECT COUNT(*) AS n FROM users WHERE role='student' AND approved=1",
        fetchone=True
    )["n"] or 0

    students_pending = query(
        "SELECT COUNT(*) AS n FROM users WHERE role='student' AND approved=0",
        fetchone=True
    )["n"] or 0

    complaints_total = query(
        "SELECT COUNT(*) AS n FROM complaints",
        fetchone=True
    )["n"] or 0

    work_completed = query(
        "SELECT COUNT(*) AS n FROM complaints WHERE status='Work Completed'",
        fetchone=True
    )["n"] or 0

    closed_complaints = query(
        "SELECT COUNT(*) AS n FROM complaints WHERE status='Closed'",
        fetchone=True
    )["n"] or 0

    stats = {
        "students_total": students_total,
        "students_approved": students_approved,
        "students_pending": students_pending,
        "complaints": complaints_total,
        "work_completed": work_completed,
        "closed": closed_complaints,
    }

    # Chart data
    student_monthly = query(
        """SELECT DATE_FORMAT(created_at, '%Y-%m') AS month_key,
                  DATE_FORMAT(created_at, '%b %Y') AS month_label,
                  COUNT(*) AS total
           FROM users
           WHERE role='student'
           GROUP BY DATE_FORMAT(created_at, '%Y-%m'),
                    DATE_FORMAT(created_at, '%b %Y')
           ORDER BY month_key ASC"""
    )

    complaint_status = query(
        """SELECT status, COUNT(*) AS total
           FROM complaints
           GROUP BY status
           ORDER BY total DESC"""
    )

    complaint_category = query(
        """SELECT category, COUNT(*) AS total
           FROM complaints
           GROUP BY category
           ORDER BY total DESC"""
    )

    complaints_monthly = query(
        """SELECT DATE_FORMAT(created_at, '%Y-%m') AS month_key,
                  DATE_FORMAT(created_at, '%b %Y') AS month_label,
                  COUNT(*) AS total
           FROM complaints
           GROUP BY DATE_FORMAT(created_at, '%Y-%m'),
                    DATE_FORMAT(created_at, '%b %Y')
           ORDER BY month_key ASC"""
    )

    complaints = query(
        """SELECT c.*, st.full_name AS student_name,
                  ms.full_name AS staff_name
           FROM complaints c
           JOIN users st ON c.student_id=st.id
           LEFT JOIN users ms ON c.assigned_staff_id=ms.id
           ORDER BY c.created_at DESC"""
    )

    pending_students = query(
        """SELECT id, full_name, email, phone, created_at
           FROM users
           WHERE role='student' AND approved=0
           ORDER BY created_at DESC"""
    )

    staff = query(
        """SELECT id, full_name, email, phone
           FROM users
           WHERE role='staff'
           ORDER BY full_name"""
    )

    return render_template(
        "admin_dashboard.html",
        stats=stats,
        # Explicit scalar values for the dashboard cards.
        students_total=students_total,
        students_approved=students_approved,
        students_pending=students_pending,
        complaints_total=complaints_total,
        closed_complaints=closed_complaints,
        complaints=complaints,
        pending_students=pending_students,
        staff=staff,
        student_monthly=student_monthly,
        complaint_status=complaint_status,
        complaint_category=complaint_category,
        complaints_monthly=complaints_monthly
    )


@app.post("/admin/student/<int:user_id>/approve")
@login_required("admin")
def approve_student(user_id):
    execute(
        "UPDATE users SET approved=1 WHERE id=%s AND role='student'",
        (user_id,)
    )
    flash("Student approved.", "success")
    return redirect(url_for("admin_dashboard"))


@app.post("/admin/student/<int:user_id>/reject")
@login_required("admin")
def reject_student(user_id):
    execute(
        "DELETE FROM users WHERE id=%s AND role='student' AND approved=0",
        (user_id,)
    )
    flash("Student registration rejected.", "success")
    return redirect(url_for("admin_dashboard"))


@app.post("/admin/staff/add")
@login_required("admin")
def add_staff():
    name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    password = request.form.get("password", "")

    if not all([name, email, password]):
        flash("Staff name, email and password are required.", "danger")
        return redirect(url_for("admin_dashboard"))

    if query("SELECT id FROM users WHERE email=%s", (email,), fetchone=True):
        flash("Email already exists.", "warning")
        return redirect(url_for("admin_dashboard"))

    execute(
        """INSERT INTO users
           (full_name,email,password_hash,role,approved,phone)
           VALUES (%s,%s,%s,'staff',1,%s)""",
        (name, email, generate_password_hash(password), phone)
    )
    flash("Maintenance staff account created.", "success")
    return redirect(url_for("admin_dashboard"))


@app.post("/admin/complaint/<int:complaint_id>/assign")
@login_required("admin")
def assign_complaint(complaint_id):
    staff_id = request.form.get("staff_id")
    if not staff_id:
        flash("Select a maintenance staff member.", "danger")
        return redirect(url_for("admin_dashboard"))

    valid_staff = query(
        "SELECT id FROM users WHERE id=%s AND role='staff'",
        (staff_id,), fetchone=True
    )
    if not valid_staff:
        flash("Invalid staff member.", "danger")
        return redirect(url_for("admin_dashboard"))

    execute(
        """UPDATE complaints
           SET assigned_staff_id=%s,status='Assigned'
           WHERE id=%s""",
        (staff_id, complaint_id)
    )
    add_history(complaint_id, "Assigned", "Complaint assigned by admin.")
    flash("Complaint assigned to maintenance staff.", "success")
    return redirect(url_for("admin_dashboard"))


@app.post("/admin/complaint/<int:complaint_id>/verify")
@login_required("admin")
def verify_complaint(complaint_id):
    complaint = query(
        "SELECT status FROM complaints WHERE id=%s",
        (complaint_id,), fetchone=True
    )
    if not complaint:
        flash("Complaint not found.", "danger")
        return redirect(url_for("admin_dashboard"))

    execute(
        """UPDATE complaints
           SET verification_status='Verified',
               status='Closed',
               verified_at=NOW()
           WHERE id=%s""",
        (complaint_id,)
    )
    add_history(complaint_id, "Closed", "Admin verified work completion.")
    flash("Work verified and complaint closed.", "success")
    return redirect(url_for("admin_dashboard"))


@app.post("/admin/complaint/<int:complaint_id>/rework")
@login_required("admin")
def request_rework(complaint_id):
    remarks = request.form.get("remarks", "").strip()
    execute(
        """UPDATE complaints
           SET verification_status='Rejected',status='Rework',
               admin_remarks=%s
           WHERE id=%s""",
        (remarks, complaint_id)
    )
    add_history(complaint_id, "Rework", remarks or "Admin requested rework.")
    flash("Complaint sent back to maintenance staff for rework.", "warning")
    return redirect(url_for("admin_dashboard"))


@app.route("/staff")
@login_required("staff")
def staff_dashboard():
    complaints = query(
        """SELECT c.*, st.full_name AS student_name, st.phone AS student_phone
           FROM complaints c
           JOIN users st ON c.student_id=st.id
           WHERE c.assigned_staff_id=%s
           ORDER BY c.created_at DESC""",
        (session["user_id"],)
    )
    return render_template("staff_dashboard.html", complaints=complaints)


@app.route("/staff/complaint/<int:complaint_id>/update", methods=["GET", "POST"])
@login_required("staff")
def staff_update(complaint_id):
    complaint = query(
        """SELECT c.*, st.full_name AS student_name, st.phone AS student_phone
           FROM complaints c
           JOIN users st ON c.student_id=st.id
           WHERE c.id=%s AND c.assigned_staff_id=%s""",
        (complaint_id, session["user_id"]), fetchone=True
    )
    if not complaint:
        flash("Complaint not found or not assigned to you.", "danger")
        return redirect(url_for("staff_dashboard"))

    if request.method == "POST":
        status = request.form.get("status", "In Progress")
        remarks = request.form.get("maintenance_remarks", "").strip()
        photo = request.files.get("maintenance_photo")

        allowed_statuses = {"In Progress", "Work Completed"}
        if status not in allowed_statuses:
            flash("Invalid status.", "danger")
            return render_template("staff_update.html", complaint=complaint)

        filename = complaint.get("maintenance_photo")
        if status == "Work Completed":
            if not photo or not photo.filename:
                flash("A work completion photo is required.", "danger")
                return render_template("staff_update.html", complaint=complaint)
            try:
                filename = save_upload(photo, MAINTENANCE_UPLOAD)
            except ValueError as e:
                flash(str(e), "danger")
                return render_template("staff_update.html", complaint=complaint)

        execute(
            """UPDATE complaints
               SET status=%s, maintenance_remarks=%s,
                   maintenance_photo=%s,
                   completed_at=CASE
                       WHEN %s='Work Completed' THEN NOW()
                       ELSE completed_at
                   END,
                   verification_status=CASE
                       WHEN %s='Work Completed' THEN 'Pending'
                       ELSE verification_status
                   END
               WHERE id=%s AND assigned_staff_id=%s""",
            (
                status, remarks, filename, status, status,
                complaint_id, session["user_id"]
            )
        )
        add_history(complaint_id, status, remarks)
        flash(
            "Work update saved. Admin can now verify the completion."
            if status == "Work Completed"
            else "Work progress updated.",
            "success"
        )
        return redirect(url_for("staff_dashboard"))

    return render_template("staff_update.html", complaint=complaint)


@app.route("/uploads/<folder>/<filename>")
def uploaded_file(folder, filename):
    if folder == "complaints":
        directory = COMPLAINT_UPLOAD
    elif folder == "maintenance":
        directory = MAINTENANCE_UPLOAD
    else:
        return "Not found", 404

    return send_from_directory(directory, filename)


@app.errorhandler(413)
def too_large(_):
    flash("Image is too large. Maximum size is 5 MB.", "danger")
    return redirect(request.referrer or url_for("dashboard"))


@app.errorhandler(Error)
def db_error(_):
    return "Database error. Check MySQL configuration and make sure the database exists.", 500


if __name__ == "__main__":
    try:
        ensure_user_profile_columns()
        ensure_default_admin()
    except Exception as e:
        print("Could not connect to MySQL.")
        print("Check DB_HOST, DB_PORT, DB_USER, DB_PASSWORD and DB_NAME.")
        print(e)
    app.run(debug=True)