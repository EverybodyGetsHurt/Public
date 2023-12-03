"""
This script defines the database models for a Flask application, primarily focused on handling user authentication,
OAuth credentials, and Twitter cookie data. It uses Flask-SQLAlchemy for ORM capabilities, integrating seamlessly
with Flask's ecosystem. The models include User, OAuth10a, OAuth20PKCE, and TwitterCookies, each representing a
specific domain within the application.

Key Features:
- User: Represents application users with attributes like email, password, and OAuth credentials.
- OAuth10a and OAuth20PKCE: Handle different OAuth authentication flows and store related data.
- TwitterCookies: Stores Twitter-related authentication and session data for interacting with Twitter's API.
- Relationships: Establishes connections between different models for referential integrity and data retrieval ease.
- Security: Implements password hashing and secure storage of sensitive information.

Each model is equipped with detailed docstrings explaining its
purpose, relationships, and the significance of each field.
"""

from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Table, Text, Boolean, func
from werkzeug.security import generate_password_hash, check_password_hash  # Werkzeug's security helpers for hashing.
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from flask_login import UserMixin  # UserMixin adds required properties/methods for Flask-Login user models.

# Configure the connection to your SQLite database
DATABASE_URI = 'sqlite:///database.sqlite'  # Replace with your database path
engine = create_engine(DATABASE_URI, echo=True)

Base = declarative_base()

# This table establishes a many-to-many relationship between the User model and OAuth models (OAuth10a and OAuth20PKCE).
# It is not a model itself but an association table to link users with their OAuth credentials.
user_oauth_association_table = Table('user_oauth_association', Base.metadata,
                                     Column('user_email', String(150), ForeignKey('all_users.email')),
                                     Column('oauth10a_email', String(150), ForeignKey('oauth10a_3legged.email')),
                                     Column('oauth20pkce_email', String(150), ForeignKey('oauth20_pkce.email'))
                                     )


class User(Base, UserMixin):
    """
    Represents a user of the application. This model includes user-related data like email, password, etc.
    Inherits from db.Model (SQLAlchemy ORM model) and UserMixin (adds Flask-Login properties and methods).
    """
    __tablename__ = 'All_Users'  # Explicitly naming the database table for clarity.

    # Defining the columns for the User table:
    email = Column(String(150), unique=True, primary_key=True)  # Email as a unique identifier and primary key.
    id = Column(Integer, unique=True, nullable=True, autoincrement=True)  # Auto-incremented user ID.
    twitter_id = Column(Integer, unique=True, nullable=True)  # Twitter ID for OAuth integration.
    account_name = Column(String(150), unique=True, nullable=False)  # User's account name.
    password = Column(String(150), nullable=False)  # Hashed password.
    date_created = Column(DateTime(timezone=True), default=func.now())  # Account creation timestamp.
    verified = Column(Boolean, default=False)  # Email verification status.

    # Defining relationships to OAuth models and TwitterCookies model:
    oauth10a = relationship('OAuth10a', backref='user', lazy=True)  # One-to-many relationship with OAuth10a.
    oauth20pkce = relationship('OAuth20PKCE', backref='user',
                               lazy=True)  # One-to-many relationship with OAuth20PKCE.
    twitter_cookies = relationship('TwitterCookies', backref='user',
                                   lazy=True)  # One-to-many relationship with TwitterCookies.

    def get_id(self):
        """
        Overrides the get_id method from Flask-Login's UserMixin.
        This method is used by Flask-Login to retrieve the unique identifier for the user.
        Returns the user's email as the identifier.
        """
        return str(self.email)


class OAuth10a(Base):
    """
    Represents OAuth 1.0a credentials associated with a user.
    Stores data necessary for the OAuth 1.0a authentication flow, like tokens and verifier.
    """
    __tablename__ = 'OAuth10a_3Legged'  # Explicit table name for clarity.

    # Defining the columns for the OAuth10a table:
    email = Column(String(150), ForeignKey('All_Users.email'), nullable=False, unique=True, primary_key=True)
    twitter_id = Column(Integer, unique=True, nullable=False)  # Twitter ID linked to OAuth credential.
    account_name = Column(String(150), nullable=False)  # Account name associated with OAuth credential.
    date_created = Column(DateTime(timezone=True), default=func.now())  # Timestamp of credential creation.
    last_token_refresh_date = Column(DateTime(timezone=True), default=func.now())  # Last token refresh timestamp.
    oauth_verifier = Column(String(150), nullable=False)  # OAuth verifier token.
    oauth_token = Column(String(150), nullable=False)  # OAuth token.
    oauth_token_secret = Column(String(150), nullable=False)  # OAuth token secret (stored securely).

    # Relationship to TwitterCookies model:
    twitter_cookies = relationship('TwitterCookies', backref='oauth10a', lazy=True)

    @property
    def oauth_token_secret_hash(self):
        """
        Property to make oauth_token_secret non-readable.
        This is a security measure to prevent accidental exposure of sensitive token secrets.
        Attempting to read this property will raise an AttributeError.
        """
        raise AttributeError('oauth_token_secret is not a readable attribute')

    @oauth_token_secret_hash.setter
    def oauth_token_secret_hash(self, oauth_token_secret):
        """
        Setter for oauth_token_secret.
        Automatically hashes the token secret using Werkzeug's generate_password_hash function.
        :param oauth_token_secret: The plaintext OAuth token secret to be hashed.
        """
        self.oauth_token_secret = generate_password_hash(oauth_token_secret)

    def check_token_secret(self, oauth_token_secret):
        """
        Verifies an OAuth token secret against the hashed version stored in the database.
        :param oauth_token_secret: The plaintext OAuth token secret for verification.
        :return: Boolean indicating whether the secret is correct.
        """
        return check_password_hash(self.oauth_token_secret, oauth_token_secret)


class UserReportingActivity(Base):
    """
    Tracks Twitter activities like muted, blocked, and reported accounts associated with a user account.
    Stores details about the Twitter activities performed by users.
    """
    __tablename__ = 'UserReportingActivity'  # Explicit table name.

    # Defining columns for UserReportingActivity table:
    email = Column(String(150), ForeignKey('All_Users.email'), nullable=False, primary_key=True)
    twitter_id = Column(Integer, nullable=False)  # Twitter ID of the user.
    username = Column(String(50), nullable=False)  # Username of the user.
    muted = Column(Text, nullable=True)  # Muted accounts (comma-separated string).
    muted_nr = Column(Integer, nullable=True)  # Number of muted accounts.
    blocked = Column(Text, nullable=True)  # Blocked accounts.
    blocked_nr = Column(Integer, nullable=True)  # Number of blocked accounts.
    reported_as_spam = Column(Text, nullable=True)  # Accounts reported as spam.
    reported_as_spam_nr = Column(Integer, nullable=True)  # Number of accounts reported as spam.
    reported_impersonation = Column(Text, nullable=True)  # Accounts reported for impersonation.
    reported_impersonation_nr = Column(Integer, nullable=True)  # Number of accounts reported for impersonation.
    last_updated = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())  # Last updated timestamp.

    def __repr__(self):
        """
        Representation method for UserReportingActivity.
        Returns a string representation of the activity with relevant details.
        """
        return (f"<UserReportingActivity {self.email}: "
                f"Muted: {self.muted_nr}, Blocked: {self.blocked_nr}, "
                f"Reported Spam: {self.reported_as_spam_nr}, Reported Impersonation: {self.reported_impersonation_nr}>")


class OAuth20PKCE(Base):
    """
    Represents OAuth 2.0 PKCE credentials associated with a user.
    Stores data necessary for the OAuth 2.0 PKCE authentication flow, like access and refresh tokens.
    """
    __tablename__ = 'OAuth20_PKCE'  # Explicit table name.

    # Defining columns for OAuth20PKCE table:
    email = Column(String(150), ForeignKey('All_Users.email'), nullable=False, unique=True, primary_key=True)
    twitter_id = Column(Integer, unique=True, nullable=True)  # Twitter ID linked to OAuth credential.
    account_name = Column(String(150), nullable=True)  # Account name associated with OAuth credential.
    date_created = Column(DateTime(timezone=True), default=func.now())  # Timestamp of credential creation.
    access_token = Column(String(150), nullable=True)  # OAuth access token.
    refresh_token = Column(String(150), nullable=True)  # OAuth refresh token.
    state = Column(String(255), nullable=True)  # State parameter for additional security.
    code_verifier = Column(String(150), nullable=False)  # Code verifier for PKCE.
    code_challenge = Column(String(150), nullable=True)  # Code challenge for PKCE.
    code_challenge_method = Column(String(150), nullable=True)  # Method used for code challenge in PKCE.
    last_token_refresh_date = Column(DateTime(timezone=True), default=func.now())  # Last token refresh timestamp.
    access_token_expires_in = Column(Integer, nullable=True)  # Expiry time for the access token.

    # Relationship to TwitterCookies model:
    twitter_cookies = relationship('TwitterCookies', backref='oauth20pkce', lazy=True)


class TwitterCookies(Base):
    """
    Represents Twitter cookie data associated with a user or an OAuth credential. Stores Twitter-specific data like
    usernames, IDs, and cookies used for authentication and interaction with Twitter's API.
    """
    __tablename__ = 'twitter_cookies'  # Explicit table name.

    # Defining columns for TwitterCookies table:
    id = Column(Integer, primary_key=True)
    user_email = Column(String(150), ForeignKey('All_Users.email'), nullable=False)  # Associated user email.
    oauth10a_email = Column(String(150), ForeignKey('OAuth10a_3Legged.email'), nullable=True)  # Associated
    # OAuth10a email.
    oauth20pkce_email = Column(String(150), ForeignKey('OAuth20_PKCE.email'), nullable=True)  # Associated
    # OAuth20PKCE email.
    twitter_username = Column(String(255), nullable=False, unique=True)  # Twitter username (unique).
    twid = Column(String(255), nullable=False)  # Twitter ID.
    guest_id = Column(String(255), nullable=False)  # Guest ID for Twitter.
    auth_token = Column(String(255), nullable=False)  # Authentication token.
    ct0 = Column(String(255), nullable=False)  # CSRF security token.
    auth_multi = Column(Text, nullable=False)  # Multiple auth tokens.
    date_created = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))  # Creation
    # timestamp.
    last_updated = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())  # Last updated

    # timestamp.

    def __repr__(self):
        """
        Representation method for TwitterCookies.
        Returns a string representation with the Twitter username.
        """
        return f'<TwitterCookies {self.twitter_username}>'
