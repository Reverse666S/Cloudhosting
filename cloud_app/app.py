from flask import Flask, request, render_template, redirect, session, jsonify
import os, json

app = Flask(__name__)
app.secret_key = "DEIN_SECRET_KEY"

USER_FILE = "users.json"
USER_FOLDER = "user_files"
MAX_STORAGE = 100 * 1024**3  # 100 GB

# User-Setup inkl. Admin
if not os.path.exists(USER_FILE):
    users = {
        "RandomAuto": {"password": "RandomAuto", "email": "carlbot0815@gmail.com", "is_admin": True}
    }
    with open(USER_FILE, "w") as f:
        json.dump(users, f)
else:
    with open(USER_FILE) as f:
        users = json.load(f)

# Hilfsfunktion Speicher
def get_user_storage(username):
    folder = os.path.join(USER_FOLDER, username)
    total = 0
    if os.path.exists(folder):
        for f in os.listdir(folder):
            total += os.path.getsize(os.path.join(folder, f))
    return total

# Index
@app.route("/")
def index():
    return render_template("index.html")

# Login
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        username = request.form["username"]
        password = request.form["password"]
        if username in users and users[username]["password"]==password:
            session["username"] = username
            session["is_admin"] = users[username]["is_admin"]
            return redirect("/admin_dashboard" if users[username]["is_admin"] else "/dashboard")
        else:
            return render_template("login.html", error="Falscher Benutzername oder Passwort")
    return render_template("login.html")

# Registrierung
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        username = request.form["username"]
        password = request.form["password"]
        email = request.form["email"]
        if username in users:
            return render_template("register.html", error="Benutzername existiert bereits")
        users[username] = {"password": password, "email": email, "is_admin": False}
        os.makedirs(os.path.join(USER_FOLDER, username), exist_ok=True)
        with open(USER_FILE, "w") as f:
            json.dump(users, f)
        return redirect("/verify?username="+username)
    return render_template("register.html")

# Verifizierung
@app.route("/verify", methods=["GET","POST"])
def verify():
    if request.method=="POST":
        username = request.form["username"]
        session["username"] = username
        session["is_admin"] = users[username]["is_admin"]
        return redirect("/dashboard")
    username = request.args.get("username")
    return render_template("verify.html", username=username)

# Logout
@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect("/")

# Dashboard
@app.route("/dashboard")
def dashboard():
    if "username" not in session or session.get("is_admin"):
        return redirect("/login")
    return render_template("dashboard.html")

@app.route("/admin_dashboard")
def admin_dashboard():
    if "username" not in session or not session.get("is_admin"):
        return redirect("/login")
    return render_template("admin_dashboard.html")

# Dateien Upload
@app.route("/upload", methods=["POST"])
def upload():
    if "username" not in session:
        return "Forbidden", 403
    username = session["username"]
    file = request.files["file"]
    folder = os.path.join(USER_FOLDER, username)
    os.makedirs(folder, exist_ok=True)
    file.save(os.path.join(folder, file.filename))
    return "OK", 200

# Dateien Download
@app.route("/download/<filename>")
def download(filename):
    if "username" not in session:
        return "Forbidden", 403
    username = session["username"]
    folder = USER_FOLDER if session.get("is_admin") else os.path.join(USER_FOLDER, username)
    if not os.path.exists(os.path.join(folder, filename)):
        return "Not found", 404
    from flask import send_from_directory
    return send_from_directory(folder, filename, as_attachment=True)

# Dateien Löschen
@app.route("/delete/<filename>", methods=["POST"])
def delete_file(filename):
    if "username" not in session:
        return "Forbidden", 403
    username = session["username"]
    folder = USER_FOLDER if session.get("is_admin") else os.path.join(USER_FOLDER, username)
    try:
        os.remove(os.path.join(folder, filename))
    except: pass
    return redirect(request.referrer)

# Admin – Alle Dateien
@app.route("/admin_files")
def admin_files():
    if "username" not in session or not session.get("is_admin"):
        return {}, 403
    result = {}
    for username, data in users.items():
        folder = os.path.join(USER_FOLDER, username)
        files = os.listdir(folder) if os.path.exists(folder) else []
        result[username] = {"files": files, "is_admin": data["is_admin"]}
    return result

# Admin – User löschen
@app.route("/admin_delete_user/<username>", methods=["POST"])
def admin_delete_user(username):
    if "username" not in session or not session.get("is_admin"):
        return "Forbidden", 403
    if username in users:
        folder = os.path.join(USER_FOLDER, username)
        if os.path.exists(folder):
            import shutil
            shutil.rmtree(folder)
        users.pop(username)
        with open(USER_FILE,"w") as f:
            json.dump(users,f)
    return redirect("/admin_dashboard")

# Admin – User erstellen
@app.route("/admin_create_user", methods=["POST"])
def admin_create_user():
    if "username" not in session or not session.get("is_admin"):
        return "Forbidden", 403
    username = request.form["username"]
    password = request.form["password"]
    email = request.form["email"]
    if username not in users:
        users[username] = {"password":password,"email":email,"is_admin":False}
        os.makedirs(os.path.join(USER_FOLDER, username), exist_ok=True)
        with open(USER_FILE,"w") as f:
            json.dump(users,f)
    return redirect("/admin_dashboard")

# User-Dateiliste
@app.route("/user_files")
def user_files():
    if "username" not in session:
        return {}, 403
    username = session["username"]
    folder = os.path.join(USER_FOLDER, username)
    files = os.listdir(folder) if os.path.exists(folder) else []
    return {"files": files}

# Speicherprüfung
@app.route("/check_storage")
def check_storage():
    if "username" not in session:
        return {"too_large": False}
    username = session["username"]
    file_size = int(request.args.get("file_size",0))
    current = get_user_storage(username)
    too_large = current + file_size > MAX_STORAGE
    return {"too_large": too_large}

if __name__=="__main__":
    os.makedirs(USER_FOLDER, exist_ok=True)
    app.run(debug=True)
