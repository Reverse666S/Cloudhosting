from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash
import os, json, hashlib, random, string, smtplib, shutil

app = Flask(__name__)
app.secret_key = "RandomAutoPepe"  # unbedingt ändern
USER_FOLDER = "user_files"
MAX_STORAGE = 100 * 1024**3  # 100GB

# Lade User
if os.path.exists("users.json"):
    with open("users.json", "r") as f:
        users = json.load(f)
else:
    users = {}

# Admin automatisch anlegen, falls nicht vorhanden
if "RandomAuto" not in users:
    hashed_pw = hashlib.sha256("RandomAuto".encode()).hexdigest()
    users["RandomAuto"] = {"email":"admin@cloud.local","password":hashed_pw,"is_admin":True}
    os.makedirs(os.path.join(USER_FOLDER, "RandomAuto"), exist_ok=True)
    with open("users.json","w") as f:
        json.dump(users,f)

# Temporäre Verifizierungscodes
if os.path.exists("verification.json"):
    with open("verification.json","r") as f:
        verification = json.load(f)
else:
    verification = {}

# Hilfsfunktionen
def hash_password(pw): return hashlib.sha256(pw.encode()).hexdigest()
def send_verification_email(to_email, code):
    # Beispiel SMTP, ggf. anpassen
    try:
        server = smtplib.SMTP("smtp.example.com", 587)
        server.starttls()
        server.login("youremail@example.com", "password")  # ersetzen
        message = f"Subject: Verifizierungscode\n\nDein Code: {code}"
        server.sendmail("youremail@example.com", to_email, message)
        server.quit()
    except Exception as e:
        print("E-Mail Fehler:", e)

def get_user_storage(username):
    folder = os.path.join(USER_FOLDER, username)
    total = 0
    for root, dirs, files in os.walk(folder):
        for f in files:
            total += os.path.getsize(os.path.join(root, f))
    return total

# ------------------ ROUTES ------------------

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method=="POST":
        username = request.form["username"]
        password = hash_password(request.form["password"])
        if username in users and users[username]["password"] == password:
            session["username"] = username
            session["is_admin"] = users[username]["is_admin"]
            return redirect("/admin_dashboard" if users[username]["is_admin"] else "/dashboard")
        flash("Ungültige Zugangsdaten")
    return render_template("login.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        if username in users:
            flash("Benutzer existiert bereits")
            return redirect("/register")
        code = ''.join(random.choices(string.digits, k=6))
        verification[username] = {"email":email, "password":hash_password(password), "code":code}
        with open("verification.json","w") as f:
            json.dump(verification,f)
        send_verification_email(email, code)
        session["verify_user"] = username
        return redirect("/verify")
    return render_template("register.html")

@app.route("/verify", methods=["GET","POST"])
def verify():
    username = session.get("verify_user")
    if not username or username not in verification:
        return redirect("/register")
    if request.method=="POST":
        code = request.form["code"]
        if code == verification[username]["code"]:
            # User erstellen
            users[username] = {"email": verification[username]["email"], "password": verification[username]["password"], "is_admin": False}
            os.makedirs(os.path.join(USER_FOLDER, username), exist_ok=True)
            with open("users.json","w") as f:
                json.dump(users,f)
            verification.pop(username)
            with open("verification.json","w") as f:
                json.dump(verification,f)
            session.pop("verify_user")
            flash("Account erstellt! Bitte einloggen.")
            return redirect("/")
        flash("Falscher Code")
    return render_template("verify.html")

@app.route("/dashboard")
def dashboard():
    if "username" not in session or session.get("is_admin"): return redirect("/")
    username = session["username"]
    user_files = os.listdir(os.path.join(USER_FOLDER, username))
    return render_template("dashboard.html", files=user_files)

@app.route("/admin_dashboard")
def admin_dashboard():
    if "username" not in session or not session.get("is_admin"): return redirect("/")
    all_users = users
    return render_template("admin_dashboard.html", all_users=all_users, user_folder=USER_FOLDER)

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect("/")

@app.route("/upload", methods=["POST"])
def upload():
    if "username" not in session: return redirect("/")
    file = request.files["file"]
    username = session["username"]
    user_path = os.path.join(USER_FOLDER, username)
    if get_user_storage(username) + len(file.read()) > MAX_STORAGE:
        flash("Maximaler Speicher erreicht")
        return redirect("/dashboard")
    file.seek(0)
    file.save(os.path.join(user_path, file.filename))
    return "OK", 200

@app.route("/download/<filename>")
def download(filename):
    if "username" not in session: return redirect("/")
    username = session["username"]
    path = os.path.join(USER_FOLDER, username)
    if session.get("is_admin"):
        # Admin kann alles downloaden
        for user in os.listdir(USER_FOLDER):
            if filename in os.listdir(os.path.join(USER_FOLDER, user)):
                path = os.path.join(USER_FOLDER, user)
                break
    if os.path.exists(os.path.join(path, filename)):
        return send_from_directory(path, filename, as_attachment=True)
    return "Datei nicht gefunden", 404

@app.route("/delete/<filename>", methods=["POST"])
def delete_file(filename):
    if "username" not in session: return redirect("/")
    username = session["username"]
    path = os.path.join(USER_FOLDER, username)
    if session.get("is_admin"):
        for user in os.listdir(USER_FOLDER):
            if filename in os.listdir(os.path.join(USER_FOLDER, user)):
                path = os.path.join(USER_FOLDER, user)
                break
    file_path = os.path.join(path, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    return redirect("/admin_dashboard" if session.get("is_admin") else "/dashboard")

@app.route("/delete_multiple", methods=["POST"])
def delete_multiple():
    if "username" not in session: return redirect("/")
    files = request.form.getlist("delete_files")
    for filename in files:
        delete_file(filename)
    return redirect("/admin_dashboard" if session.get("is_admin") else "/dashboard")

# Optional: Admin Userverwaltung
@app.route("/admin_create_user", methods=["POST"])
def admin_create_user():
    if "username" not in session or not session.get("is_admin"): return redirect("/")
    username = request.form["username"]
    password = hash_password(request.form["password"])
    email = request.form.get("email","admin@cloud.local")
    if username in users: flash("User existiert"); return redirect("/admin_dashboard")
    users[username] = {"email":email,"password":password,"is_admin":False}
    os.makedirs(os.path.join(USER_FOLDER, username), exist_ok=True)
    with open("users.json","w") as f: json.dump(users,f)
    return redirect("/admin_dashboard")

@app.route("/admin_delete_user/<username>", methods=["POST"])
def admin_delete_user(username):
    if "username" not in session or not session.get("is_admin"): return redirect("/")
    if username in users:
        shutil.rmtree(os.path.join(USER_FOLDER, username), ignore_errors=True)
        users.pop(username)
        with open("users.json","w") as f: json.dump(users,f)
    return redirect("/admin_dashboard")

if __name__=="__main__":
    os.makedirs(USER_FOLDER, exist_ok=True)
    app.run(debug=True)
