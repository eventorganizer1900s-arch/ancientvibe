import os, secrets, string
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import qrcode
from io import BytesIO
import base64

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-before-launch")
db_url = os.environ.get("DATABASE_URL", "sqlite:///ancient_event.db")
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="staff", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.String(40), unique=True, nullable=False, index=True)
    guest_name = db.Column(db.String(120), default="")
    status = db.Column(db.String(20), default="unused", nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    used_at = db.Column(db.DateTime, nullable=True)
    used_by = db.Column(db.String(80), nullable=True)

with app.app_context():
    db.create_all()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = db.session.get(User, session.get("user_id")) if session.get("user_id") else None
        if not user or user.role != "admin":
            flash("Admin access required.", "error")
            return redirect(url_for("dashboard"))
        return fn(*args, **kwargs)
    return wrapper

def make_ticket_id():
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "AVE-" + "".join(secrets.choice(alphabet) for _ in range(10))
        if not Ticket.query.filter_by(ticket_id=code).first():
            return code

def qr_data(ticket_id):
    img = qrcode.make(ticket_id)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")

@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("home.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    # First account becomes admin; subsequent accounts are created by an admin only.
    if User.query.count() > 0 and not session.get("user_id"):
        flash("The first admin account already exists. Ask your admin to create your staff account.", "error")
        return redirect(url_for("login"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        if len(username) < 3 or len(password) < 8:
            flash("Use a username of at least 3 characters and a password of at least 8 characters.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        elif User.query.filter_by(username=username).first():
            flash("That username already exists.", "error")
        else:
            role = "admin" if User.query.count() == 0 else "staff"
            user = User(username=username, password_hash=generate_password_hash(password), role=role)
            db.session.add(user); db.session.commit()
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role
            flash("Account created. Welcome to Ancient Event!", "success")
            return redirect(url_for("dashboard"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session.clear()
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role
            return redirect(url_for("dashboard"))
        flash("Incorrect username or password.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/dashboard")
@login_required
def dashboard():
    q = request.args.get("q", "").strip()
    tickets_query = Ticket.query
    if q:
        tickets_query = tickets_query.filter(
            db.or_(Ticket.ticket_id.ilike(f"%{q}%"), Ticket.guest_name.ilike(f"%{q}%"))
        )
    tickets = tickets_query.order_by(Ticket.created_at.desc()).limit(100).all()
    return render_template("dashboard.html", tickets=tickets, q=q,
        total=Ticket.query.count(), unused=Ticket.query.filter_by(status="unused").count(),
        used=Ticket.query.filter_by(status="used").count())

@app.route("/tickets/create", methods=["POST"])
@login_required
def create_ticket():
    guest = request.form.get("guest_name", "").strip()[:120]
    ticket = Ticket(ticket_id=make_ticket_id(), guest_name=guest)
    db.session.add(ticket); db.session.commit()
    flash("Ticket created: " + ticket.ticket_id, "success")
    return redirect(url_for("ticket_detail", ticket_id=ticket.ticket_id))

@app.route("/tickets/<ticket_id>")
@login_required
def ticket_detail(ticket_id):
    ticket = Ticket.query.filter_by(ticket_id=ticket_id.upper()).first_or_404()
    return render_template("ticket.html", ticket=ticket, qr=qr_data(ticket.ticket_id))

@app.route("/tickets/<ticket_id>/qr.png")
@login_required
def ticket_qr(ticket_id):
    ticket = Ticket.query.filter_by(ticket_id=ticket_id.upper()).first_or_404()
    img = qrcode.make(ticket.ticket_id)
    buf = BytesIO(); img.save(buf, format="PNG"); buf.seek(0)
    return send_file(buf, mimetype="image/png", download_name=f"{ticket.ticket_id}.png")

@app.route("/api/verify", methods=["POST"])
@login_required
def verify_ticket():
    data = request.get_json(silent=True) or request.form
    ticket_id = str(data.get("ticket_id", "")).strip().upper()
    if not ticket_id:
        return jsonify(result="invalid", message="Enter or scan a ticket ID.")
    # Locking the row and committing the status change prevents normal duplicate use.
    ticket = Ticket.query.filter_by(ticket_id=ticket_id).with_for_update().first()
    if not ticket:
        return jsonify(result="invalid", message="INVALID TICKET — not found in the database.")
    if ticket.status == "used":
        return jsonify(result="used", message="ALREADY USED — entry was previously recorded.",
                       ticket_id=ticket.ticket_id, guest_name=ticket.guest_name, used_at=ticket.used_at.isoformat() if ticket.used_at else None)
    ticket.status = "used"
    ticket.used_at = datetime.utcnow()
    ticket.used_by = session.get("username", "staff")
    db.session.commit()
    return jsonify(result="accepted", message="ACCEPTED — valid ticket marked used.",
                   ticket_id=ticket.ticket_id, guest_name=ticket.guest_name, used_at=ticket.used_at.isoformat())

@app.route("/staff/create", methods=["POST"])
@login_required
@admin_required
def create_staff():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    if len(username) < 3 or len(password) < 8:
        flash("Staff username must be 3+ characters and password 8+ characters.", "error")
    elif User.query.filter_by(username=username).first():
        flash("That username already exists.", "error")
    else:
        db.session.add(User(username=username, password_hash=generate_password_hash(password), role="staff"))
        db.session.commit()
        flash(f"Staff account '{username}' created.", "success")
    return redirect(url_for("dashboard"))

@app.route("/guest-list")
@login_required
def guest_list():
    guests = Ticket.query.order_by(Ticket.guest_name.asc()).all()
    return render_template("guests.html", tickets=guests)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
