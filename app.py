from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import sqlite3
import hashlib
import jwt
import datetime
import os
from functools import wraps
from werkzeug.utils import secure_filename
from PIL import Image
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = 'your-secure-secret-key'  # Replace with a secure key
SECRET_KEY = 'your-jwt-secret-key'        # Replace with a secure JWT key
app.config['SESSION_PERMANENT'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'txt'}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB limit

# Ensure upload directory exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Database initialization
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  name TEXT NOT NULL, 
                  email TEXT UNIQUE NOT NULL, 
                  password TEXT NOT NULL, 
                  contact TEXT, 
                  photo TEXT, 
                  passed_out_year INTEGER, 
                  approved INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS events 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  title TEXT NOT NULL, 
                  date TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS contact_messages 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  name TEXT NOT NULL, 
                  email TEXT NOT NULL, 
                  message TEXT NOT NULL, 
                  submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS event_registrations 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  user_id INTEGER NOT NULL, 
                  event_id INTEGER NOT NULL, 
                  registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                  FOREIGN KEY (user_id) REFERENCES users(id), 
                  FOREIGN KEY (event_id) REFERENCES events(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  sender_id INTEGER NOT NULL, 
                  receiver_id INTEGER NOT NULL, 
                  message TEXT NOT NULL, 
                  attachment TEXT, 
                  sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
                  FOREIGN KEY (sender_id) REFERENCES users(id), 
                  FOREIGN KEY (receiver_id) REFERENCES users(id))''')
    conn.commit()
    conn.close()

# Migration function to add approved column if it doesn't exist
def migrate_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in c.fetchall()]
    if 'approved' not in columns:
        c.execute("ALTER TABLE users ADD COLUMN approved INTEGER DEFAULT 0")
    conn.commit()
    conn.close()

# Check if file has allowed extension
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Save uploaded file (for profile photos and attachments)
def save_file(file):
    if file and allowed_file(file.filename):
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        if file_size > MAX_FILE_SIZE:
            return None, "File size exceeds 100MB limit"
        file.seek(0)
        
        filename = secure_filename(file.filename)
        base, extension = os.path.splitext(filename)
        counter = 1
        while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], filename)):
            filename = f"{base}_{counter}{extension}"
            counter += 1
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        if extension[1:].lower() in {'png', 'jpg', 'jpeg', 'gif'}:
            try:
                img = Image.open(filepath)
                img.thumbnail((300, 300))
                img.save(filepath)
            except:
                pass
        return filename, None
    return None, "Invalid file type"

# Get events
def get_events():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT DISTINCT id, title, date FROM events")
    events = [{'id': row[0], 'title': row[1], 'date': row[2]} for row in c.fetchall()]
    conn.close()
    return events

# Get user's event registrations
def get_user_registrations(user_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''SELECT e.title, e.date, er.registered_at 
                 FROM event_registrations er 
                 JOIN events e ON er.event_id = e.id 
                 WHERE er.user_id = ?''', (user_id,))
    registrations = [{'event_title': row[0], 'event_date': row[1], 'registered_at': row[2]} for row in c.fetchall()]
    conn.close()
    return registrations

# Get all future events for notifications
def get_upcoming_events():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    c.execute("SELECT id, title, date FROM events WHERE date >= ?", (today,))
    events = [{'id': row[0], 'title': row[1], 'date': row[2]} for row in c.fetchall()]
    conn.close()
    return events

# Get all user profiles
def get_user_profiles(current_email=None):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if current_email:
        c.execute("SELECT id, name, email, contact, photo, passed_out_year, approved FROM users WHERE email != ?", (current_email,))
    else:
        c.execute("SELECT id, name, email, contact, photo, passed_out_year, approved FROM users")
    users = [{'id': row[0], 'name': row[1], 'email': row[2], 'contact': row[3], 'photo': row[4], 'passed_out_year': row[5], 'approved': row[6]} for row in c.fetchall()]
    conn.close()
    return users

# Get conversation history
def get_conversation(sender_id, receiver_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''SELECT m.message, m.sent_at, m.attachment, u1.name AS sender_name, u2.name AS receiver_name
                 FROM messages m
                 JOIN users u1 ON m.sender_id = u1.id
                 JOIN users u2 ON m.receiver_id = u2.id
                 WHERE (m.sender_id = ? AND m.receiver_id = ?) OR (m.sender_id = ? AND m.receiver_id = ?)
                 ORDER BY m.sent_at ASC''', (sender_id, receiver_id, receiver_id, sender_id))
    messages = [{'message': row[0], 'sent_at': row[1], 'attachment': row[2], 'sender_name': row[3], 'receiver_name': row[4]} for row in c.fetchall()]
    conn.close()
    return messages

# Check if user is admin
def is_admin(email):
    return email == "admin@ksrmce.ac.in"

# Token required decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = session.get('token')
        if not token:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            email = data['email']
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute("SELECT approved FROM users WHERE email = ?", (email,))
            approved = c.fetchone()
            conn.close()
            if not approved or (approved[0] == 0 and not is_admin(email)):  # Only check approval if not admin
                flash('Your account is awaiting admin approval.', 'error')
                return redirect(url_for('login'))
        except:
            session.pop('token', None)
            flash('Session expired. Please log in again.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# Send welcome email using smtplib
def send_welcome_email(to_email, name):
    # Your personal email credentials
    from_email = "alumniksrmce@gmail.com"  # Replace with your Gmail address
    from_password = "Ksrmce@123"  # Replace with your App Password or regular password

    # Email content
    subject = "Welcome to KSRM Alumni Portal! (Pending Approval)"
    body = f"""Dear {name},

Thank you for registering with the KSRM Alumni Portal. Your account is pending admin approval. You will receive a notification once approved.

Best regards,
KSRM Alumni Network Team
"""
    
    # Create MIME object
    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        # Connect to Gmail's SMTP server
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()  # Enable TLS
        server.login(from_email, from_password)  # Login to your account
        server.send_message(msg)  # Send the email
        server.quit()
        print(f"Email sent to {to_email} successfully!")
    except Exception as e:
        print(f"Failed to send welcome email: {e}")

# Routes
@app.route('/')
@app.route('/home')
def home():
    return render_template('home.html', events=get_events())

@app.route('/allumini')
def allumini():
    return render_template('allumini.html')

@app.route('/events', methods=['GET', 'POST'])
@token_required
def events():
    token = session['token']
    data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    email = data['email']
    is_admin_user = is_admin(email)

    if request.method == 'POST':
        data = request.get_json()
        if not data:
            return jsonify({'message': 'Invalid request'}), 400

        action = data.get('action')
        conn = sqlite3.connect('database.db')
        c = conn.cursor()

        try:
            if action == 'add':
                title = data.get('title')
                date = data.get('date')
                if not title or not date:
                    return jsonify({'message': 'Title and date are required'}), 400
                c.execute("INSERT INTO events (title, date) VALUES (?, ?)", (title, date))
            elif action == 'delete':
                event_id = data.get('event_id')
                if not event_id:
                    return jsonify({'message': 'Event ID is required'}), 400
                c.execute("DELETE FROM events WHERE id = ?", (event_id,))
                c.execute("DELETE FROM event_registrations WHERE event_id = ?", (event_id,))
            elif action == 'edit':
                event_id = data.get('event_id')
                title = data.get('title')
                date = data.get('date')
                if not event_id or not title or not date:
                    return jsonify({'message': 'Event ID, title, and date are required'}), 400
                c.execute("UPDATE events SET title = ?, date = ? WHERE id = ?", (title, date, event_id))
            else:
                return jsonify({'message': 'Invalid action'}), 400

            conn.commit()
            return jsonify({'message': 'Success'})
        except Exception as e:
            conn.rollback()
            return jsonify({'message': f'Server error: {str(e)}'}), 500
        finally:
            conn.close()

    events = get_events()
    return render_template('events.html', events=events, is_admin=is_admin_user)

@app.route('/profiles')
@token_required
def profiles():
    token = session['token']
    data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    email = data['email']
    is_admin_user = is_admin(email)
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE email = ?", (email,))
    current_user = c.fetchone()
    conn.close()
    if not current_user:
        flash('User not found. Please register.', 'error')
        return redirect(url_for('register'))
    current_user_id = current_user[0]

    users = get_user_profiles(email)
    return render_template('profiles.html', users=users, is_admin=is_admin_user, current_user_id=current_user_id)

@app.route('/contact_us')
def contact_us():
    return render_template('contact_us.html')

@app.route('/contact', methods=['POST'])
def contact():
    data = request.get_json()
    if not data:
        flash('Invalid request.', 'error')
        return jsonify({'message': 'Invalid request'}), 400

    name = data.get('name')
    email = data.get('email')
    message = data.get('message')

    if not name or not email or not message:
        flash('All fields are required.', 'error')
        return jsonify({'message': 'All fields are required'}), 400

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("INSERT INTO contact_messages (name, email, message) VALUES (?, ?, ?)", 
              (name, email, message))
    conn.commit()
    conn.close()

    flash('Message sent successfully!', 'success')
    return jsonify({'message': 'Message sent successfully'})

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash('Email and password are required.', 'error')
            return render_template('login.html')

        password_hash = hashlib.sha256(password.encode()).hexdigest()

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT id, name, email, password, contact, photo, passed_out_year, approved FROM users WHERE email = ? AND password = ?", (email, password_hash))
        user = c.fetchone()
        conn.close()

        if user:
            if user[7] == 0 and not is_admin(email):  # Check approved status only if not admin
                flash('Your account is awaiting admin approval.', 'error')
                return render_template('login.html')
            token = jwt.encode({
                'email': email,
                'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
            }, SECRET_KEY, algorithm="HS256")
            session['token'] = token
            flash('Login successful!', 'success')
            if is_admin(email):
                return redirect(url_for('dashboard'))  # Admin goes to dashboard
            elif user[7] == 1:  # Approved non-admin user
                return redirect(url_for('profiles'))  # Redirect to profiles for now
            else:
                return render_template('login.html')  # Should not reach here due to approval check
        else:
            flash('Invalid email or password.', 'error')
            return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        current_year = datetime.datetime.now().year
        return render_template('register.html', current_year=current_year)
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        contact = request.form.get('contact')
        passed_out_year = request.form.get('passed_out_year')
        photo = request.files.get('photo')
        password = request.form.get('password')

        missing_fields = []
        if not name: missing_fields.append("name")
        if not email: missing_fields.append("email")
        if not contact: missing_fields.append("contact")
        if not passed_out_year: missing_fields.append("passed_out_year")
        if not password: missing_fields.append("password")

        if missing_fields:
            flash(f'Missing required fields: {", ".join(missing_fields)}.', 'error')
            return jsonify({'message': f'Missing required fields: {", ".join(missing_fields)}', 'success': False}), 400

        if not 1900 <= int(passed_out_year) <= datetime.datetime.now().year:
            flash('Invalid passed-out year.', 'error')
            return jsonify({'message': 'Invalid passed-out year.', 'success': False}), 400

        password_hash = hashlib.sha256(password.encode()).hexdigest()
        filename, error = save_file(photo) if photo else (None, None)
        if error:
            flash(error, 'error')
            return jsonify({'message': error, 'success': False}), 400

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        try:
            approved = 1 if is_admin(email) else 0
            c.execute("INSERT INTO users (name, email, password, contact, passed_out_year, photo, approved) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                      (name, email, password_hash, contact, passed_out_year, filename, approved))
            conn.commit()
            send_welcome_email(email, name)  # Send welcome email
            message = 'Registration successful! ' + ('Please wait for admin approval.' if not approved else 'Please proceed to login.')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'message': message, 'success': True}), 200
            else:
                flash(message, 'success')
                return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email already registered.', 'error')
            return jsonify({'message': 'Email already registered.', 'success': False}), 400
        finally:
            conn.close()

@app.route('/dashboard')
@token_required
def dashboard():
    token = session['token']
    data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    email = data['email']

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE email = ?", (email,))
    user = c.fetchone()
    if not user:
        conn.close()
        flash('User not found. Please register.', 'error')
        return redirect(url_for('register'))
    user_id = user[0]
    conn.close()

    registrations = get_user_registrations(user_id)
    notifications = get_upcoming_events()
    current_year = datetime.datetime.now().year
    return render_template('dashboard.html', registrations=registrations, notifications=notifications, current_year=current_year, is_admin=is_admin(email))

@app.route('/current_user_session')
@token_required
def current_user_session():
    token = session['token']
    data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    email = data['email']
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT name, email, contact, photo, passed_out_year, approved FROM users WHERE email = ?", (email,))
    user = c.fetchone()
    conn.close()
    
    if user:
        return jsonify({'name': user[0], 'email': user[1], 'contact': user[2], 'photo': user[3], 'passed_out_year': user[4], 'approved': user[5]})
    flash('User not found.', 'error')
    return jsonify({'message': 'User not found'}), 404

@app.route('/update_profile', methods=['POST'])
@token_required
def update_profile():
    token = session['token']
    data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    email = data['email']

    name = request.form.get('name')
    new_email = request.form.get('email')
    contact = request.form.get('contact')
    passed_out_year = request.form.get('passed_out_year')
    password = request.form.get('password')
    photo = request.files.get('photo')

    if not all([name, new_email, contact, passed_out_year]):
        flash('All fields are required except password and photo.', 'error')
        return jsonify({'message': 'All fields are required except password and photo'}), 400

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute("SELECT id FROM users WHERE email = ? AND email != ?", (new_email, email))
    if c.fetchone():
        conn.close()
        flash('Email already in use by another user.', 'error')
        return jsonify({'message': 'Email already in use'}), 400

    photo_filename = None
    if photo and allowed_file(photo.filename):
        filename, error = save_file(photo)
        if error:
            conn.close()
            flash(error, 'error')
            return jsonify({'message': error}), 400
        photo_filename = filename
        if photo_filename:
            c.execute("SELECT photo FROM users WHERE email = ?", (email,))
            old_photo = c.fetchone()[0]
            if old_photo and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], old_photo)):
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], old_photo))

    if password:
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        if photo_filename:
            c.execute("UPDATE users SET name = ?, email = ?, contact = ?, passed_out_year = ?, password = ?, photo = ? WHERE email = ?", 
                      (name, new_email, contact, passed_out_year, password_hash, photo_filename, email))
        else:
            c.execute("UPDATE users SET name = ?, email = ?, contact = ?, passed_out_year = ?, password = ? WHERE email = ?", 
                      (name, new_email, contact, passed_out_year, password_hash, email))
    else:
        if photo_filename:
            c.execute("UPDATE users SET name = ?, email = ?, contact = ?, passed_out_year = ?, photo = ? WHERE email = ?", 
                      (name, new_email, contact, passed_out_year, photo_filename, email))
        else:
            c.execute("UPDATE users SET name = ?, email = ?, contact = ?, passed_out_year = ? WHERE email = ?", 
                      (name, new_email, contact, passed_out_year, email))
    
    conn.commit()
    conn.close()

    if new_email != email:
        token = jwt.encode({
            'email': new_email,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        }, SECRET_KEY, algorithm="HS256")
        session['token'] = token

    flash('Profile updated successfully!', 'success')
    return jsonify({'message': 'Profile updated successfully', 'new_email': new_email})

@app.route('/register_event', methods=['POST'])
@token_required
def register_event():
    token = session['token']
    data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    email = data['email']

    data = request.get_json()
    if not data:
        flash('Invalid request.', 'error')
        return jsonify({'message': 'Invalid request'}), 400

    event_id = data.get('event_id')
    if not event_id:
        flash('Event ID is required.', 'error')
        return jsonify({'message': 'Event ID is required'}), 400

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute("SELECT id FROM users WHERE email = ?", (email,))
    user = c.fetchone()
    if not user:
        conn.close()
        flash('User not found.', 'error')
        return jsonify({'message': 'User not found'}), 404
    user_id = user[0]

    c.execute("SELECT * FROM event_registrations WHERE user_id = ? AND event_id = ?", (user_id, event_id))
    if c.fetchone():
        conn.close()
        flash('You are already registered for this event.', 'error')
        return jsonify({'message': 'You are already registered for this event'}), 400

    c.execute("INSERT INTO event_registrations (user_id, event_id) VALUES (?, ?)", (user_id, event_id))
    conn.commit()
    conn.close()

    flash('Successfully registered for the event!', 'success')
    return jsonify({'message': 'Successfully registered for the event'})

@app.route('/admin', methods=['GET', 'POST'])
@token_required
def admin():
    token = session['token']
    data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    email = data['email']

    if not is_admin(email):
        flash('Access denied. Admins only.', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        data = request.get_json()
        if not data:
            return jsonify({'message': 'Invalid request'}), 400

        action = data.get('action')
        conn = sqlite3.connect('database.db')
        c = conn.cursor()

        try:
            if action == 'add':
                title = data.get('title')
                date = data.get('date')
                if not title or not date:
                    return jsonify({'message': 'Title and date are required'}), 400
                c.execute("INSERT INTO events (title, date) VALUES (?, ?)", (title, date))
            elif action == 'delete':
                event_id = data.get('event_id')
                if not event_id:
                    return jsonify({'message': 'Event ID is required'}), 400
                c.execute("DELETE FROM events WHERE id = ?", (event_id,))
                c.execute("DELETE FROM event_registrations WHERE event_id = ?", (event_id,))
            elif action == 'edit':
                event_id = data.get('event_id')
                title = data.get('title')
                date = data.get('date')
                if not event_id or not title or not date:
                    return jsonify({'message': 'Event ID, title, and date are required'}), 400
                c.execute("UPDATE events SET title = ?, date = ? WHERE id = ?", (title, date, event_id))
            elif action == 'approve':
                user_id = data.get('user_id')
                if not user_id:
                    return jsonify({'message': 'User ID is required'}), 400
                c.execute("UPDATE users SET approved = 1 WHERE id = ?", (user_id,))
            elif action == 'reject':
                user_id = data.get('user_id')
                if not user_id:
                    return jsonify({'message': 'User ID is required'}), 400
                c.execute("DELETE FROM users WHERE id = ? AND email != 'admin@ksrmce.ac.in'", (user_id,))
            else:
                return jsonify({'message': 'Invalid action'}), 400

            conn.commit()
            return jsonify({'message': 'Success'})
        except Exception as e:
            conn.rollback()
            return jsonify({'message': f'Server error: {str(e)}'}), 500
        finally:
            conn.close()

    events = get_events()
    users = get_user_profiles()  # Fetch all users for approval
    return render_template('admin.html', events=events, users=users, is_admin=is_admin(email))

@app.route('/send_message', methods=['POST'])
@token_required
def send_message():
    token = session['token']
    data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    email = data['email']

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE email = ?", (email,))
    sender = c.fetchone()
    if not sender:
        conn.close()
        return jsonify({'message': 'Sender not found'}), 404
    sender_id = sender[0]

    receiver_id = request.form.get('receiver_id')
    message = request.form.get('message')
    attachment = request.files.get('attachment')

    if not receiver_id:
        conn.close()
        return jsonify({'message': 'Receiver ID is required'}), 400

    if not message and not attachment:
        conn.close()
        return jsonify({'message': 'Either a message or an attachment is required'}), 400

    if sender_id == int(receiver_id):
        conn.close()
        return jsonify({'message': 'You cannot send a message to yourself'}), 400

    attachment_path = None
    if attachment:
        filename, error = save_file(attachment)
        if error:
            conn.close()
            return jsonify({'message': error}), 400
        attachment_path = filename

    try:
        c.execute("INSERT INTO messages (sender_id, receiver_id, message, attachment) VALUES (?, ?, ?, ?)", 
                  (sender_id, receiver_id, message or "", attachment_path))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'message': f'Failed to send message: {str(e)}'}), 500
    finally:
        conn.close()

    return jsonify({'message': 'Message sent successfully'})

@app.route('/get_conversation/<int:receiver_id>', methods=['GET'])
@token_required
def get_conversation_route(receiver_id):
    token = session['token']
    data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    email = data['email']

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE email = ?", (email,))
    sender = c.fetchone()
    if not sender:
        conn.close()
        return jsonify({'message': 'Sender not found'}), 404
    sender_id = sender[0]

    messages = get_conversation(sender_id, receiver_id)
    return jsonify({'messages': messages})

@app.route('/logout')
def logout():
    session.pop('token', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    migrate_db()
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT email FROM users WHERE email = 'admin@ksrmce.ac.in'")
    if not c.fetchone():
        password_hash = hashlib.sha256("Admin123!".encode()).hexdigest()
        c.execute("INSERT INTO users (name, email, password, approved) VALUES (?, ?, ?, ?)", 
                  ("Admin User", "admin@ksrmce.ac.in", password_hash, 1))  # Explicitly set approved = 1
    c.execute("INSERT OR IGNORE INTO events (title, date) VALUES (?, ?)", 
              ("Alumni Reunion 2025", "2025-06-15"))
    c.execute("INSERT OR IGNORE INTO events (title, date) VALUES (?, ?)", 
              ("Job Fair 2025", "2025-07-10"))
    conn.commit()
    conn.close()
    app.run(debug=True, host='0.0.0.0', port=5000)