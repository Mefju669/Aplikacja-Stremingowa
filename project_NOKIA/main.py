from flask import Flask, render_template, request, redirect, url_for, session, flash
from db import *
import secrets
import os
from flask_login import LoginManager, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
import random
from datetime import datetime, timedelta
from threading import Thread
import time

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

# Główna strona aplikacji
@app.route('/')
def index():
    # Wyświetlanie strony głównej z aktualnie zalogowanym użytkownikiem
    return render_template('index.html', current_user=session.get('current_user'))

# Strona i logika rejestracji użytkownika
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Pobieranie danych z formularza
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']

        # Sprawdzenie, czy użytkownik już istnieje w bazie danych
        existing_user = User.query.filter_by(Name=username).first()
        if existing_user:
            error_message = "Użytkownik o tej nazwie już istnieje. Proszę wybrać inną nazwę."
            return render_template('register.html', error_message=error_message)
        existing_user = User.query.filter_by(Email=email).first()
        if existing_user:
            error_message = "Użytkownik o podanym adresie email już istnieje. Może chcesz się <a href='/login'>zalogować</a>?"
            return render_template('register.html', error_message=error_message)

        # Rejestracja nowego użytkownika
        new_user = User(Name=username, Password=password, Email=email)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

# Strona i logika logowania użytkownika
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Pobieranie danych z formularza
        username = request.form['username']
        password = request.form['password']

        # Sprawdzenie, czy dane logowania są poprawne
        user = User.query.filter_by(Name=username, Password=password).first()
        if user and user.Password == password:
            # Ustawienie sesji użytkownika
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

# Trasa odpowiedzialna za wylogowanie użytkownika
@app.route('/logout', methods=['GET'])
def logout():
    session.clear()  # Usunięcie wszystkich danych z sesji
    return redirect(url_for('login'))  # Przekierowanie do strony logowania

@app.route('/join_room', methods=['GET', 'POST'])
def join_room():
    current_user = session.get('current_user')
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Pobieranie kodu identyfikującego pokój z formularza
        room_code = request.form['room_code']
    
        # Sprawdzanie, czy kod składa się tylko z cyfr
        if not room_code.isdigit():
            flash('Kod pokoju musi składać się tylko z cyfr.', 'error')
            return redirect(url_for('join_room'))

        # Sprawdzanie, czy istnieje spotkanie o podanym kodzie w bazie danych
        meeting = Meeting.query.filter_by(MeetingID=room_code).first()
        if meeting is None:
            flash('Nie ma spotkania o podanym kodzie.', 'error')
            return redirect(url_for('join_room'))
        
        # Dodanie meeting_id do sesji
        session['meeting_id'] = room_code
        join_meeting(room_code)
        # Przekierowanie do strony room.html
        return redirect(url_for('room', room_code=room_code))
    
    return render_template('join_room.html', current_user=current_user)

@app.route('/create_room', methods=['GET', 'POST'])
def create_room():
    current_user = session.get('current_user')
    if 'user_id' not in session:
        return redirect(url_for('login'))

    room_code = session.pop('room_code', '')  # Pobranie wartości room_code z sesji

    if request.method == 'POST':
        # Pobieranie kodu identyfikującego pokoju z formularza
        room_code = request.form['room_code']

        # Sprawdzanie, czy kod składa się tylko z cyfr
        if not room_code.isdigit():
            flash('Kod pokoju musi składać się tylko z cyfr.', 'error')
            return redirect(url_for('create_room'))

        # Sprawdzanie, czy istnieje już spotkanie o podanym kodzie w bazie danych
        existing_meeting = Meeting.query.filter_by(MeetingID=room_code).first()
        if existing_meeting:
            flash('Spotkanie o podanym kodzie już istnieje.', 'error')
            return redirect(url_for('create_room'))

        # Dodanie spotkania do bazy danych
        meeting = Meeting(MeetingID=room_code)
        db.session.add(meeting)
        db.session.commit()

        # Przekierowanie do strony join_room.html z już wpisanym kodem spotkania
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


# Trasa do zarządzania ustawieniami użytkownika
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
        
        user = User.query.filter_by(UserID=user_id).first()  # Pobranie danych użytkownika

        if password != confirm_password:
            flash('Hasła nie są identyczne.', 'error')  # Komunikat o błędzie
            return redirect(url_for('settings'))

        # Aktualizacja danych użytkownika
        if username:
            user.Name = username
        if email:
            user.Email = email
        if password:
            user.Password = password

        db.session.commit()  # Zapisanie zmian w bazie danych

        flash('Zmiany zostały zapisane.', 'success')  # Komunikat o sukcesie
        return redirect(url_for('settings'))

    current_email = User.query.filter_by(Name=current_user).first().Email  # Pobranie aktualnego emaila użytkownika
    return render_template('settings.html', current_user=current_user, current_email=current_email)

def handle_message(msg, meeting_id):
    print(f"Message: {msg}")
    # Tworzenie nowego obiektu wiadomości czatu
    new_message = ChatMessage(UserID=session['user_id'], MeetingID=meeting_id, MessageContent=msg)
    # Dodanie nowej wiadomości do sesji SQLAlchemy
    db.session.add(new_message)
    # Zatwierdzenie zmian w bazie danych
    db.session.commit()

@app.route('/room/<int:room_code>', methods=['GET', 'POST'])
def room(room_code):
    current_user = session.get('current_user')
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Sprawdzenie, czy spotkanie o danym kodzie istnieje w bazie danych
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


def remove_inactive_meetings():
    while True:
        with app.app_context():
            # Wyszukiwanie wszystkich spotkań z liczbą uczestników równą 0
            inactive_meetings = Meeting.query.filter_by(attendees_count=0).all()
            if inactive_meetings:
                for meeting in inactive_meetings:
                    db.session.delete(meeting)
                db.session.commit()
                print("Removed inactive meetings.")
        time.sleep(600)  # Pauza na 10 min przed kolejnym sprawdzeniem

# Tworzenie i uruchamianie wątku w tle
def start_background_task():
    thread = Thread(target=remove_inactive_meetings)
    thread.daemon = True 
    thread.start()
    

with app.app_context():
    start_background_task()    



# Trasa do strony FAQ
@app.route('/faq')
def faq():
    remove_inactive_meetings
    return render_template('faq.html')  # Wyświetlenie strony FAQ

# Trasa do strony O nas
@app.route('/about')
def about():
    return render_template('about.html')  # Wyświetlenie strony O nas

if __name__ == '__main__':
    start_background_task()
    app.run(debug=True)