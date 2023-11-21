# Importing Werkzeug security helpers for password hashing and verification.
from werkzeug.security import generate_password_hash, check_password_hash
# Flask-Login's UserMixin adds Flask-Login's required properties and methods to the User model.
from flask_login import UserMixin
# Importing func from SQLAlchemy for SQL function support (like NOW() for the current time).
from sqlalchemy.sql import func
# datetime module for handling date and time operations.
from datetime import datetime
# Importing the database instance from the current application context.
from . import db

# Intermediate association table to represent a many-to-many relationship between User and OAuth10a/OAuth2PKCE.
user_oauth_association_table = db.Table('user_oauth_association', db.Model.metadata,
                                        db.Column('user_email', db.String(150), db.ForeignKey('All_Users.email')),
                                        db.Column('oauth10a_email', db.String(150),
                                                  db.ForeignKey('OAuth10a_3Legged.email')),
                                        db.Column('oauth20pkce_email', db.String(150),
                                                  db.ForeignKey('OAuth20_PKCE.email')),
                                        )


class User(db.Model, UserMixin):
    """
    User model representing a user in the application's database.
    Inherits from db.Model for SQLAlchemy integration and UserMixin for Flask-Login functionalities.
    """
    __tablename__ = 'All_Users'  # Explicitly naming the database table.

    # Database columns:
    email = db.Column(db.String(150), unique=True, primary_key=True)  # Email as primary key.
    id = db.Column(db.Integer, unique=True, nullable=True, autoincrement=True)  # Auto-incremented user ID.
    twitter_id = db.Column(db.Integer, unique=True, nullable=True)  # Twitter ID for OAuth.
    account_name = db.Column(db.String(150), unique=True, nullable=False)  # Account name.
    password = db.Column(db.String(150), nullable=False)  # Password hash.
    date_created = db.Column(db.DateTime(timezone=True), default=func.now())  # Timestamp of account creation.
    verified = db.Column(db.Boolean, default=False)  # Flag for verifying the user's email.

    # Relationships to OAuth tables (one-to-many):
    oauth10a = db.relationship('OAuth10a', backref='user', lazy=True)
    oauth20pkce = db.relationship('OAuth20PKCE', backref='user', lazy=True)

    def get_id(self):
        """
        Override the method from Flask-Login's UserMixin.
        Flask-Login uses this to get a unique identifier for the user session.
        """
        return str(self.email)


# Explanation for OAuth10a, UserReportingActivity, and OAuth20PKCE models continues.
# Each class reflects a specific table in the database with tailored columns and relationships.


class OAuth10a(db.Model):
    """
    Represents an OAuth 1.0a credential record associated with a user.
    This model is designed to store the necessary data for OAuth 1.0a authentication flow.
    """
    __tablename__ = 'OAuth10a_3Legged'  # Explicitly setting a table name.

    # Database columns definition:
    email = db.Column(db.String(150), db.ForeignKey('All_Users.email'), nullable=False, unique=True, primary_key=True)
    twitter_id = db.Column(db.Integer, unique=True, nullable=False)  # Twitter ID associated with the OAuth credential.
    account_name = db.Column(db.String(150), nullable=False)  # Account name linked to the OAuth credential.
    date_created = db.Column(db.DateTime(timezone=True), default=func.now())  # Timestamp of creation.
    last_token_refresh_date = db.Column(db.DateTime(timezone=True), default=func.now())  # Timestamp for the last
    # token refresh.
    oauth_verifier = db.Column(db.String(150), nullable=False)  # OAuth verifier token.
    oauth_token = db.Column(db.String(150), nullable=False)  # OAuth token.
    oauth_token_secret = db.Column(db.String(150), nullable=False)  # OAuth token secret (stored securely).
    previous_twitter_account_info = db.Column(db.String, nullable=True)  # Stores previous Twitter account
    # information if available.

    @property
    def oauth_token_secret_hash(self):
        """
        Property to make oauth_token_secret a non-readable attribute.
        This prevents accidental exposure of sensitive token secrets.
        """
        raise AttributeError('oauth_token_secret is not a readable attribute')

    @oauth_token_secret_hash.setter
    def oauth_token_secret_hash(self, oauth_token_secret):
        """
        Setter for the oauth_token_secret_hash.
        Automatically hashes the token secret using Werkzeug's generate_password_hash function.
        :param oauth_token_secret: The plaintext OAuth token secret.
        """
        self.oauth_token_secret = generate_password_hash(oauth_token_secret)

    def check_token_secret(self, oauth_token_secret):
        """
        Verifies an OAuth token secret against the hashed version stored in the database.
        :param oauth_token_secret: The plaintext OAuth token secret to verify.
        :return: Boolean indicating whether the secret is correct.
        """
        return check_password_hash(self.oauth_token_secret, oauth_token_secret)


# The UserReportedActivity model tracks impersonators handled by users.
class UserReportingActivity(db.Model):
    """
    Model representing Twitter activities (muted, blocked, reported accounts) associated with a user account.
    This model stores details about the Twitter activities performed by users.
    """
    __tablename__ = 'UserReportingActivity'  # Renaming the table

    # Primary key and Foreign key relationship with All_Users table
    email = db.Column(db.String(150), db.ForeignKey('All_Users.email'), nullable=False, primary_key=True)

    # Other attributes
    twitter_id = db.Column(db.Integer, nullable=False)  # Twitter ID of the user
    username = db.Column(db.String(50), nullable=False)  # Username of the user
    muted = db.Column(db.Text, nullable=True)  # Stores muted accounts as a comma-separated string
    muted_nr = db.Column(db.Integer, nullable=True)  # Number of muted accounts
    blocked = db.Column(db.Text, nullable=True)  # Stores blocked accounts
    blocked_nr = db.Column(db.Integer, nullable=True)  # Number of blocked accounts
    reported_as_spam = db.Column(db.Text, nullable=True)  # Stores accounts reported as spam
    reported_as_spam_nr = db.Column(db.Integer, nullable=True)  # Number of accounts reported as spam
    reported_impersonation = db.Column(db.Text, nullable=True)  # Stores accounts reported for impersonation
    reported_impersonation_nr = db.Column(db.Integer, nullable=True)  # Number of accounts reported for impersonation
    last_updated = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)  # Last update timestamp

    def __repr__(self):
        return (f"<UserReportingActivity {self.email}: "
                f"Muted: {self.muted_nr}, Blocked: {self.blocked_nr}, "
                f"Reported Spam: {self.reported_as_spam_nr}, Reported Impersonation: {self.reported_impersonation_nr}>")


# The OAuth20PKCE model represents OAuth 2.0 PKCE credentials linked to a user account.
class OAuth20PKCE(db.Model):
    """
    Model representing an OAuth 2.0 PKCE credential record for a user.
    This model stores data necessary for the OAuth 2.0 PKCE authentication flow.
    """
    __tablename__ = 'OAuth20_PKCE'  # Setting the table name.

    # Database columns for OAuth 2.0 PKCE credentials.
    email = db.Column(db.String(150), db.ForeignKey('All_Users.email'), nullable=False, unique=True, primary_key=True)
    twitter_id = db.Column(db.Integer, unique=True, nullable=True)  # Twitter ID associated with the OAuth credential.
    account_name = db.Column(db.String(150), nullable=True)  # Account name linked to the OAuth credential.
    date_created = db.Column(db.DateTime(timezone=True), default=func.now())  # Timestamp of creation.
    access_token = db.Column(db.String(150), nullable=True)  # OAuth access token.
    refresh_token = db.Column(db.String(150), nullable=True)  # OAuth refresh token.
    state = db.Column(db.String(255), nullable=True)  # State parameter for additional security in OAuth flow.
    code_verifier = db.Column(db.String(150), nullable=False)  # Code verifier for PKCE.
    code_challenge = db.Column(db.String(150), nullable=True)  # Code challenge for PKCE.
    code_challenge_method = db.Column(db.String(150), nullable=True)  # Method used for code challenge in PKCE.
    last_token_refresh_date = db.Column(db.DateTime(timezone=True), default=func.now())  # Timestamp for the last
    # token refresh.
    access_token_expires_in = db.Column(db.Integer, nullable=True)  # Expiry time for the access token.
