from flask_sqlalchemy import SQLAlchemy


# Inicjalizacja obiektu SQLAlchemy
db = SQLAlchemy()

# Model tabeli Users
class User(db.Model):
    UserID = db.Column(db.Integer, primary_key=True)
    Name = db.Column(db.String(255))
    Email = db.Column(db.String(255))
    Password = db.Column(db.String(255))


# Model tabeli Meetings
class Meeting(db.Model):
    MeetingID = db.Column(db.Integer, primary_key=True)
    attendees_count = db.Column(db.Integer, default=0)  


# Model tabeli ChatMessage
class ChatMessage(db.Model):
    MessageID = db.Column(db.Integer, primary_key=True)
    UserID = db.Column(db.Integer, db.ForeignKey('user.UserID'))
    MeetingID = db.Column(db.Integer, db.ForeignKey('meeting.MeetingID'))
    MessageContent = db.Column(db.String(1000))

    user = db.relationship('User', backref='messages')
    meeting = db.relationship('Meeting', backref='messages')
