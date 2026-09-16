

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
from supabase import create_client, Client
from datetime import datetime, timezone
from functools import wraps
import random

app = Flask(__name__)
app.secret_key = "student-portal-secret"
CORS(app)

# ============================================================
# SUPABASE
# ============================================================

SUPABASE_URL = "https://rcrbazstbgqfmhzubmrg.supabase.co"

# Server-side key only. Do NOT put this key in HTML/JavaScript.
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJjcmJhenN0YmdxZm1oenVibXJnIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1Nzc2NTMxMiwiZXhwIjoyMDczMzQxMzEyfQ.Y42dwejCsS66t0d-cMXaxL5Gxm9YuWx1JebUQelC5FQ"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ============================================================
# HELPERS
# ============================================================

def api_error(message, status=400):
    return jsonify({"success": False, "error": message}), status


def current_student():
    student_id = session.get("student_id")
    if not student_id:
        return None

    response = (
        supabase
        .table("students")
        .select("id,roll_no,name,section,year")
        .eq("id", student_id)
        .limit(1)
        .execute()
    )

    return response.data[0] if response.data else None


def student_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if not session.get("student_id"):
            return api_error("Student login required.", 401)
        return function(*args, **kwargs)
    return wrapper


def handle_supabase_error(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except Exception as error:
            print("=" * 70)
            print("SUPABASE/API ERROR")
            print(error)
            print("=" * 70)
            return jsonify({
                "success": False,
                "error": str(error)
            }), 500
    return wrapper


# ============================================================
# PAGES
# ============================================================

@app.route("/")
def home():
    if session.get("student_id"):
        return redirect(url_for("student_dashboard"))
    return render_template("register.html")


@app.route("/student/login")
def student_login_page():
    if session.get("student_id"):
        return redirect(url_for("student_dashboard"))
    return render_template("login.html")


@app.route("/student/register")
def student_register_page():
    if session.get("student_id"):
        return redirect(url_for("student_dashboard"))
    return render_template("register.html")


@app.route("/student/dashboard")
def student_dashboard():
    if not session.get("student_id"):
        return redirect(url_for("student_login_page"))
    return render_template("dashboard.html")


@app.route("/student/quiz/<quiz_id>")
def quiz_page(quiz_id):
    if not session.get("student_id"):
        return redirect(url_for("student_login_page"))
    return render_template("quiz.html", quiz_id=quiz_id)


@app.route("/student/results")
def results_page():
    if not session.get("student_id"):
        return redirect(url_for("student_login_page"))
    return render_template("results.html")


# ============================================================
# STUDENT LOGIN
# Roll number + year uniquely identifies the student.
# ============================================================

@app.route("/api/student/login", methods=["POST"])
@handle_supabase_error
def student_login():
    data = request.get_json(silent=True) or {}

    roll_no = str(data.get("roll_no", "")).strip().upper()
    year = str(data.get("year", "")).strip()

    if not roll_no or not year:
        return api_error("Roll number and year are required.")

    response = (
        supabase
        .table("students")
        .select("id,roll_no,name,section,year")
        .eq("roll_no", roll_no)
        .eq("year", year)
        .limit(1)
        .execute()
    )

    if not response.data:
        return jsonify({
            "success": False,
            "registered": False,
            "error": "Student not found. Please register first."
        }), 404

    student = response.data[0]

    session["student_id"] = student["id"]
    session["roll_no"] = student["roll_no"]
    session["year"] = student["year"]

    return jsonify({
        "success": True,
        "student": student
    })


# ============================================================
# STUDENT REGISTRATION
# Details are saved immediately.
# Unique identity = roll_no + year.
# ============================================================

@app.route("/api/student/register", methods=["POST"])
@handle_supabase_error
def student_register():
    data = request.get_json(silent=True) or {}

    roll_no = str(data.get("roll_no", "")).strip().upper()
    name = str(data.get("name", "")).strip()
    section = str(data.get("section", "")).strip().upper()
    year = str(data.get("year", "")).strip()

    if not roll_no or not name or not section or not year:
        return api_error("Roll number, name, section and year are required.")

    existing = (
        supabase
        .table("students")
        .select("id,roll_no,name,section,year")
        .eq("roll_no", roll_no)
        .eq("year", year)
        .limit(1)
        .execute()
    )

    if existing.data:
        return jsonify({
            "success": False,
            "error": "This roll number is already registered for this year. Please login."
        }), 409

    student_data = {
        "roll_no": roll_no,
        "name": name,
        "section": section,
        "year": year,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    response = (
        supabase
        .table("students")
        .insert(student_data)
        .select("id,roll_no,name,section,year")
        .execute()
    )

    student = response.data[0]

    session["student_id"] = student["id"]
    session["roll_no"] = student["roll_no"]
    session["year"] = student["year"]

    return jsonify({
        "success": True,
        "student": student
    })


# ============================================================
# CURRENT STUDENT
# ============================================================

@app.route("/api/student/me", methods=["GET"])
@student_required
@handle_supabase_error
def get_me():
    student = current_student()

    if not student:
        session.clear()
        return api_error("Student account not found.", 401)

    return jsonify({
        "success": True,
        "student": student
    })


# ============================================================
# LOGOUT
# ============================================================

@app.route("/api/student/logout", methods=["POST"])
def student_logout():
    session.clear()
    return jsonify({"success": True})


@app.route("/student/logout")
def student_logout_page():
    session.clear()
    return redirect(url_for("student_login_page"))


# ============================================================
# DASHBOARD - AVAILABLE QUIZZES FOR STUDENT YEAR
# ============================================================

@app.route("/api/student/quizzes", methods=["GET"])
@student_required
@handle_supabase_error
def get_student_quizzes():
    student = current_student()

    if not student:
        return api_error("Student account not found.", 401)

    response = (
        supabase
        .table("quizzes")
        .select("id,title,description,status,year,created_at,winners_revealed,leaderboard_revealed,results_revealed")
        .eq("status", "active")
        .eq("year", student["year"])
        .order("created_at", desc=True)
        .execute()
    )

    quizzes = response.data or []

    # Mark whether this student already attempted each quiz.
    for quiz in quizzes:
        attempts = (
            supabase
            .table("quiz_responses")
            .select("id,score,total_questions,submitted_at")
            .eq("quiz_id", quiz["id"])
            .eq("student_id", student["id"])
            .limit(1)
            .execute()
        )

        quiz["attempted"] = bool(attempts.data)
        quiz["attempt"] = attempts.data[0] if attempts.data else None

    return jsonify({
        "success": True,
        "quizzes": quizzes
    })


# ============================================================
# GET ONE QUIZ
# Only quizzes belonging to student's year are accessible.
# ============================================================

@app.route("/api/student/quiz/<quiz_id>", methods=["GET"])
@student_required
@handle_supabase_error
def get_student_quiz(quiz_id):
    student = current_student()

    if not student:
        return api_error("Student account not found.", 401)

    # Check if already submitted.
    existing = (
        supabase
        .table("quiz_responses")
        .select("id,score,total_questions,submitted_at")
        .eq("quiz_id", quiz_id)
        .eq("student_id", student["id"])
        .limit(1)
        .execute()
    )

    if existing.data:
        return jsonify({
            "success": False,
            "already_submitted": True,
            "error": "You have already attempted this quiz."
        }), 409

    quiz_response = (
        supabase
        .table("quizzes")
        .select("id,title,description,status,year,winners_revealed,leaderboard_revealed,results_revealed")
        .eq("id", quiz_id)
        .eq("status", "active")
        .eq("year", student["year"])
        .limit(1)
        .execute()
    )

    if not quiz_response.data:
        return api_error(
            "Quiz is not active or is not available for your year.",
            404
        )

    quiz = quiz_response.data[0]

    questions_response = (
        supabase
        .table("questions")
        .select(
            "id,question_text,option_a,option_b,option_c,option_d,"
            "question_order,time_limit,image_url"
        )
        .eq("quiz_id", quiz_id)
        .order("question_order", desc=False)
        .execute()
    )

    questions = questions_response.data or []

    if not questions:
        return api_error("This quiz has no questions.", 404)

    # Different order for every student.
    random.shuffle(questions)

    return jsonify({
        "success": True,
        "quiz": quiz,
        "questions": questions
    })


# ============================================================
# SUBMIT QUIZ
# Server calculates score using correct_answer.
# Client never receives correct answers.
# ============================================================

@app.route("/api/student/submit", methods=["POST"])
@student_required
@handle_supabase_error
def submit_student_quiz():
    student = current_student()

    if not student:
        return api_error("Student account not found.", 401)

    data = request.get_json(silent=True) or {}

    quiz_id = data.get("quiz_id")
    answers = data.get("answers") or {}

    # Total time taken for the complete quiz, sent by the student website.
    # Stored in seconds.
    try:
        total_time_taken = int(data.get("total_time_taken", 0))
    except (TypeError, ValueError):
        total_time_taken = 0

    total_time_taken = max(0, total_time_taken)

    if not quiz_id:
        return api_error("Quiz ID is required.")

    if not isinstance(answers, dict):
        return api_error("Answers must be an object.")

    # Verify quiz belongs to student's year and is active.
    quiz_response = (
        supabase
        .table("quizzes")
        .select("id,title,status,year,results_revealed")
        .eq("id", quiz_id)
        .eq("status", "active")
        .eq("year", student["year"])
        .limit(1)
        .execute()
    )

    if not quiz_response.data:
        return api_error(
            "Quiz is not active or is not available for your year.",
            403
        )

    quiz = quiz_response.data[0]

    # Prevent second attempt.
    existing = (
        supabase
        .table("quiz_responses")
        .select("id")
        .eq("quiz_id", quiz_id)
        .eq("student_id", student["id"])
        .limit(1)
        .execute()
    )

    if existing.data:
        return jsonify({
            "success": False,
            "error": "You have already submitted this quiz."
        }), 409

    # Get correct answers SERVER-SIDE.
    questions_response = (
        supabase
        .table("questions")
        .select("id,correct_answer")
        .eq("quiz_id", quiz_id)
        .execute()
    )

    questions = questions_response.data or []
    total_questions = len(questions)

    if total_questions == 0:
        return api_error("Quiz has no questions.", 400)

    score = 0
    clean_answers = {}

    for question in questions:
        question_id = str(question["id"])
        submitted_answer = answers.get(question_id)

        if submitted_answer in ["A", "B", "C", "D"]:
            clean_answers[question_id] = submitted_answer

            if submitted_answer == question["correct_answer"]:
                score += 1

    answered_questions = len(clean_answers)

    submission = {
        "quiz_id": quiz_id,
        "student_id": student["id"],
        "roll_no": student["roll_no"],
        "name": student["name"],
        "section": student["section"],
        "year": student["year"],
        "answers": clean_answers,
        "total_questions": total_questions,
        "answered_questions": answered_questions,
        "score": score,
        "total_time_taken": total_time_taken,
        "submitted_at": datetime.now(timezone.utc).isoformat()
    }

    response = (
        supabase
        .table("quiz_responses")
        .insert(submission)
        .select(
            "id,score,total_questions,answered_questions,"
            "total_time_taken,submitted_at"
        )
        .execute()
    )

    submission_row = response.data[0] if response.data else {}

    return jsonify({
        "success": True,
        "message": "Quiz submitted successfully.",
        "submission": submission_row
    })


# ============================================================
# MY SCORES
# Only reveal score when admin sets results_revealed = true.
# ============================================================

@app.route("/api/student/scores", methods=["GET"])
@student_required
@handle_supabase_error
def get_scores():
    student = current_student()

    if not student:
        return api_error("Student account not found.", 401)

    responses = (
        supabase
        .table("quiz_responses")
        .select(
            "id,quiz_id,total_questions,answered_questions,"
            "score,total_time_taken,submitted_at"
        )
        .eq("student_id", student["id"])
        .order("submitted_at", desc=True)
        .execute()
    )

    scores = []

    for row in responses.data or []:
        quiz_response = (
            supabase
            .table("quizzes")
            .select("id,title,winners_revealed,leaderboard_revealed,results_revealed")
            .eq("id", row["quiz_id"])
            .limit(1)
            .execute()
        )

        if not quiz_response.data:
            continue

        quiz = quiz_response.data[0]

        scores.append({
            "quiz_id": row["quiz_id"],
            "title": quiz["title"],
            "results_revealed": bool(quiz.get("results_revealed")),
            "score": row["score"] if quiz.get("results_revealed") else None,
            "total_questions": row["total_questions"],
            "answered_questions": row["answered_questions"],
            "total_time_taken": row.get("total_time_taken", 0),
            "submitted_at": row["submitted_at"]
        })

    return jsonify({
        "success": True,
        "scores": scores
    })


# ============================================================
# LEADERBOARD
# Only available after admin reveals results.
# ============================================================

@app.route("/api/student/leaderboard/<quiz_id>", methods=["GET"])
@student_required
@handle_supabase_error
def get_leaderboard(quiz_id):
    student = current_student()

    if not student:
        return api_error("Student account not found.", 401)

    quiz_response = (
        supabase
        .table("quizzes")
        .select(
            "id,title,year,winners_revealed,"
            "leaderboard_revealed,results_revealed"
        )
        .eq("id", quiz_id)
        .eq("year", student["year"])
        .limit(1)
        .execute()
    )

    if not quiz_response.data:
        return api_error("Quiz not found.", 404)

    quiz = quiz_response.data[0]

    # Leaderboard visibility is controlled ONLY by leaderboard_revealed.
    if not quiz.get("leaderboard_revealed"):
        return jsonify({
            "success": True,
            "revealed": False,
            "leaderboard": [],
            "quiz": {
                "id": quiz["id"],
                "title": quiz["title"]
            }
        })

    response = (
        supabase
        .table("quiz_responses")
        .select(
            "student_id,score,total_questions,total_time_taken,submitted_at,"
            "students(name,roll_no,section,year)"
        )
        .eq("quiz_id", quiz_id)
        .order("score", desc=True)
        .order("total_time_taken", desc=False)
        .order("submitted_at", desc=False)
        .execute()
    )

    rows = response.data or []

    leaderboard = []

    for index, row in enumerate(rows, start=1):
        student_data = row.get("students") or {}

        leaderboard.append({
            "rank": index,
            "name": student_data.get("name", "Student"),
            "roll_no": student_data.get("roll_no", ""),
            "section": student_data.get("section", ""),
            "year": student_data.get("year", ""),
            "score": row.get("score", 0),
            "total_questions": row.get("total_questions", 0),
            "total_time_taken": row.get("total_time_taken", 0)
        })

    return jsonify({
        "success": True,
        "revealed": True,
        "quiz": {
            "id": quiz["id"],
            "title": quiz["title"]
        },
        "leaderboard": leaderboard
    })


# ============================================================
# WINNERS
# Only available after admin declares winners.
# ============================================================

@app.route("/api/student/winners/<quiz_id>", methods=["GET"])
@student_required
@handle_supabase_error
def get_winners(quiz_id):
    student = current_student()

    if not student:
        return api_error("Student account not found.", 401)

    quiz_response = (
        supabase
        .table("quizzes")
        .select(
            "id,title,year,winners_revealed,"
            "leaderboard_revealed,results_revealed"
        )
        .eq("id", quiz_id)
        .eq("year", student["year"])
        .limit(1)
        .execute()
    )

    if not quiz_response.data:
        return api_error("Quiz not found.", 404)

    quiz = quiz_response.data[0]

    if not quiz.get("winners_revealed"):
        return jsonify({
            "success": True,
            "revealed": False,
            "winners": [],
            "quiz": {
                "id": quiz["id"],
                "title": quiz["title"]
            }
        })

    # Get all submitted students in the same ranking order used by
    # the leaderboard: marks DESC, total time ASC, submission time ASC.
    response = (
        supabase
        .table("quiz_responses")
        .select(
            "student_id,roll_no,name,section,year,"
            "score,total_questions,total_time_taken,submitted_at"
        )
        .eq("quiz_id", quiz_id)
        .order("score", desc=True)
        .order("total_time_taken", desc=False)
        .order("submitted_at", desc=False)
        .execute()
    )

    rows = response.data or []

    # Read the selected winners.
    winners_response = (
        supabase
        .table("winners")
        .select("student_id,roll_no,name,section,year")
        .eq("quiz_id", quiz_id)
        .execute()
    )

    selected = winners_response.data or []
    selected_ids = {
        str(row.get("student_id"))
        for row in selected
    }

    winners = []

    for position, row in enumerate(rows, start=1):

        if str(row.get("student_id")) not in selected_ids:
            continue

        winners.append({
            "position": position,
            "student_id": row.get("student_id"),
            "roll_no": row.get("roll_no", ""),
            "name": row.get("name", "Student"),
            "section": row.get("section", ""),
            "year": row.get("year", ""),
            "score": row.get("score", 0),
            "total_questions": row.get("total_questions", 0),
            "total_time_taken": row.get("total_time_taken", 0)
        })

    return jsonify({
        "success": True,
        "revealed": True,
        "quiz": {
            "id": quiz["id"],
            "title": quiz["title"]
        },
        "winners": winners
    })


# ============================================================
# STUDENT RESULT SCRIPT
# Shows the student's submitted answer for every question,
# the correct answer, and whether it was correct.
# Only available after the admin declares RESULTS.
# ============================================================

@app.route("/api/student/script/<quiz_id>", methods=["GET"])
@student_required
@handle_supabase_error
def get_student_script(quiz_id):

    student = current_student()

    if not student:
        return api_error("Student account not found.", 401)

    quiz_response = (
        supabase
        .table("quizzes")
        .select(
            "id,title,year,results_revealed"
        )
        .eq("id", quiz_id)
        .eq("year", student["year"])
        .limit(1)
        .execute()
    )

    if not quiz_response.data:
        return api_error("Quiz not found.", 404)

    quiz = quiz_response.data[0]

    if not quiz.get("results_revealed"):
        return jsonify({
            "success": True,
            "revealed": False,
            "quiz": {
                "id": quiz["id"],
                "title": quiz["title"]
            },
            "script": []
        })

    response = (
        supabase
        .table("quiz_responses")
        .select(
            "student_id,answers,score,total_questions,"
            "answered_questions,total_time_taken,submitted_at"
        )
        .eq("quiz_id", quiz_id)
        .eq("student_id", student["id"])
        .limit(1)
        .execute()
    )

    if not response.data:
        return api_error("You have not submitted this quiz.", 404)

    submission = response.data[0]

    raw_answers = submission.get("answers") or {}

    # Support answers stored as JSON text as well as a JSON object.
    if isinstance(raw_answers, str):
        try:
            import json
            raw_answers = json.loads(raw_answers)
        except Exception:
            raw_answers = {}

    questions_response = (
        supabase
        .table("questions")
        .select(
            "id,question_text,option_a,option_b,option_c,option_d,correct_answer"
        )
        .eq("quiz_id", quiz_id)
        .execute()
    )

    questions = questions_response.data or []

    script = []

    for index, question in enumerate(questions, start=1):

        question_id = str(question.get("id"))

        submitted = (
            raw_answers.get(question_id)
            if isinstance(raw_answers, dict)
            else None
        )

        # Some older submissions may have used integer/string keys.
        if submitted is None and isinstance(raw_answers, dict):
            submitted = raw_answers.get(str(question.get("id")))

        correct = question.get("correct_answer")

        is_correct = (
            submitted is not None
            and str(submitted).strip().upper()
            == str(correct).strip().upper()
        )

        script.append({
            "number": index,
            "question_id": question.get("id"),
            "question_text": question.get("question_text"),
            "options": {
                "A": question.get("option_a"),
                "B": question.get("option_b"),
                "C": question.get("option_c"),
                "D": question.get("option_d")
            },
            "submitted_answer": submitted,
            "correct_answer": correct,
            "is_correct": is_correct
        })

    return jsonify({
        "success": True,
        "revealed": True,
        "quiz": {
            "id": quiz["id"],
            "title": quiz["title"]
        },
        "summary": {
            "score": submission.get("score", 0),
            "total_questions": submission.get("total_questions", 0),
            "answered_questions": submission.get("answered_questions", 0),
            "total_time_taken": submission.get("total_time_taken", 0),
            "submitted_at": submission.get("submitted_at")
        },
        "script": script
    })


# ============================================================
# STUDENT SCRIPT PAGE
# ============================================================

@app.route("/student/script")
@student_required
def student_script_page():
    return render_template("student_script.html")



# ============================================================
# HEALTH
# ============================================================

@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "service": "student-portal"
    })


# ============================================================
# ERROR
# ============================================================

@app.errorhandler(404)
def page_not_found(error):
    return jsonify({
        "success": False,
        "error": "Page or API endpoint not found."
    }), 404


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    app.run(
        debug=True,
        host="127.0.0.1",
        port=5001
    )
