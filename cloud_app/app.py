from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash
import os, json, smtplib, random, string
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "dein_geheimes_schluesselwort"

USERS_FILE = "users.json"
BASE_DIR = "files"
MAX_USER_STORAGE = 100 * 1024**3  # 100 GB

os.makedirs(BASE_DIR, exist_ok=True)

# --- Hilfsfunktionen ---
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)

def create_user_folder(username):
    path = os.path.join(BASE_DIR, username)
    os.makedirs(path, exist_ok=True)
    return path

def admin_required(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "username" not in session or session.get("role") != "admin":
            flash("Admin-Zugang erforderlich!", "danger")
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper

def user_required(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "username" not in session:
            flash("Login erforderlich!", "danger")
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper

# --- E-Mail-Verifikation (Dummy-Funktion, hier SMTP eintragen) ---
VERIFICATION_CODES = {}
def send_verification_email(email, code):
    # Hier SMTP oder API eintragen, aktuell nur Print
    print(f"Verifizierungscode an {email}: {code}")

# --- Login ---
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        username = request.form["username"]
        password = request.form["password"]
        users = load_users()
        user = users.get(username)
        if user and user["password"]==password:
            session["username"]=username
            session["role"]=user["role"]
            return redirect(url_for("dashboard"))
        flash("Ungültige Zugangsdaten!", "danger")
    return render_template("login.html")

# --- Logout ---
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# --- Registrierung ---
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        users = load_users()
        if username in users:
            flash("Benutzer existiert bereits!", "danger")
            return redirect(url_for("register"))
        # Verifizierungscode generieren
        code = ''.join(random.choices(string.digits, k=6))
        VERIFICATION_CODES[username] = {"code":code, "email":email, "password":password}
        send_verification_email(email, code)
        return redirect(url_for("verify", username=username))
    return render_template("register.html")

# --- Code-Verifikation ---
@app.route("/verify/<username>", methods=["GET","POST"])
def verify(username):
    if request.method=="POST":
        input_code = request.form["code"]
        info = VERIFICATION_CODES.get(username)
        if info and input_code==info["code"]:
            users = load_users()
            users[username] = {"password":info["password"], "role":"user", "email":info["email"]}
            save_users(users)
            create_user_folder(username)
            flash("Account erstellt!", "success")
            VERIFICATION_CODES.pop(username)
            return redirect(url_for("login"))
        flash("Falscher Code!", "danger")
    return render_template("verify.html", username=username)

# --- Dashboard ---
@app.route("/")
@user_required
def dashboard():
    username = session["username"]
    role = session["role"]
    user_folder = os.path.join(BASE_DIR, username)
    os.makedirs(user_folder, exist_ok=True)
    files = os.listdir(user_folder)
    return render_template("dashboard.html", username=username, role=role, files=files)

# --- Datei-Upload ---
@app.route("/upload", methods=["POST"])
@user_required
def upload_file():
    username = session["username"]
    user_folder = os.path.join(BASE_DIR, username)
    f = request.files["file"]
    if f:
        filename = secure_filename(f.filename)
        f.save(os.path.join(user_folder, filename))
    return redirect(url_for("dashboard"))

# --- Datei-Download ---
@app.route("/download/<filename>")
@user_required
def download_file(filename):
    username = session["username"]
    user_folder = os.path.join(BASE_DIR, username)
    return send_from_directory(user_folder, filename, as_attachment=True)

# --- Datei-Löschen ---
@app.route("/delete/<filename>", methods=["POST"])
@user_required
def delete_file(filename):
    username = session["username"]
    user_folder = os.path.join(BASE_DIR, username)
    path = os.path.join(user_folder, filename)
    if os.path.exists(path):
        os.remove(path)
    return redirect(url_for("dashboard"))

# --- Admin: alle Dateien einsehen ---
@app.route("/admin_dashboard")
@admin_required
def admin_dashboard():
    all_users = os.listdir(BASE_DIR)
    return render_template("admin_dashboard.html", users=all_users)

if __name__=="__main__":
    app.run(debug=True)
