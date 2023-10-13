from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from sqlalchemy.sql import func
from datetime import datetime
from . import db


# Intermediate table to represent the many-to-many relationship between User and OAuth10a/OAuth2PKCE
user_oauth_association_table = db.Table('user_oauth_association', db.Model.metadata,
                                        db.Column('user_email', db.String(150), db.ForeignKey('All_Users.email')),
                                        db.Column('oauth10a_email', db.String(150), db.ForeignKey('OAuth10a_3Legged'
                                                                                                  '.email')),
                                        db.Column('note_email', db.String(150), db.ForeignKey('Notes.email')),
                                        db.Column('oauth20pkce_email', db.String(150), db.ForeignKey('OAuth20_PKCE'
                                                                                                     '.email')),
                                        db.Column('post_email', db.String(150), db.ForeignKey('Posts.email'))
                                        )


class User(db.Model, UserMixin):
    __tablename__ = 'All_Users'
    email = db.Column(db.String(150), unique=True, primary_key=True)
    id = db.Column(db.Integer, unique=True, nullable=True, autoincrement=True)
    twitter_id = db.Column(db.Integer, unique=True, nullable=True)  # Added twitter_id here
    account_name = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    date_created = db.Column(db.DateTime(timezone=True), default=func.now())
    verified = db.Column(db.Boolean, default=False)
    oauth10a = db.relationship('OAuth10a', backref='user', lazy=True)  # many-to-many relationship
    oauth20pkce = db.relationship('OAuth20PKCE', backref='user', lazy=True)  # many-to-many relationship
    notes = db.relationship('Note', backref='user', lazy=True)  # one-to-many relationship
    posts = db.relationship('Post', backref='author', lazy=True)

    def get_id(self):
        return str(self.email)


class Post(db.Model):
    __tablename__ = 'Posts'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), db.ForeignKey('All_Users.email'), nullable=False)
    twitter_id = db.Column(db.Integer, unique=True, nullable=False)
    title = db.Column(db.String(100), nullable=False)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    content = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f"Post('{self.title}', '{self.date_posted}')"


class Note(db.Model):
    __tablename__ = 'Notes'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), db.ForeignKey('All_Users.email'), nullable=False)
    twitter_id = db.Column(db.Integer, nullable=True)
    account_name = db.Column(db.String(150), nullable=True)
    date_created = db.Column(db.DateTime(timezone=True), default=func.now(), nullable=False)
    title = db.Column(db.String(100), nullable=True)
    data = db.Column(db.Text, nullable=False)

    def __repr__(self):
        return f"<Note {self.id} '{self.title}' created at {self.date_created} by {self.email}>"


class OAuth10a(db.Model):
    __tablename__ = 'OAuth10a_3Legged'
    email = db.Column(db.String(150), db.ForeignKey('All_Users.email'), nullable=False, unique=True, primary_key=True)
    twitter_id = db.Column(db.Integer, unique=True, nullable=False)  # Updated to twitter_id
    account_name = db.Column(db.String(150), nullable=False)
    date_created = db.Column(db.DateTime(timezone=True), default=func.now())
    last_token_refresh_date = db.Column(db.DateTime(timezone=True), default=func.now())
    oauth_verifier = db.Column(db.String(150), nullable=False)
    oauth_token = db.Column(db.String(150), nullable=False)
    oauth_token_secret = db.Column(db.String(150), nullable=False)
    previous_twitter_account_info = db.Column(db.String, nullable=True)

    @property
    def oauth_token_secret_hash(self):
        raise AttributeError('oauth_token_secret is not a readable attribute')

    @oauth_token_secret_hash.setter
    def oauth_token_secret_hash(self, oauth_token_secret):
        self.oauth_token_secret = generate_password_hash(oauth_token_secret)

    def check_token_secret(self, oauth_token_secret):
        return check_password_hash(self.oauth_token_secret, oauth_token_secret)


class UserReportedImpersonator(db.Model):
    __tablename__ = 'UserReportedImpersonator'
    email = db.Column(db.String(150), db.ForeignKey('All_Users.email'), nullable=False, unique=True, primary_key=True)
    twitter_id = db.Column(db.Integer, unique=True, nullable=False)  # Updated to twitter_id
    screen_name = db.Column(db.String(50), nullable=False)
    muted = db.Column(db.Integer, nullable=False, default=0)
    blocked = db.Column(db.Integer, nullable=False, default=0)
    reported = db.Column(db.Integer, nullable=False, default=0)
    impersonator = db.Column(db.String(50), nullable=False)
    report_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<UserReportedImpersonator {self.id}: {self.screen_name}" \
               f" reported {self.impersonator} on {self.report_date}>"


class OAuth20PKCE(db.Model):
    __tablename__ = 'OAuth20_PKCE'
    email = db.Column(db.String(150), db.ForeignKey('All_Users.email'), nullable=False, unique=True, primary_key=True)
    twitter_id = db.Column(db.Integer, unique=True, nullable=True)  # Updated to twitter_id
    account_name = db.Column(db.String(150), nullable=True)
    date_created = db.Column(db.DateTime(timezone=True), default=func.now())
    access_token = db.Column(db.String(150), nullable=True)
    refresh_token = db.Column(db.String(150), nullable=True)
    state = db.Column(db.String(255), nullable=True)
    code_verifier = db.Column(db.String(150), nullable=False)
    code_challenge = db.Column(db.String(150), nullable=True)
    code_challenge_method = db.Column(db.String(150), nullable=True)
    last_token_refresh_date = db.Column(db.DateTime(timezone=True), default=func.now())
    access_token_expires_in = db.Column(db.Integer, nullable=True)
