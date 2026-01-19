import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash

# =========================
# APP CONFIG
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)
app.secret_key = "segak_secret_key"

DATABASE = os.path.join(BASE_DIR, "segak.db")

# =========================
# DATABASE CONNECTION
# =========================
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# =========================
# LOGIN
# =========================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()

        # ===== CHECK TEACHER =====
        teacher = conn.execute(
            "SELECT * FROM teacher WHERE email = ?",
            (email,)
        ).fetchone()

        if teacher and check_password_hash(teacher["password"], password):
            session.clear()
            session["user_id"] = teacher["teacher_id"]
            session["role"] = "teacher"
            conn.close()
            return redirect(url_for("dashboard"))

        # ===== CHECK STUDENT =====
        student = conn.execute(
            """
            SELECT su.*, s.name
            FROM student_user su
            JOIN student s ON su.student_id = s.student_id
            WHERE su.email = ?
            """,
            (email,)
        ).fetchone()

        if student and check_password_hash(student["password"], password):
            session.clear()
            session["user_id"] = student["student_id"]
            session["role"] = "student"
            conn.close()
            return redirect(url_for("student_dashboard"))

        conn.close()
        return render_template("login.html", error="Invalid email or password")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# =========================
# DASHBOARD
# =========================
@app.route("/dashboard")
def dashboard():
    if session.get("role") != "teacher":
        return redirect(url_for("login"))

    conn = get_db_connection()

    # ambil nama teacher
    teacher = conn.execute(
        "SELECT name FROM teacher WHERE teacher_id = ?",
        (session.get("user_id"),)
    ).fetchone()

    total_students = conn.execute("SELECT COUNT(*) FROM student").fetchone()[0]
    total_bmi = conn.execute("SELECT COUNT(*) FROM bmi_record").fetchone()[0]
    total_segak = conn.execute("SELECT COUNT(*) FROM segak_record").fetchone()[0]
    total_classes = conn.execute("SELECT COUNT(*) FROM class").fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        teacher_name=teacher["name"],
        total_students=total_students,
        total_bmi=total_bmi,
        total_segak=total_segak,
        total_classes=total_classes
    )

#student dashboard
@app.route("/student_dashboard")
def student_dashboard():
    if session.get("role") != "student":
        return redirect(url_for("login"))

    student_id = session.get("user_id")
    conn = get_db_connection()

    # info student
    student = conn.execute("""
        SELECT s.name, s.gender, s.age, c.class_name AS class
        FROM student s
        JOIN class c ON s.class_id = c.class_id
        WHERE s.student_id = ?
    """, (student_id,)).fetchone()

    # BMI records (student sendiri)
    bmi_records = conn.execute("""
        SELECT record_date, height, weight, bmi_value, bmi_status
        FROM bmi_record
        WHERE student_id = ?
        ORDER BY record_date DESC
    """, (student_id,)).fetchall()

    # SEGAK records (student sendiri)
    segak_records = conn.execute("""
        SELECT test_date, step_test, push_up, sit_up, sit_reach, fitness_level
        FROM segak_record
        WHERE student_id = ?
        ORDER BY test_date DESC
    """, (student_id,)).fetchall()

    conn.close()

    return render_template(
        "student_dashboard.html",
        student=student,
        bmi_records=bmi_records,
        segak_records=segak_records
    )


# =========================
# ADD STUDENT
# =========================
@app.route("/add_student", methods=["GET", "POST"])
def add_student():
    if session.get("role") != "teacher":
        return redirect(url_for("login"))

    conn = get_db_connection()

    classes = conn.execute(
        "SELECT class_id, class_name FROM class ORDER BY class_name"
    ).fetchall()

    if request.method == "POST":
        conn.execute(
            """
            INSERT INTO student (name, gender, age, class_id)
            VALUES (?, ?, ?, ?)
            """,
            (
                request.form["name"],
                request.form["gender"],
                request.form["age"],
                request.form["class_id"]
            )
        )
        conn.commit()
        conn.close()

        return render_template(
            "add_student.html",
            success="Student added successfully!",
            classes=classes
        )

    conn.close()
    return render_template("add_student.html", classes=classes)


# =========================
# STUDENT LIST
# =========================
@app.route("/students")
def students():
    if session.get("role") != "teacher":
        return redirect(url_for("login"))

    selected_class = request.args.get("class")
    conn = get_db_connection()

    classes = conn.execute(
        "SELECT class_name AS class FROM class ORDER BY class_name"
    ).fetchall()

    if selected_class:
        students = conn.execute(
            """
            SELECT s.student_id, s.name, s.gender, s.age,
                   c.class_name AS class
            FROM student s
            JOIN class c ON s.class_id = c.class_id
            WHERE c.class_name = ?
            ORDER BY s.name
            """,
            (selected_class,)
        ).fetchall()
    else:
        students = conn.execute(
            """
            SELECT s.student_id, s.name, s.gender, s.age,
                   c.class_name AS class
            FROM student s
            JOIN class c ON s.class_id = c.class_id
            ORDER BY c.class_name, s.name
            """
        ).fetchall()

    conn.close()

    return render_template(
        "student.html",
        students=students,
        classes=classes,
        selected_class=selected_class
    )

#edit student
@app.route("/edit_student/<int:student_id>", methods=["GET","POST"])
def edit_student(student_id):
    if session.get("role") != "teacher":
        return redirect(url_for("login"))


    conn = get_db_connection()
    student = conn.execute(
        "SELECT * FROM student WHERE student_id=?",(student_id,)
    ).fetchone()
    classes = conn.execute("SELECT * FROM class").fetchall()

    if request.method=="POST":
        conn.execute("""
        UPDATE student SET name=?,gender=?,age=?,class_id=?
        WHERE student_id=?
        """,(
            request.form["name"],
            request.form["gender"],
            request.form["age"],
            request.form["class_id"],
            student_id
        ))
        conn.commit()
        conn.close()
        return redirect(url_for("students"))

    conn.close()
    return render_template("edit_student.html",student=student,classes=classes)

#delete student
@app.route("/delete_student/<int:student_id>")
def delete_student(student_id):
    if session.get("role") != "teacher":
        return redirect(url_for("login"))


    conn = get_db_connection()
    conn.execute("DELETE FROM student WHERE student_id=?",(student_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("students"))



# =========================
# ADD BMI
# =========================
@app.route("/add_bmi", methods=["GET", "POST"])
def add_bmi():
    if session.get("role") != "teacher":
        return redirect(url_for("login"))

    conn = get_db_connection()

    # Ambil semua class (UNIQUE)
    classes = conn.execute(
        "SELECT class_name FROM class ORDER BY class_name"
    ).fetchall()

    # Ambil semua student (untuk JS filter)
    students = conn.execute(
        """
        SELECT s.student_id, s.name, s.gender,
               c.class_name AS class
        FROM student s
        JOIN class c ON s.class_id = c.class_id
        ORDER BY c.class_name, s.name
        """
    ).fetchall()

    if request.method == "POST":
        student_id = request.form["student_id"]
        height_cm = float(request.form["height"])
        weight = float(request.form["weight"])
        record_date = request.form["record_date"]

        height_m = height_cm / 100
        bmi = round(weight / (height_m * height_m), 2)

        if bmi < 18.5:
            status = "Underweight"
        elif bmi < 25:
            status = "Normal"
        elif bmi < 30:
            status = "Overweight"
        else:
            status = "Obese"

        conn.execute(
            """
            INSERT INTO bmi_record
            (student_id, height, weight, bmi_value, bmi_status, record_date)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (student_id, height_m, weight, bmi, status, record_date)
        )
        conn.commit()
        conn.close()

        return redirect(url_for("bmi_records"))

    conn.close()
    return render_template(
        "add_bmi.html",
        classes=classes,
        students=students
    )


# =========================
# BMI RECORDS
# =========================
@app.route("/bmi_records")
def bmi_records():
    if session.get("role") != "teacher":
        return redirect(url_for("login"))

    selected_class = request.args.get("class")

    conn = get_db_connection()

    classes = conn.execute(
        "SELECT class_name FROM class ORDER BY class_name"
    ).fetchall()

    if selected_class:
        records = conn.execute("""
            SELECT 
                b.rowid AS bmi_id,
                s.name,
                c.class_name AS class,
                b.height,
                b.weight,
                b.bmi_value,
                b.bmi_status,
                b.record_date
            FROM bmi_record b
            JOIN student s ON b.student_id = s.student_id
            JOIN class c ON s.class_id = c.class_id
            WHERE c.class_name = ?
            ORDER BY s.name, b.record_date DESC
        """, (selected_class,)).fetchall()
    else:
        records = conn.execute("""
            SELECT 
                b.rowid AS bmi_id,
                s.name,
                c.class_name AS class,
                b.height,
                b.weight,
                b.bmi_value,
                b.bmi_status,
                b.record_date
            FROM bmi_record b
            JOIN student s ON b.student_id = s.student_id
            JOIN class c ON s.class_id = c.class_id
            ORDER BY c.class_name, s.name, b.record_date DESC
        """).fetchall()

    conn.close()

    return render_template(
        "bmi_record.html",
        records=records,
        classes=classes,
        selected_class=selected_class
    )


#edit bmi
@app.route("/edit_bmi/<int:bmi_id>", methods=["GET","POST"])
def edit_bmi(bmi_id):
    if session.get("role") != "teacher":
        return redirect(url_for("login"))


    conn = get_db_connection()

    record = conn.execute(
        "SELECT rowid AS bmi_id, * FROM bmi_record WHERE rowid = ?",
        (bmi_id,)
    ).fetchone()

    if record is None:
        conn.close()
        return "BMI record not found", 404

    if request.method == "POST":
        height = float(request.form["height"])
        weight = float(request.form["weight"])
        record_date = request.form["record_date"]

        bmi = round(weight / (height * height), 2)


        if bmi < 18.5:
            status = "Underweight"
        elif bmi < 25:
            status = "Normal"
        elif bmi < 30:
            status = "Overweight"
        else:
            status = "Obese"

        conn.execute("""
            UPDATE bmi_record
            SET height=?, weight=?, bmi_value=?, bmi_status=?, record_date=?
            WHERE rowid=?
        """, (height, weight, bmi, status, record_date, bmi_id))

        conn.commit()
        conn.close()
        return redirect(url_for("bmi_records"))

    conn.close()
    return render_template("edit_bmi.html", record=record)

#delete bmi
@app.route("/delete_bmi/<int:bmi_id>")
def delete_bmi(bmi_id):
    if session.get("role") != "teacher":
        return redirect(url_for("login"))

    conn = get_db_connection()
    conn.execute("DELETE FROM bmi_record WHERE rowid = ?", (bmi_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("bmi_records"))


# =========================
# ADD SEGAK
# =========================
@app.route("/add_segak", methods=["GET", "POST"])
def add_segak():
    if session.get("role") != "teacher":
        return redirect(url_for("login"))

    conn = get_db_connection()
    students = conn.execute(
        "SELECT student_id, name FROM student ORDER BY name"
    ).fetchall()

    if request.method == "POST":
        student_id = request.form["student_id"]
        test_date = request.form["test_date"]

        step_test = int(request.form["step_test"])
        push_up = int(request.form["push_up"])
        sit_up = int(request.form["sit_up"])
        sit_reach = int(request.form["sit_reach"])

        # =========================
        # SEGAK FITNESS LOGIC (BETUL)
        # =========================

        # PRIORITY: POOR
        if push_up < 10 or sit_up < 10 or sit_reach < 2:
            fitness_level = "Poor"

        # AVERAGE
        elif push_up < 20 or sit_up < 20:
            fitness_level = "Average"

        # GOOD
        elif push_up < 25 or sit_up < 25:
            fitness_level = "Good"

        # EXCELLENT
        else:
            fitness_level = "Excellent"

        # =========================
        # INSERT DATABASE
        # =========================
        conn.execute("""
            INSERT INTO segak_record
            (student_id, test_date, step_test, push_up, sit_up, sit_reach, fitness_level)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            student_id,
            test_date,
            step_test,
            push_up,
            sit_up,
            sit_reach,
            fitness_level
        ))

        conn.commit()
        conn.close()

        return redirect(url_for("segak_records"))

    conn.close()
    return render_template("add_segak.html", students=students)


# =========================
# SEGAK RECORDS
# =========================
@app.route("/segak_records")
def segak_records():
    if session.get("role") != "teacher":
        return redirect(url_for("login"))

    selected_class = request.args.get("class")

    conn = get_db_connection()

    classes = conn.execute(
        "SELECT class_name FROM class ORDER BY class_name"
    ).fetchall()

    if selected_class:
        records = conn.execute("""
            SELECT 
                r.segak_id,
                s.name,
                c.class_name AS class,
                r.step_test,
                r.push_up,
                r.sit_up,
                r.sit_reach,
                r.fitness_level,
                r.test_date
            FROM segak_record r
            JOIN student s ON r.student_id = s.student_id
            JOIN class c ON s.class_id = c.class_id
            WHERE c.class_name = ?
            ORDER BY s.name, r.test_date DESC
        """, (selected_class,)).fetchall()
    else:
        records = conn.execute("""
            SELECT 
                r.segak_id,
                s.name,
                c.class_name AS class,
                r.step_test,
                r.push_up,
                r.sit_up,
                r.sit_reach,
                r.fitness_level,
                r.test_date
            FROM segak_record r
            JOIN student s ON r.student_id = s.student_id
            JOIN class c ON s.class_id = c.class_id
            ORDER BY c.class_name, s.name, r.test_date DESC
        """).fetchall()

    conn.close()

    return render_template(
        "segak_records.html",
        records=records,
        classes=classes,
        selected_class=selected_class
    )

#edit segak
@app.route("/edit_segak/<int:segak_id>", methods=["GET","POST"])
def edit_segak(segak_id):
    if session.get("role") != "teacher":
        return redirect(url_for("login"))

    conn = get_db_connection()

    record = conn.execute(
        "SELECT * FROM segak_record WHERE segak_id=?",
        (segak_id,)
    ).fetchone()

    if request.method == "POST":
        step = int(request.form["step_test"])
        push = int(request.form["push_up"])
        sit = int(request.form["sit_up"])
        reach = float(request.form["sit_reach"])
        test_date = request.form["test_date"]

        # =========================
        # SEGAK FITNESS LOGIC (SAMA DENGAN ADD)
        # =========================
        if push < 10 or sit < 10 or reach < 2:
            fitness_level = "Poor"
        elif push < 20 or sit < 20:
            fitness_level = "Average"
        elif push < 25 or sit < 25:
            fitness_level = "Good"
        else:
            fitness_level = "Excellent"

        conn.execute(
            """
            UPDATE segak_record
            SET step_test=?, push_up=?, sit_up=?, sit_reach=?,
                fitness_level=?, test_date=?
            WHERE segak_id=?
            """,
            (step, push, sit, reach, fitness_level, test_date, segak_id)
        )
        conn.commit()
        conn.close()
        return redirect(url_for("segak_records"))

    conn.close()
    return render_template("edit_segak.html", record=record)


#delete segak
@app.route("/delete_segak/<int:segak_id>")
def delete_segak(segak_id):
    if session.get("role") != "teacher":
        return redirect(url_for("login"))

    conn = get_db_connection()
    conn.execute("DELETE FROM segak_record WHERE segak_id=?", (segak_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("segak_records"))



# =========================
# RESULT (teacher)
# =========================
@app.route("/results")
def results():
    if session.get("role") != "teacher":
        return redirect(url_for("login"))

    selected_class = request.args.get("class")
    selected_student = request.args.get("student")

    conn = get_db_connection()

    # semua class
    classes = conn.execute(
        "SELECT class_name FROM class ORDER BY class_name"
    ).fetchall()

    students = []
    student_info = None
    bmi_results = []
    segak_results = []

    # bila class dipilih → load student
    if selected_class:
        students = conn.execute("""
            SELECT s.student_id, s.name
            FROM student s
            JOIN class c ON s.class_id = c.class_id
            WHERE c.class_name = ?
            ORDER BY s.name
        """, (selected_class,)).fetchall()

    # bila student dipilih → load result
    if selected_student:
        student_info = conn.execute("""
            SELECT s.name, c.class_name AS class
            FROM student s
            JOIN class c ON s.class_id = c.class_id
            WHERE s.student_id = ?
        """, (selected_student,)).fetchone()

        bmi_results = conn.execute("""
            SELECT record_date, height, weight, bmi_value, bmi_status
            FROM bmi_record
            WHERE student_id = ?
            ORDER BY record_date DESC
        """, (selected_student,)).fetchall()

        segak_results = conn.execute("""
            SELECT test_date, step_test, push_up, sit_up, sit_reach, fitness_level
            FROM segak_record
            WHERE student_id = ?
            ORDER BY test_date DESC
        """, (selected_student,)).fetchall()

    conn.close()

    return render_template(
        "result.html",
        classes=classes,
        students=students,
        selected_class=selected_class,
        selected_student=selected_student,
        student_info=student_info,
        bmi_results=bmi_results,
        segak_results=segak_results
    )
#stdent print
@app.route("/student/print")
def student_print():
    if session.get("role") != "student":
        return redirect(url_for("login"))

    conn = get_db_connection()

    student = conn.execute("""
    SELECT student.*, class.class_name AS class
    FROM student
    LEFT JOIN class ON student.class_id = class.class_id
    WHERE student.student_id = ?
""", (session.get("user_id"),)).fetchone()


    bmi = conn.execute(
        "SELECT * FROM bmi_record WHERE student_id = ? ORDER BY record_date DESC LIMIT 1",
        (session.get("user_id"),)
    ).fetchone()

    segak = conn.execute(
        "SELECT * FROM segak_record WHERE student_id = ? ORDER BY test_date DESC LIMIT 1",
        (session.get("user_id"),)
    ).fetchone()

    conn.close()

    return render_template(
        "student_print.html",
        student=student,
        bmi=bmi,
        segak=segak
    )


# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(debug=True)
