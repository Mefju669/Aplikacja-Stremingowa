from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
from db import *
import secrets
import os
from flask_login import LoginManager, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
import random
from datetime import datetime, timedelta
import time
import cv2

# Inicjalizacja aplikacji Flask
app = Flask(__name__)

# Ustawienie sekretnego klucza dla sesji, generowane losowo za każdym razem, gdy aplikacja się uruchamia
app.secret_key = secrets.token_hex(16)

# Konfiguracja bazy danych
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'database.db')
db.init_app(app)

# Utworzenie wszystkich tabel w bazie danych, jeśli nie istnieją
with app.app_context():
    db.create_all()

# Konfiguracja kamery
camera = cv2.VideoCapture(0)

def gen_frames():
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# Główna strona aplikacji
@app.route('/')
def index():
    return render_template('index.html', current_user=session.get('current_user'))

# Strona i logika rejestracji użytkownika
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']

        existing_user = User.query.filter_by(Name=username).first()
        if existing_user:
            error_message = "Użytkownik o tej nazwie już istnieje. Proszę wybrać inną nazwę."
            return render_template('register.html', error_message=error_message)
        existing_user = User.query.filter_by(Email=email).first()
        if existing_user:
            error_message = "Użytkownik o podanym adresie email już istnieje. Może chcesz się <a href='/login'>zalogować</a>?"
            return render_template('register.html', error_message=error_message)

        new_user = User(Name=username, Password=password, Email=email)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

# Strona i logika logowania użytkownika
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(Name=username, Password=password).first()
        if user and user.Password == password:
            session['user_id'] = user.UserID
            session['current_user'] = user.Name
            return redirect(url_for('index'))
        else:
            error_message = "Nieprawidłowa nazwa użytkownika lub hasło. Spróbuj ponownie!"
            return render_template('login.html', error_message=error_message)
    return render_template('login.html')

def get_chat_history(meeting_id):
    chat_history = ChatMessage.query.filter_by(MeetingID=meeting_id).order_by(ChatMessage.MessageID.asc()).all()
    return chat_history

@app.route('/logout', methods=['GET'])
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/join_room', methods=['GET', 'POST'])
def join_room():
    current_user = session.get('current_user')
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        room_code = request.form['room_code']
        if not room_code.isdigit():
            flash('Kod pokoju musi składać się tylko z cyfr.', 'error')
            return redirect(url_for('join_room'))

        meeting = Meeting.query.filter_by(MeetingID=room_code).first()
        if meeting is None:
            flash('Nie ma spotkania o podanym kodzie.', 'error')
            return redirect(url_for('join_room'))

        session['meeting_id'] = room_code
        join_meeting(room_code)
        return redirect(url_for('room', room_code=room_code))

    return render_template('join_room.html', current_user=current_user)

@app.route('/create_room', methods=['GET', 'POST'])
def create_room():
    current_user = session.get('current_user')
    if 'user_id' not in session:
        return redirect(url_for('login'))

    room_code = session.pop('room_code', '')

    if request.method == 'POST':
        room_code = request.form['room_code']
        if not room_code.isdigit():
            flash('Kod pokoju musi składać się tylko z cyfr.', 'error')
            return redirect(url_for('create_room'))

        existing_meeting = Meeting.query.filter_by(MeetingID=room_code).first()
        if existing_meeting:
            flash('Spotkanie o podanym kodzie już istnieje.', 'error')
            return redirect(url_for('create_room'))

        meeting = Meeting(MeetingID=room_code)
        db.session.add(meeting)
        db.session.commit()
        return redirect(url_for('join_room', room_code=room_code))

    return render_template('create_room.html', current_user=current_user, room_code=room_code)

def join_meeting(meeting_id):
    meeting = Meeting.query.get(meeting_id)
    if meeting:
        meeting.attendees_count += 1
        db.session.commit()
    else:
        raise ValueError("Meeting not found.")

@app.route('/redirect_and_leave', methods=['GET', 'POST'])
def redirect_and_leave():
    meeting_id = session.get('meeting_id')
    if meeting_id:
        leave_meeting(meeting_id)
    return redirect(url_for('index'))

def leave_meeting(meeting_id):
    meeting = Meeting.query.get(meeting_id)
    if meeting and meeting.attendees_count > 0:
        meeting.attendees_count -= 1
        db.session.commit()
    elif meeting:
        raise ValueError("No attendees to leave the meeting.")
    else:
        raise ValueError("Meeting not found.")

def remove_inactive_meetings():
    while True:
        current_time = datetime.now()
        if current_time.minute % 10 == 0:
            inactive_meetings = Meeting.query.filter_by(attendees_count=0).all()
            for meeting in inactive_meetings:
                db.session.delete(meeting)
            db.session.commit()
        time.sleep(60)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    current_user = session.get('current_user')
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        user = User.query.filter_by(UserID=user_id).first()

        if password != confirm_password:
            flash('Hasła nie są identyczne.', 'error')
            return redirect(url_for('settings'))

        if username:
            user.Name = username
        if email:
            user.Email = email
        if password:
            user.Password = password

        db.session.commit()

        flash('Zmiany zostały zapisane.', 'success')
        return redirect(url_for('settings'))

    current_email = User.query.filter_by(Name=current_user).first().Email
    return render_template('settings.html', current_user=current_user, current_email=current_email)

def handle_message(msg, meeting_id):
    new_message = ChatMessage(UserID=session['user_id'], MeetingID=meeting_id, MessageContent=msg)
    db.session.add(new_message)
    db.session.commit()

@app.route('/room/<int:room_code>', methods=['GET', 'POST'])
def room(room_code):
    current_user = session.get('current_user')
    if 'user_id' not in session:
        return redirect(url_for('login'))

    meeting = Meeting.query.filter_by(MeetingID=room_code).first()
    if not meeting:
        flash('Spotkanie o podanym kodzie nie istnieje.', 'error')
        return redirect(url_for('join_room'))
    chat_history = get_chat_history(room_code)

    return render_template('room.html', current_user=current_user, room_code=room_code, chat_history=chat_history)

@app.route('/send_message/<int:room_code>', methods=['POST'])
def send_message(room_code):
    message = request.form['message']
    handle_message(message, room_code)
    return redirect(url_for('room', room_code=room_code))

@app.route('/faq')
def faq():
    return render_template('faq.html')

@app.route('/about')
def about():
    return render_template('about.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
