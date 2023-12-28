"""
This script contains all secret values which should not be public
"""
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Table, Text, Boolean, func, JSON
from sqlalchemy.orm import relationship, declarative_base, scoped_session, sessionmaker
from werkzeug.security import generate_password_hash, check_password_hash
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone  # Used for handling date and time values, used for logging database entries.
from flask_login import UserMixin
import requests  # Allows the script to send HTTP requests to Twitter's API.
import logging
import sqlite3  # Provides functionality for interacting with SQLite databases.
import base64
import json  # Work with JSON-formatted data for encoding data sent in requests and decoding responses from the API.
import sys  # Is used to Exit the script when a KeyboardInterrupt was caught.
import re
import os  # Interacts with the operating system, for example, to generate random bytes or handle file paths.

# Declare and initialize global_cookies at the module level
global_cookies = {  # Initialize with default values or leave it empty
    "auth_multi": "",
    "auth_token": "",
    "guest_id": "",
    "twid": "",
    "ct0": ""
}

# Define log level constants
DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL

# Static values to use as environment information throughout this project
FLASKAPP = 'app.py'
FLASK_ENV = 'development'
FLASK_DEBUG = 'True'
SECRET_KEY = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
DB_NAME = 'database.sqlite'
OAUTH_STORE = '{}'
HOST = '0.0.0.0'
PORT = "443"
SQLALCHEMY_DATABASE_URI = 'sqlite:///database.sqlite'  # Or SQLALCHEMY_BINDS
SQLALCHEMY_TRACK_MODIFICATIONS = True
SQLALCHEMY_ECHO = True
JSONIFY_PRETTYPRINT_REGULAR = True
AUTHORIZE_URL = 'https://api.twitter.com/oauth/authorize'
ACCESS_TOKEN_URL = 'https://api.twitter.com/oauth/access_token'
REQUEST_TOKEN_URL = 'https://api.twitter.com/oauth/request_token'
SHOW_USER_URL = 'https://api.twitter.com/1.1/users/show.json'
AUTHORIZE_URL_V2 = "https://twitter.com/i/oauth2/authorize"
ACCESS_TOKEN_URL_V2 = 'https://api.twitter.com/oauth/access_token'
LOG_FILENAME = "TwitterData/SQL-ImpersonatorAccounts/ImpersonatorAccounts.log"
DATABASE_PATH = "TwitterData/SQL-ImpersonatorAccounts/ImpersonatorAccounts.sqlite"
UPDATE_DATABASE_BASE_URL = "https://api.twitter.com/2/users/by"
REDIRECT_URI = 'https://benemortasia.com/oauth20pkcecallback'
REDIRECT_URI_V2 = 'https://example.com/oauth20pkcecallback'
CHAT_GPT_API = 'xx-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
# This scope string includes the following permissions:
SCOPE = "tweet.read users.read mute.read mute.write block.read block.write offline.access"
SCOPE_V2 = "tweet.read users.read mute.read mute.write block.read block.write offline.access"
# tweet.read: Read Tweets from your timeline.
# users.read: Read user profiles.
# mute.read: Read accounts you’ve muted.
# mute.write: Mute or unmute accounts.
# block.read: Read accounts you’ve blocked.
# block.write: Block or unblock accounts.
# offline.access: Maintain access to the account's resources even when your application is not actively being used.
########################################################################################################################
# CONSUMER KEYS (User Authentication)                                                                                  #
# Think of these as the username and password that represents your App when making API requests.                       #
# While your Secret will remain permanently hidden, you can always view the last 6 characters of your API Key.         #
API_AKA_CONSUMER_KEY = 'xxxxxxxxxxxxxxxxxxxxxxxxx'
API_AKA_CONSUMER_KEY_SECRET = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
API_AKA_CONSUMER_KEY_V2 = 'xxxxxxxxxxxxxxxxxxxxxxxxx'
API_AKA_CONSUMER_KEY_SECRET_V2 = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
########################################################################################################################
# Authentication Tokens(User Authentication).                                                                          #
# Bearer Token authenticates requests on behalf of your developer App
BEARER_TOKEN = ('XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
                'XXXXXXXXXXX')
BEARER_TOKEN_V2 = ('XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
                   'XXXXXXXXXXXXX')
BEARER_TOKEN_TWITTER = ('XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
                        'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX')
# An Access Token and Secret are user-specific credentials used to authenticate OAuth 1.0a API requests.
# They specify the Twitter account the request is made on behalf of.                                                   #
ACCESS_TOKEN = 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
ACCESS_TOKEN_SECRET = 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
ACCESS_TOKEN_V2 = 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
ACCESS_TOKEN_SECRET_V2 = 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
ACCESS_TOKEN_B = 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
ACCESS_TOKEN_SECRET_B = 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
########################################################################################################################
OAUTH2PCKE_REDIRECT_URI = 'https://benemortasia.com/oauth20pkcecallback'
# OAuth 2.0 Client ID and Client Secret (Application Authentication).                                                  #
CLIENT_ID_AKA_CONSUMER_KEY = 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
CLIENT_ID_AKA_CONSUMER_KEY_SECRET = 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
CLIENT_ID_AKA_CONSUMER_KEY_V2 = 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
CLIENT_ID_AKA_CONSUMER_KEY_SECRET_V2 = 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
########################################################################################################################

# SQLAlchemy Setup
engine = create_engine(SQLALCHEMY_DATABASE_URI, echo=True)
Base = declarative_base()

# SQLAlchemy Setup for impersonator database
impersonator_engine = create_engine('sqlite:///ImpersonatorAccounts.sqlite', echo=True)
ImpersonatorBase = declarative_base()
ImpersonatorBase.metadata.bind = impersonator_engine

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


# Custom JSON encoder to handle non-serializable objects
class SafeEncoder(json.JSONEncoder):
    """
        SafeEncoder
    """

    def default(self, obj):
        """

        :param obj:
        :return:
        """
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)


# Class for the SQL-Alchemy database schema for ImpersonatorAccounts
class TwitterAccount(ImpersonatorBase):
    """
        TwitterAccount database schema
    """
    __tablename__ = "impersonator_account"
    protected_channel = Column(String, index=True)
    protected_channel_id = Column(String, index=True)
    id = Column(Integer, primary_key=True, index=True)
    twitter_id = Column(String, unique=True)
    username = Column(String, nullable=False, unique=True)
    name = Column(String)
    followers_count = Column(Integer)
    following_count = Column(Integer)
    tweet_count = Column(Integer)
    username_changed = Column(Integer, default=0)
    previous_username = Column(String)
    username_changed_date = Column(DateTime)
    suspended = Column(Boolean, default=False)
    suspended_date = Column(DateTime)
    unresolvable = Column(Boolean, default=False)
    created_at = Column(DateTime)
    description = Column(String)
    listed_count = Column(Integer)
    url = Column(String)
    profile_image_url = Column(String)
    api_response = Column(JSON)
    api_response_updated_at = Column(DateTime)
    previous_api_response = Column(JSON)
    previous_api_response_updated_at = Column(DateTime)

    def __init__(self, **kwargs):
        """

        :param kwargs:
        """
        self.protected_channel = kwargs.get("protected_channel")
        self.protected_channel_id = kwargs.get("protected_channel_id")
        self.twitter_id = kwargs.get("twitter_id")  # Use "twitter_id" instead of "id"
        self.username = kwargs.get("username")
        self.name = kwargs.get("name")
        self.followers_count = kwargs.get("public_metrics", {}).get("followers_count")
        self.following_count = kwargs.get("public_metrics", {}).get("following_count")
        self.tweet_count = kwargs.get("public_metrics", {}).get("tweet_count")
        self.username_changed = False
        self.username_changed_to = None
        self.username_changed_date = None
        self.suspended = False
        self.suspended_date = None
        self.unresolvable = False
        self.created_at = datetime.strptime(
            kwargs.get("created_at"), '%Y-%m-%dT%H:%M:%S.%fZ') if kwargs.get("created_at") else None
        self.description = kwargs.get("description")
        self.listed_count = kwargs.get("public_metrics", {}).get("listed_count")
        self.url = kwargs.get("url")
        self.profile_image_url = kwargs.get("profile_image_url")
        self.api_response = kwargs.get("api_response")
        self.api_response_updated_at = datetime.now()  # Set the current time

    def mark_as_suspended(self, date=None):
        """

        :param date:
        :return:
        """
        if not self.suspended:
            logging.info(f"Marking {self.username} as suspended.")
            self.suspended = True
            self.suspended_date = date or datetime.now()
            logging.info(f"Marked {self.username} as suspended at {self.suspended_date}.")
        else:
            logging.info(f"{self.username} is already marked as suspended.")

    def update_username(self, new_username, session):
        """

        :param new_username:
        :param session:
        :return:
        """
        if self.username != new_username:
            # Concatenate previous_username with the current username if not empty
            self.previous_username = (self.previous_username + ',' if self.previous_username else '') + self.username
            self.username = new_username
            self.username_changed = True
            self.username_changed_date = datetime.now()
        session.commit()  # Commit the session after updating

    def update_api_response(self, new_response):
        """

        :param new_response:
        :return:
        """
        self.previous_api_response = self.api_response
        self.previous_api_response_updated_at = self.api_response_updated_at
        # Ensure that new_response is converted to JSON only if it's not already a JSON string
        if not isinstance(new_response, str):
            self.api_response = json.dumps(new_response, cls=SafeEncoder)
        else:
            self.api_response = new_response
        self.api_response_updated_at = datetime.now()

    def __repr__(self):
        return f"<TwitterAccount(username={self.username}, twitter_id={self.twitter_id}, suspended={self.suspended})>"


def find_root():
    """
    Traverses up the directory tree to find the project root.

    The project root is identified as the directory that contains the 'instance' folder.

    Returns:
        str: The absolute path to the project root directory.

    Raises:
        FileNotFoundError: If no suitable project root is found.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    while current_dir:
        if os.path.isdir(os.path.join(current_dir, 'instance')):
            return current_dir  # Project root found
        parent_dir = os.path.dirname(current_dir)
        if current_dir == parent_dir:
            break  # Reached the filesystem root
        current_dir = parent_dir
    raise FileNotFoundError("Project root directory containing 'instance' folder not found.")


def get_databases():
    """
    Returns the paths to the main and impersonator SQLite database files with new names.
    """
    project_root = find_root()
    accounts_db_path = os.path.join(project_root, 'instance', 'database.sqlite')
    if not os.path.exists(accounts_db_path):
        raise FileNotFoundError("Main database file not found at: " + accounts_db_path)
    impersonators_db_path = os.path.join(project_root, 'instance', 'ImpersonatorAccounts.sqlite')
    if not os.path.exists(impersonators_db_path):
        raise FileNotFoundError("Impersonator database file not found at: " + impersonators_db_path)
    return accounts_db_path, impersonators_db_path


def update_database_structure():
    """
    Updates the database structure for the main database but excludes the impersonator_account table.
    """
    # This will update all tables bound to 'engine' but will not touch the impersonator_engine
    Base.metadata.create_all(engine)
    print("Main database structure updated successfully.")

    # Update the structure for the impersonator database
    ImpersonatorBase.metadata.create_all(impersonator_engine)
    print("Impersonator database structure updated successfully.")


def get_log_file_name(default_name="app.log"):
    """
    Returns the filename for the log file based on the name of the Python script.
    """
    script_name = os.path.basename(sys.argv[0])
    log_file_name, _ = os.path.splitext(script_name)
    return log_file_name + '.log' if log_file_name and log_file_name != '__main__' else default_name


def set_logging(log_level=logging.WARNING):
    """
    Initializes logging with a file and stream handler, using the specified log level.
    """

    class AsciiFilter(logging.Filter):
        """
        ASCII filter
        """

        def filter(self, record):
            """

            :param record:
            :return:
            """
            if record.msg:
                record.msg = record.msg.encode('ascii', errors='replace').decode()
            return True

    logger = logging.getLogger()
    logger.setLevel(log_level)
    logger.addFilter(AsciiFilter())

    # Determine log directory and file name
    project_root = find_root()
    log_directory = os.path.join(project_root, 'logs')
    os.makedirs(log_directory, exist_ok=True)
    log_file_path = os.path.join(log_directory, get_log_file_name("Correct_Database.log"))

    # File handler for detailed logs
    file_handler = RotatingFileHandler(log_file_path, maxBytes=int(49.9 * 1024 * 1024), backupCount=1, encoding='utf-8')
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Console handler for brief messages
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter('%(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # Disable SQLAlchemy's own logger to console
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)


def log_debug(message):
    """
    Logs a debug message.
    """
    logging.debug(message.encode('utf-8', 'replace').decode('utf-8'))


def log_info(message):
    """
    Logs an info message.
    """
    logging.info(message.encode('utf-8', 'replace').decode('utf-8'))


def log_warning(message):
    """
    Logs a warning message.
    """
    logging.warning(message.encode('utf-8', 'replace').decode('utf-8'))


def log_error(message):
    """
    Logs an error message.
    """
    logging.error(message.encode('utf-8', 'replace').decode('utf-8'))


def log_critical(message):
    """
    Logs a critical message.
    """
    logging.critical(message.encode('utf-8', 'replace').decode('utf-8'))


def generate_custom_transaction_id():
    """

    :return:
    """
    # Generate 70 random bytes. The number 70 is chosen because 70 * 4/3 = 93.33, which is just under 94.
    # This ensures that the Base64 encoded string of these bytes will be close to 94 characters without padding.
    random_bytes = os.urandom(70)
    # Encode the random bytes into a Base64 string. The encoding process converts binary data into
    # a string format, using a Base64 algorithm. This string is then decoded from bytes to a UTF-8 string.
    encoded_id = base64.b64encode(random_bytes).decode()
    # Truncate the encoded string to 94 characters to meet the required length.
    # This truncation is necessary because the encoded string might slightly exceed 94 characters.
    return encoded_id[:94]


def get_filtered_protected_channels(accounts_db):
    """
    Fetches unique protected channels from the database.

    :param accounts_db:
    :return:
    """
    try:
        conn = sqlite3.connect(accounts_db)
        cursor = conn.cursor()

        # SQL query to select distinct protected channels and their IDs
        query = ("""
                 SELECT DISTINCT protected_channel, protected_channel_id 
                 FROM impersonator_account 
                 WHERE protected_channel IS NOT NULL 
                 AND protected_channel_id != 0
                 """)
        cursor.execute(query)
        results = cursor.fetchall()
        conn.close()

        # Exclusions for certain channels
        exclusions = ['Uncategorized', 'Spam']
        protected_channels = [(channel, channel_id) for channel, channel_id in results if channel not in exclusions]

        return protected_channels

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return []


def get_active_impersonator_accounts(impersonator_db_path, protected_channel):
    """

    :param impersonator_db_path:
    :param protected_channel:
    :return:
    """
    try:
        conn = sqlite3.connect(impersonator_db_path)
        cursor = conn.cursor()
        # SQL query to select usernames and Twitter IDs from active impersonator accounts.
        query = """
        SELECT username, twitter_id FROM impersonator_account
        WHERE protected_channel = ? AND suspended = 0 AND unresolvable = 0
        AND username IS NOT NULL AND twitter_id IS NOT NULL
        """
        cursor.execute(query, (protected_channel,))

        accounts = cursor.fetchall()
        conn.close()

        # return accounts

        # Formatting Twitter IDs as strings and returning the list of active impersonators.
        return [(username, str(twitter_id)) for username, twitter_id in accounts]

    except sqlite3.Error as e:
        print(f"Database error: {e}")  # Print the database error and return an empty list.
        return []

    except Exception as e:
        print(f"An error occurred: {e}")  # Print the database error and return an empty list.
        return []


def get_cookies_for_account(accounts_db, account_id):
    """

    :param accounts_db:
    :param account_id:
    :return:
    """
    try:
        conn = sqlite3.connect(accounts_db)
        cursor = conn.cursor()

        # SQL query to fetch cookies for the specified account
        cursor.execute(
            "SELECT auth_multi, auth_token, guest_id, twid, ct0 FROM twitter_cookies WHERE rowid = ?",
            (account_id,)
        )
        result = cursor.fetchone()

        if result:
            # Keys corresponding to the cookie names
            keys = ["auth_multi", "auth_token", "guest_id", "twid", "ct0"]
            return dict(zip(keys, result))
        else:
            print("Account not found.")
            return None

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None
    finally:
        conn.close()


# Function to list accounts
def list_accounts():
    """

    :return:
    """
    accounts_db_path = get_databases()[0]  # Get the accounts_db_path from the tuple

    with sqlite3.connect(accounts_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT twitter_username FROM twitter_cookies")
        return [row[0] for row in cursor.fetchall()]


def list_twitter_accounts_with_emails():
    """
    Retrieves and lists all accounts from the All_Users table along with their associated OAuth details, if any.
    Accounts without OAuth details will be displayed with placeholders for username and Twitter ID.
    :return: A list of account details including email, Twitter username, and Twitter ID.
    """
    try:
        accounts_db_path, _ = get_databases()
        conn = sqlite3.connect(accounts_db_path)
        cursor = conn.cursor()

        # Updated query to include additional criteria for account selection
        query = """
            SELECT 
                au.email,
                COALESCE(o10a.account_name, o20.account_name, 'No username') AS twitter_username,
                COALESCE(o10a.twitter_id, o20.twitter_id, 'No Twitter ID') AS twitter_id
            FROM All_Users au
            LEFT JOIN OAuth10a_3Legged o10a ON au.email = o10a.email
            LEFT JOIN OAuth20_PKCE o20 ON au.email = o20.email
            WHERE o10a.twitter_id IS NOT NULL OR o20.twitter_id IS NOT NULL OR au.email IS NOT NULL
            GROUP BY au.email
            ORDER BY au.email
        """
        cursor.execute(query)
        accounts = cursor.fetchall()

        if not accounts:
            print("No accounts found.")
            return []

        return accounts

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return []
    finally:
        conn.close()


def list_user_emails():
    """
    Lists all user emails stored in the database.

    Returns:
        list: A list of email strings.

    Raises:
        sqlite3.Error: If there's an error in database operations.

    :return:
    """
    try:
        accounts_db_path, _ = get_databases()  # Get the accounts_db_path from the tuple
        conn = sqlite3.connect(accounts_db_path)  # Establishing a connection to the SQLite database
        cursor = conn.cursor()  # Creating a cursor object to execute SQL commands

        query = "SELECT email FROM All_Users"  # SQL query to select all emails from the All_Users table
        cursor.execute(query)  # Executing the SQL query

        results = cursor.fetchall()  # Fetching all results from the query execution
        conn.close()  # Closing the database connection

        emails = [email[0] for email in results]  # Extracting email from each tuple in the results
        return emails  # Returning the list of emails

    except sqlite3.Error as e:  # Catching any SQLite database operation errors
        raise sqlite3.Error(f"Database error: {e}")  # Raising the error for external handling


def get_registered_user_id(user_email):
    """

    :param user_email:
    :return:
    """
    try:
        accounts_db_path, _ = get_databases()  # Get the accounts_db_path from the tuple
        conn = sqlite3.connect(accounts_db_path)  # Establishing a connection to the SQLite database
        cursor = conn.cursor()  # Creating a cursor object to execute SQL commands

        # First, try to get the Twitter ID from the OAuth10a_3Legged table
        query = "SELECT twitter_id FROM OAuth10a_3Legged WHERE email = ?"  # SQL query to select Twitter ID
        cursor.execute(query, (user_email,))  # Executing the SQL query with user_email as a parameter
        result = cursor.fetchone()  # Fetching the result (first row)

        if not result:
            # If not found, try to get the Twitter ID from the OAuth20_PKCE table
            query = "SELECT twitter_id FROM OAuth20_PKCE WHERE email = ?"  # SQL query for alternative table
            cursor.execute(query, (user_email,))  # Executing the SQL query with user_email as a parameter
            result = cursor.fetchone()  # Fetching the result from the alternative table

        conn.close()  # Closing the database connection

        if result and result[0] is not None:
            return int(result[0])  # Convert the Twitter ID to an integer and return it
        else:
            print(f"No Twitter ID found for email: {user_email}")
            return None

    except sqlite3.Error as e:  # Catching any SQLite database operation errors
        raise sqlite3.Error(f"Database error: {e}")  # Raising the error for external handling


def initialize_cookies_in_database(selected_account=None):
    """

    :param selected_account:
    :return:
    """
    accounts_db_path, _ = get_databases()  # Get the accounts_db_path from the tuple
    with sqlite3.connect(accounts_db_path) as conn:
        cursor = conn.cursor()

        if selected_account:
            # Prompt for cookie data for the selected account
            print(f"Paste the cookies information (full text as copied) for {selected_account}:")
            raw_cookies = ""
            while True:
                line = input()
                if line.strip() == "":  # Empty line signals end of cookie data input
                    break
                raw_cookies += line + "\n"

            # Parse and insert/update cookie data for the selected account
            cookie_data = parse_cookies(raw_cookies)
            cookie_data = additional_processing(cookie_data)  # Add this line
            cursor.execute("""
                INSERT INTO twitter_cookies (twitter_username, auth_multi, auth_token, guest_id, twid, ct0)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(twitter_username) DO UPDATE SET
                auth_multi=excluded.auth_multi,
                auth_token=excluded.auth_token,
                guest_id=excluded.guest_id,
                twid=excluded.twid,
                ct0=excluded.ct0
            """, (
                selected_account, cookie_data.get('auth_multi'), cookie_data.get('auth_token'),
                cookie_data.get('guest_id'), cookie_data.get('twid'), cookie_data.get('ct0')))
            print(f"Cookie data added/updated for {selected_account}.")
        else:
            # Display a list of existing accounts
            existing_usernames = list_twitter_accounts_with_emails()

            print(f"Existing Twitter accounts with cookies:")
            for index, (email, account_name, twitter_id) in enumerate(existing_usernames, start=1):
                account_name_fixed_width = account_name.ljust(18)
                index_fixed_width = f"{index}. ".ljust(4)
                twitter_id_fixed_width = f"{twitter_id}".rjust(20)
                print(f"{index_fixed_width}{account_name_fixed_width}"
                      f" (Twitter ID:{twitter_id_fixed_width}, Email: {email})")
            print(f"{len(existing_usernames) + 1}. Add New Account")
            print(f"{len(existing_usernames) + 2}. Quit")

            user_choice = input("Enter your choice (number): ").strip()

            if user_choice == str(len(existing_usernames) + 1):
                # Prompt for new Twitter account username
                account_name = input("Enter new Twitter account username: ").strip()

                # Prompt for cookie data
                print(f"Paste the cookies information (full text as copied) for {account_name}:")
                raw_cookies = ""
                while True:
                    line = input()
                    if line.strip() == "":  # Empty line signals end of cookie data input
                        break
                    raw_cookies += line + "\n"

                # Parse and insert/update cookie data for the new account
                cookie_data = parse_cookies(raw_cookies)
                cookie_data = additional_processing(cookie_data)  # Add this line
                cursor.execute("""
                    INSERT INTO twitter_cookies (twitter_username, auth_multi, auth_token, guest_id, twid, ct0)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(twitter_username) DO UPDATE SET
                    auth_multi=excluded.auth_multi,
                    auth_token=excluded.auth_token,
                    guest_id=excluded.guest_id,
                    twid=excluded.twid,
                    ct0=excluded.ct0
                """, (
                    account_name, cookie_data.get('auth_multi'), cookie_data.get('auth_token'),
                    cookie_data.get('guest_id'), cookie_data.get('twid'), cookie_data.get('ct0')))
                print(f"Cookie data added/updated for {account_name}.")
            elif user_choice == str(len(existing_usernames) + 2):
                print("Exiting the update menu.")
            elif user_choice.isdigit() and 1 <= int(user_choice) <= len(existing_usernames):
                selected_account = existing_usernames[int(user_choice) - 1][1]
                # Prompt for cookie data for the selected account
                print(f"Paste the cookies information (full text as copied) for {selected_account}:")
                raw_cookies = ""
                while True:
                    line = input()
                    if line.strip() == "":  # Empty line signals end of cookie data input
                        break
                    raw_cookies += line + "\n"

                # Parse and insert/update cookie data for the selected account
                cookie_data = parse_cookies(raw_cookies)
                cookie_data = additional_processing(cookie_data)  # Add this line
                cursor.execute("""
                    INSERT INTO twitter_cookies (twitter_username, auth_multi, auth_token, guest_id, twid, ct0)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(twitter_username) DO UPDATE SET
                    auth_multi=excluded.auth_multi,
                    auth_token=excluded.auth_token,
                    guest_id=excluded.guest_id,
                    twid=excluded.twid,
                    ct0=excluded.ct0
                """, (
                    selected_account, cookie_data.get('auth_multi'), cookie_data.get('auth_token'),
                    cookie_data.get('guest_id'), cookie_data.get('twid'), cookie_data.get('ct0')))
                print(f"Cookie data added/updated for {selected_account}.")
            else:
                print("Invalid choice.")


def normalize_cookie_data(raw_cookies):
    """

    :param raw_cookies:
    :return:
    """
    # Normalize line breaks and spaces
    normalized = re.sub(r'\s+', ' ', raw_cookies).strip()
    # Replace multiple spaces with a single space for consistency
    normalized = re.sub(r' {2,}', ' ', normalized)

    return normalized


def extract_cookie_value(normalized_cookies, cookie_name):
    """

    :param normalized_cookies:
    :param cookie_name:
    :return:
    """
    # Regular expression pattern to extract specific cookie value
    pattern = rf"{cookie_name}\s+([^\s]+)"
    match = re.search(pattern, normalized_cookies)

    if match:
        return match.group(1)
    else:
        return None


def parse_json_cookies(raw_cookies):
    """
    Parse cookies from a JSON formatted string.

    :param raw_cookies: String containing JSON formatted cookies.
    :return: Dictionary of cookie values.
    """
    try:
        json_data = json.loads(raw_cookies)
        # Assuming the cookies are always under the "Request Cookies" key
        cookie_dict = json_data.get("Request Cookies", {})

        # Transform 'twid' and 'guest_id' if necessary
        twid = cookie_dict.get('twid')
        if twid and twid.startswith('u='):
            cookie_dict['twid'] = twid.replace('u=', 'u%3D')

        guest_id = cookie_dict.get('guest_id')
        if guest_id and guest_id.startswith('v1:'):
            cookie_dict['guest_id'] = guest_id.replace('v1:', 'v1%3A')

        return {key: value for key, value in cookie_dict.items() if
                key in ['ct0', 'twid', 'guest_id', 'auth_token', 'auth_multi']}
    except json.JSONDecodeError:
        print("Error: Invalid JSON format.")
        return {}


def parse_cookies(raw_cookies):
    """
    Parse cookies from a string, checking for JSON format first.

    :param raw_cookies: String containing cookies.
    :return: Dictionary of cookie values.
    """
    # Check if raw_cookies starts with '{' indicating JSON format
    if raw_cookies.strip().startswith('{'):
        return parse_json_cookies(raw_cookies)

    # If not JSON, proceed with existing parsing method
    cookie_values = {}
    normalized_cookies = normalize_cookie_data(raw_cookies)
    cookie_names = ['ct0', 'twid', 'guest_id', 'auth_token', 'auth_multi']

    for name in cookie_names:
        value = extract_cookie_value(normalized_cookies, name)
        if value:
            cookie_values[name] = value

    return cookie_values


def additional_processing(cookie_data):
    """

    :param cookie_data:
    :return:
    """
    # Check for the specific starting patterns in 'twid' and 'guest_id'
    if cookie_data.get('twid', '').startswith('"u=') and cookie_data.get('guest_id', '').startswith('"v1:'):
        print("Reformatting required for Firefox cookie format.")
        for key in cookie_data:
            cookie_data[key] = reformat_cookie(key, cookie_data[key])

    print("Processing the following cookie data:")
    for key, value in cookie_data.items():
        print(f"{key}: {value}")

    return cookie_data


def reformat_cookie(key, cookie_value):
    """

    :param key:
    :param cookie_value:
    :return:
    """
    # Remove leading and trailing double quotes for all values
    value = cookie_value.strip('"')

    # Apply specific transformations based on the key
    if key == 'twid' and value.startswith('u='):
        value = 'u%3D' + value[2:]
    elif key == 'guest_id' and value.startswith('v1:'):
        value = 'v1%3A' + value[3:]
    elif key == 'auth_multi':
        # Remove single quotes from 'auth_multi' while keeping double quotes
        value = value.replace("'", "")

    return value


# Function to update cookies
def update_cookies(selected_account, new_cookies, accounts_db):
    """

    :param selected_account:
    :param new_cookies:
    :param accounts_db:
    :return:
    """
    global global_cookies
    with sqlite3.connect(accounts_db) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE twitter_cookies
            SET auth_multi = ?, auth_token = ?, guest_id = ?, twid = ?, ct0 = ?
            WHERE twitter_username = ?
        """, (new_cookies.get('auth_multi'), new_cookies.get('auth_token'),
              new_cookies.get('guest_id'), new_cookies.get('twid'),
              new_cookies.get('ct0'), selected_account))
        conn.commit()
    global_cookies.update(new_cookies)


def create_new_cookies_account():
    """

    :return:
    """
    accounts_db_path, _ = get_databases()  # Get the accounts_db_path from the tuple
    with sqlite3.connect(accounts_db_path) as conn:
        cursor = conn.cursor()

        # Prompt for new Twitter account username
        account_name = input("Enter new Twitter account username: ").strip()

        # Prompt for cookie data
        print(f"Paste the cookies information (full text as copied) for {account_name}:")
        raw_cookies = ""
        while True:
            line = input()
            if line.strip() == "":  # Empty line signals end of cookie data input
                break
            raw_cookies += line + "\n"

        # Parse and insert/update cookie data
        cookie_data = parse_cookies(raw_cookies)
        cookie_data = additional_processing(cookie_data)  # Add this line
        cursor.execute("""
            INSERT INTO twitter_cookies (twitter_username, auth_multi, auth_token, guest_id, twid, ct0)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(twitter_username) DO UPDATE SET
            auth_multi=excluded.auth_multi,
            auth_token=excluded.auth_token,
            guest_id=excluded.guest_id,
            twid=excluded.twid,
            ct0=excluded.ct0
        """, (
            account_name, cookie_data.get('auth_multi'), cookie_data.get('auth_token'),
            cookie_data.get('guest_id'), cookie_data.get('twid'), cookie_data.get('ct0')))
        conn.commit()
        print(f"Cookie data added/updated for {account_name}.")


def update_cookies_menu():
    """

    :return:
    """
    account_email_pairs = list_twitter_accounts_with_emails()

    print(f"\n========================================================================================================="
          f"=====\n                                     ALL CURRENT ACCOUNTS WITH COOKIES\n============================"
          f"==================================================================================")
    for index, (rowid, username, modified_twid, email) in enumerate(account_email_pairs, start=1):
        email_display = email if email else "None"
        formatted_index = f"{index:4}."
        formatted_username = f"@{username:<18}"  # Limit to 18 characters and left align
        formatted_details = f"(Twitter ID: {modified_twid}, Email: {email_display})"
        print(f"{formatted_index} {formatted_username} {formatted_details}")

    print(f"{len(account_email_pairs) + 1:4}. Add New Account")
    print(f"{len(account_email_pairs) + 2:4}. Quit")
    print("Select an option by entering the number:")

    try:
        user_choice = input().strip()  # Remove the int conversion here
        if user_choice == str(len(account_email_pairs) + 1):
            create_new_cookies_account()
        elif user_choice == str(len(account_email_pairs) + 2):
            print("Exiting the update menu.")
        elif user_choice.isdigit() and 1 <= int(user_choice) <= len(account_email_pairs):
            selected_account = account_email_pairs[int(user_choice) - 1][1]
            initialize_cookies_in_database(selected_account)
        else:
            print("Invalid choice.")
    except ValueError:
        print("Please enter a valid number.")


def prompt_for_cookie_update(selected_account, accounts_db):
    """

    :param selected_account:
    :param accounts_db:
    :return:
    """
    print(f"Paste the cookies information (full text as copied) for {selected_account}:")
    raw_cookies = ""
    while True:
        line = input()
        if line.strip() == "":
            break
        raw_cookies += line + "\n"

    cookie_data = parse_cookies(raw_cookies)
    cookie_data = additional_processing(cookie_data)  # Add this line
    update_cookies(selected_account, cookie_data, accounts_db)
    # Call update_cookies without accounts_db
    print(f"Cookie data updated for {selected_account}.")


def log_issue(issue_description, account):
    """

    :param issue_description:
    :param account:
    :return:
    """
    # Ensure logger is defined globally
    logger = logging.getLogger()
    detail = f"{issue_description} in account: {account.username} (ID: {account.twitter_id})"
    logger.warning(detail)
    print(detail)


def is_valid_json(json_string):
    """

    :param json_string:
    :return:
    """
    try:
        if isinstance(json_string, str):
            json.loads(json_string)
        return True
    except json.JSONDecodeError:
        return False


def check_for_duplicates(session):
    """

    :param session:
    :return:
    """
    # Ensure logger is defined globally
    logger = logging.getLogger()
    """

    :param session:
    :return:
    """
    # Adjusted query to check for duplicates in a case-insensitive manner
    duplicate_usernames = session.query(func.lower(TwitterAccount.username)).group_by(
        func.lower(TwitterAccount.username)).having(
        func.count(TwitterAccount.username) > 1).all()
    duplicate_twitter_ids = session.query(TwitterAccount.twitter_id).group_by(TwitterAccount.twitter_id).having(
        func.count(TwitterAccount.twitter_id) > 1).all()

    if duplicate_usernames or duplicate_twitter_ids:
        logger.warning("Duplicate entries found!")
        if duplicate_usernames:
            logger.warning(f"Duplicate Usernames: {[u[0] for u in duplicate_usernames]}")
        if duplicate_twitter_ids:
            logger.warning(f"Duplicate Twitter IDs: {[tid[0] for tid in duplicate_twitter_ids]}")
    else:
        logger.info("No duplicate entries found.")


def check_data_integrity(session):
    """
    Check the integrity of data in the database.

    :param session: Database session
    :return: None
    """
    missing_twitter_id_header_printed = False
    missing_twitter_id_active_header_printed = False
    accounts_with_missing_twitter_id = []
    active_accounts_with_missing_twitter_id = []

    accounts = session.query(TwitterAccount).all()
    for account in accounts:
        # Check for negative or None values in numeric fields only if Twitter ID is missing and account is active
        if not account.twitter_id and account.suspended == 0 and account.unresolvable == 0:
            numeric_fields = [account.followers_count, account.following_count, account.tweet_count,
                              account.listed_count]
            if any(x is None or (isinstance(x, int) and x < 0) for x in numeric_fields):
                log_issue("Invalid values in numeric fields in active account with no Twitter ID", account)

        # Check for valid datetime objects or None in date fields
        date_fields = [account.created_at, account.suspended_date, account.username_changed_date,
                       account.api_response_updated_at, account.previous_api_response_updated_at]
        if any(dt is not None and not isinstance(dt, datetime) for dt in date_fields):
            log_issue("Invalid date value", account)

        # Check API response formats
        if account.api_response and not is_valid_json(account.api_response):
            log_issue("Invalid API response format", account)
        if account.previous_api_response and not is_valid_json(account.previous_api_response):
            log_issue("Invalid previous API response format", account)

        # Check username change logic
        if account.username_changed:
            if not account.previous_username or account.username in account.previous_username:
                log_issue("Username change inconsistency", account)
            if not account.username_changed_date:
                log_issue("Missing username change date", account)

        # Check unresolvable accounts
        if account.unresolvable and not (account.api_response or account.previous_api_response):
            log_issue("Unresolvable account missing API response", account)

            # Check for missing Twitter ID
            if not account.twitter_id:
                account_info = (f"Twitter account {account.username.ljust(16)} is Missing a"
                                f" TwitterID: twitter_id={account.twitter_id}, suspended={account.suspended},"
                                f" unresolvable={account.unresolvable}")

                if account.suspended or account.unresolvable:
                    if not missing_twitter_id_header_printed:
                        print(f"\n====================================================================================="
                              "=============\nCHECKING FOR ACCOUNTS WITH A MISSING TWITTER_ID (SUSPENDED OR UNRESOLVABL"
                              "E)\n===================================================================================="
                              "==============")
                        missing_twitter_id_header_printed = True
                    accounts_with_missing_twitter_id.append(account_info)
                else:
                    if not missing_twitter_id_active_header_printed:
                        print(f"\n====================================================================================="
                              f"=============\nCHECKING FOR ACTIVE ACCOUNTS WITH A MISSING TWITTER_ID\n================"
                              f"==================================================================================")
                        missing_twitter_id_active_header_printed = True
                    active_accounts_with_missing_twitter_id.append(account_info)

        # Print the collected information
        for info in accounts_with_missing_twitter_id:
            print(info)

        # Additional checks based on other fields can be added here


def prompt_for_correction():
    """

    :return:
    """
    response = input("Duplicate Usernames found. Do you want to correct/fix the database? (Y/N) ").strip().lower()
    return response == 'y'


def verify_duplicates(session, duplicates):
    """

    :param session:
    :param duplicates:
    :return:
    """
    # Ensure logger is defined globally
    logger = logging.getLogger()
    for dup in duplicates:
        accounts = session.query(TwitterAccount).filter(func.lower(TwitterAccount.username) == dup[0]).all()

        if len(accounts) != 2:
            logger.warning(f"More than two accounts found for username {dup[0]}, manual review recommended.")
            continue

        suspended_accounts = [acc for acc in accounts if acc.suspended]
        active_accounts = [acc for acc in accounts if not acc.suspended]

        if len(suspended_accounts) != 1 or len(active_accounts) != 1:
            logger.warning(
                f"Expected one active and one suspended account for username {dup[0]}, "
                f"found {len(active_accounts)} active and {len(suspended_accounts)} suspended.")
            continue

        yield active_accounts[0], suspended_accounts[0]


def display_account_details(account):
    """

    :param account:
    :return:
    """
    details = f"ID: {account.id}, Twitter ID: {account.twitter_id}, Username: {account.username}, " \
              f"Suspended: {account.suspended}, Suspended Date: {account.suspended_date}, " \
              f"Unresolvable: {account.unresolvable}"
    return details


def handle_duplicate_accounts(session, active_account, duplicate_account):
    """

    :param session:
    :param active_account:
    :param duplicate_account:
    :return:
    """
    # Determine the status for the duplicate entry
    if duplicate_account.suspended:
        status = 'suspended'
    elif duplicate_account.unresolvable:
        status = 'unresolvable'
    else:
        status = 'active'

    # Print the details
    print(f"\nDuplicate username: {active_account.username}")
    print(f"Original entry: {display_account_details(active_account)}")
    print(f"Duplicate entry: {status}")

    response = input("Do you want to merge this duplicate? (Y/N) ").strip().lower()
    if response == 'y':
        if duplicate_account.suspended:
            active_account.suspended = True
            active_account.suspended_date = duplicate_account.suspended_date
        elif duplicate_account.unresolvable:
            active_account.unresolvable = True

        session.delete(duplicate_account)
        session.commit()
        print(f"Merged and removed duplicate for '{active_account.username}'.")
    else:
        print("Merge skipped.")


def fix_duplicates(session, duplicates):
    """

    :param session:
    :param duplicates:
    :return:
    """
    # Ensure logger is defined globally
    logger = logging.getLogger()
    for dup in duplicates:
        accounts = session.query(TwitterAccount).filter(func.lower(TwitterAccount.username) == dup[0]).order_by(
            TwitterAccount.id).all()

        if len(accounts) != 2:
            logger.warning(
                f"Unexpected number of accounts found for username {dup[0]}. Expected 2, found {len(accounts)}.")
            continue

        # Assuming the first account in the ordered list is the original
        original_account, duplicate_account = accounts

        handle_duplicate_accounts(session, original_account, duplicate_account)


def extract_channel_ids_from_files(txt_files_directory):
    """
    Extracts protected channel usernames and IDs from text file names.

    :param txt_files_directory: Directory containing the text files.
    :return: Dictionary with usernames as keys and IDs as values.
    """
    print(f"\n========================================================================================================="
          f"=======\nPREPARING TO FIX THE PROTECTED_CHANNEL_ID'S BY EXTRACTING THEM FROM THE .TXT FILES\n=============="
          f"==================================================================================================")
    channels_from_files = {}
    for filename in os.listdir(txt_files_directory):
        if filename.endswith('.txt') and '(' in filename and ')' in filename:
            username, channel_id = filename.rstrip('.txt').split('(')
            channel_id = channel_id.rstrip(')')
            channels_from_files[username] = channel_id
            print(f"Extracted: {username} - {channel_id}")  # Diagnostic print
    return channels_from_files


def correct_protected_channel_id(impersonator_db_path, txt_files_directory):
    """
    Corrects the protected_channel_id in the database.

    :param impersonator_db_path: Path to the impersonator database.
    :param txt_files_directory: Directory containing the text files.
    :return: None
    """
    channel_ids_from_files = extract_channel_ids_from_files(txt_files_directory)
    correct_engine = create_engine(f'sqlite:///{impersonator_db_path}')
    correct_session = scoped_session(sessionmaker(bind=correct_engine))

    no_account_found_messages = []

    with correct_session() as session:
        for protected_channel, correct_id in channel_ids_from_files.items():
            # Find all accounts with the specified protected_channel
            accounts = session.query(TwitterAccount).filter_by(protected_channel=protected_channel).all()
            if accounts:
                for account in accounts:
                    if account.protected_channel_id != correct_id:
                        # Print detailed information about the account being updated
                        print("========================================================================================"
                              "================")
                        print(f"UPDATING ACCOUNT DETAILS FOR '{account.username}' (Twitter ID: {account.twitter_id}):")
                        print("========================================================================================"
                              "================")
                        print(f" - Old Protected Channel ID: {account.protected_channel_id}")
                        print(f" - New Protected Channel ID: {correct_id}")
                        print(f" - Username: {account.username}")
                        print(f" - Suspended: {account.suspended}")
                        print(f" - Unresolvable: {account.unresolvable}")
                        # Update the protected_channel_id in the database
                        account.protected_channel_id = correct_id
                session.commit()  # Commit after updating all accounts
            else:
                no_account_found_messages.append(f"No account found for protected channel: {protected_channel}")

    # Print messages for channels with no associated accounts
    if no_account_found_messages:
        print("\n======================================================================================================"
              "==")
        print("NO ACCOUNTS FOUND FOR THE FOLLOWING PROTECTED CHANNELS")
        print(f"======================================================================================================="
              f"=")
        for message in no_account_found_messages:
            print(message)


# Correct the database content
def correct_database_content():
    """

    :return:
    """
    logger = logging.getLogger()
    correct_session = scoped_session(sessionmaker(bind=impersonator_engine))

    with correct_session() as session:
        # Check for duplicate entries
        logger.info("Checking for duplicate entries...")
        duplicates = session.query(func.lower(TwitterAccount.username)).group_by(
            func.lower(TwitterAccount.username)).having(
            func.count(TwitterAccount.username) > 1).all()

        if duplicates:
            logger.warning("Duplicate Usernames found.")
            if prompt_for_correction():
                logger.info("Correcting duplicates...")
                fix_duplicates(session, duplicates)
                logger.info("Duplicates corrected.")
            else:
                logger.info("Duplicate correction skipped.")
        else:
            logger.info("No duplicate entries found.")

        # Check data integrity
        logger.info("Checking data integrity...")
        check_data_integrity(session)

        # Correct protected_channel_id values based on text files
        logger.info("Correcting protected_channel_id values...")
        txt_files_directory = os.path.join(find_root(), 'TwitterData', 'TXT-ImpersonatorAccounts')  # Correct path
        correct_protected_channel_id(impersonator_engine.url.database, txt_files_directory)
        logger.info("protected_channel_id values corrected.")


# Attach the bearer token to the HTTP request for authentication.
def bearer_oauth(r):
    """
    Attach the bearer token to the HTTP request for authentication.

    Parameters:
    - r: The HTTP request before sending.

    Returns:
    - r: The HTTP request with the bearer token attached.
    """
    r.headers["Authorization"] = f"Bearer {BEARER_TOKEN}"
    r.headers["User-Agent"] = "v2UserLookupPython"
    return r


# Send a request to the given URL and return the JSON response.
def connect_to_endpoint(url):
    """
    Send a request to the given URL and return the JSON response.

    Parameters:
    - url: The URL of the API endpoint.

    Returns:
    - The JSON response from the API endpoint.

    Raises:
    - Exception: An exception is raised if the request returns an error status code.
    """
    response = requests.request("GET", url, auth=bearer_oauth)
    if response.status_code != 200:
        raise Exception(
            f"Request returned an error: {response.status_code}, {response.text}"
        )
    return response.json()


# Construct and return the Twitter API URL for fetching user information by username.
def create_url_by_username(username):
    """
    id: The unique identifier of this user.
    name: The name of the user, as they’ve defined it on their profile.
    username: The Twitter screen name, handle, or alias that this user identifies themselves with.
    created_at: The UTC datetime that the user account was created on Twitter.
    description: The text of this user's profile description (also known as bio), if the user provided one.
    entities: Contains details about text that has a special meaning in the user's description.
    location: The location specified in the user's profile, if the user provided one.
    pinned_tweet_id: Unique identifier of this user's pinned Tweet.
    profile_image_url: The URL to the profile image for this user, as shown on the user's profile.
    protected: Indicates if this user has chosen to protect their Tweets
               (in other words, if this user's Tweets are private).
    public_metrics: Contains details about activity for this user.
    url: The URL specified in the user's profile, if present.
    verified: Indicates if this user is a verified Twitter User.
    withheld: Contains withholding details for withheld content, if applicable.
    """
    user_fields = ("user.fields=id,name,username,created_at,description,"
                   "public_metrics,location,url,verified,profile_image_url,"
                   "protected,entities,pinned_tweet_id,withheld,blocked_by,blocking,"
                   "follow_request_sent,muting,profile_background_color,profile_background_image_url,"
                   "profile_banner_url,profile_text_color,translator_type,withheld")

    """
    attachments: Contains information about any attached media, URLs, or polls.
    author_id: The unique identifier of the author of this Tweet.
    context_annotations: Contains context annotations including domain and entity IDs.
    conversation_id: The unique identifier of the conversation this Tweet is part of.
    created_at: The UTC datetime when this Tweet was created.
    entities: Contains details about text that has a special meaning in the Tweet, such as hashtags, 
              URLs, user mentions, and cashtags.
    geo: Contains details about the location tagged in the Tweet, if the user has enabled location tagging.
    id: The unique identifier of this Tweet.
    in_reply_to_user_id: The unique identifier of the User this Tweet is in reply to, if applicable.
    lang: The language of the Tweet, if detected by Twitter. Returned as a BCP47 language tag.
    public_metrics: Contains details about public engagement with the Tweet.
    referenced_tweets: Contains details about Tweets this Tweet refers to.
    reply_settings: Indicates who can reply to this Tweet. Returned as either "everyone", 
                    "mentioned_users", or "followers".
    source: The name of the app the user Tweeted from.
    text: The text of the Tweet.
    withheld: Contains withholding details for withheld content, if applicable.
    non_public_metrics: Contains non-public engagement metrics of the Tweet (requires user context).
    organic_metrics: Contains organic engagement metrics of the Tweet (requires user context).
    promoted_metrics: Contains promoted engagement metrics of the Tweet (requires user context).
    possibly_sensitive: Indicates whether this Tweet contains URLs marked as sensitive, for example, by link shorteners.
    filter_level: Indicates the maximum value of the filter_level parameter which may be used and still stream this
                  Tweet. So a value of medium will be streamed on none, low, and medium streams.
    """
    tweet_fields = ("tweet.fields=attachments,author_id,context_annotations,"
                    "conversation_id,created_at,entities,geo,id,in_reply_to_user_id,"
                    "lang,public_metrics,referenced_tweets,reply_settings,source,"
                    "text,withheld,non_public_metrics,organic_metrics,promoted_metrics,"
                    "possibly_sensitive,filter_level")
    """
    attachments.poll_ids: Expands to an array of Polls included in the Tweet.
    attachments.media_keys: Expands to an array of Media included in the Tweet.
    author_id: Expands to the User who authored the Tweet.
    entities.mentions.username: Expands to an array of Users mentioned in the Tweet.
    geo.place_id: Expands to a Place associated with the location tagged in the Tweet.
    in_reply_to_user_id: Expands to the User mentioned in the parent Tweet of a conversation.
    referenced_tweets.id: Expands to an array of Tweets mentioned in the conversation.
    referenced_tweets.id.author_id: Expands to an array of Users who authored referenced Tweets in the conversation.
    """
    expansions = ("expansions=pinned_tweet_id,attachments.media_keys,referenced_tweets.id,"
                  "entities.mentions.username,entities.hashtags,geo.place_id,"
                  "author_id,in_reply_to_user_id,attachments.poll_ids,referenced_tweets.id.author_id")

    """
    media_key: Unique identifier of the media.
    type: Type of media (photo, video, animated GIF).
    duration_ms: Duration of the media in milliseconds (for videos and GIFs).
    height: Height of media in pixels.
    width: Width of media in pixels.
    preview_image_url: URL of the media preview image (for videos and GIFs).
    url: URL of the media.
    public_metrics: Public engagement metrics of the media.
    non_public_metrics: Non-public engagement metrics of the media (requires user context).
    organic_metrics: Organic engagement metrics of the media (requires user context).
    promoted_metrics: Promoted engagement metrics of the media (requires user context).
    alt_text: Alternative text description of the media.
    description: Description of the media.
    """
    media_fields = ("media.fields=duration_ms,height,media_key,preview_image_url,"
                    "type,url,width,public_metrics,non_public_metrics,organic_metrics,"
                    "promoted_metrics,alt_text,description")

    """
    contained_within: Returns the identifiers of known places that contain the referenced place.
    country: The full-length name of the country this place belongs to.
    country_code: The ISO Alpha-2 country code this place belongs to.
    full_name: A longer-form detailed place name.
    geo: Contains place details in GeoJSON format.
    id: The unique identifier of the expanded place, if this is a point of interest tagged in the Tweet.
    name: The short name of this place.
    place_type: Specifies the particular type of information represented by this place information,
                such as a city name, or a point of interest.
    """
    place_fields = "place.fields=contained_within,country,country_code,full_name,geo,id,name,place_type"

    """
    id: Unique identifier of the expanded poll.
    options: Contains objects describing each choice in the referenced poll.
    duration_minutes: Specifies the total duration of this poll.
    end_datetime: Specifies the end date and time for this poll.
    voting_status: Indicates if this poll is still active and can receive votes, or if the voting is now closed.
    """
    poll_fields = "poll.fields=duration_minutes,end_datetime,id,options,voting_status"

    url = (f"https://api.twitter.com/2/users/by/username/{username}?{user_fields}&{tweet_fields}"
           f"&{expansions}&{media_fields}&{place_fields}&{poll_fields}")

    return url


def create_url_by_userid(user_id):
    """

    :param user_id:
    :return:
    """
    user_fields = "user.fields=description,created_at"
    # User fields are adjustable, options include:
    # created_at, description, entities, id, location, name,
    # pinned_tweet_id, profile_image_url, protected,
    # public_metrics, url, username, verified, and withheld
    url = f"https://api.twitter.com/2/users/{user_id}?{user_fields}"
    return url


# Fetch and print the user's recent tweets.
def get_users_tweets(username):
    """
    Fetch and print the user's recent tweets.

    Parameters:
    - username: The Twitter username of the target user.

    Returns:
    - None: Prints the JSON response containing the user's tweets.
    """
    tweet_fields = ("tweet.fields=attachments,author_id,context_annotations,"
                    "conversation_id,created_at,entities,geo,id,in_reply_to_user_id,"
                    "lang,public_metrics,referenced_tweets,reply_settings,source,"
                    "text,withheld,non_public_metrics,organic_metrics,promoted_metrics,"
                    "possibly_sensitive,filter_level")

    url = f"https://api.twitter.com/2/tweets/search/recent?query=from:{username}&{tweet_fields}"
    response = connect_to_endpoint(url)
    print(json.dumps(response, indent=4, sort_keys=True))


# Fetch and print the user's Twitter timeline.
def get_user_timeline(username):
    """
    Fetch and print the user's Twitter timeline.

    Parameters:
    - username: The Twitter username of the target user.

    Returns:
    - None: Prints the JSON response containing the user's timeline.
    """
    tweet_fields = ("tweet.fields=attachments,author_id,context_annotations,"
                    "conversation_id,created_at,entities,geo,id,in_reply_to_user_id,"
                    "lang,public_metrics,referenced_tweets,reply_settings,source,"
                    "text,withheld,non_public_metrics,organic_metrics,promoted_metrics,"
                    "possibly_sensitive,filter_level")

    url = f"https://api.twitter.com/2/tweets/timeline?query=from:{username}&{tweet_fields}"
    response = connect_to_endpoint(url)
    print(json.dumps(response, indent=4, sort_keys=True))


def get_user_id(accounts_db_path, user_email):
    """

    :param accounts_db_path:
    :param user_email:
    :return:
    """
    try:
        # Establish a connection to the SQLite database
        conn = sqlite3.connect(accounts_db_path)  # Establishing a connection to the SQLite database
        cursor = conn.cursor()  # Creating a cursor object to execute SQL commands

        # First, try to get the Twitter ID from the OAuth10a_3Legged table
        query = "SELECT twitter_id FROM OAuth10a_3Legged WHERE email = ?"  # SQL query to select Twitter ID
        cursor.execute(query, (user_email,))  # Executing the SQL query with user_email as a parameter
        result = cursor.fetchone()  # Fetching the result (first row)

        if not result:
            # If not found, try to get the Twitter ID from the OAuth20_PKCE table
            query = "SELECT twitter_id FROM OAuth20_PKCE WHERE email = ?"  # SQL query for alternative table
            cursor.execute(query, (user_email,))  # Executing the SQL query with user_email as a parameter
            result = cursor.fetchone()  # Fetching the result from the alternative table

        conn.close()  # Closing the database connection

        if result and result[0] is not None:
            return int(result[0])  # Convert the Twitter ID to an integer and return it
        else:
            print(f"No Twitter ID found for email: {user_email}")
            return None

    except sqlite3.Error as e:  # Catching any SQLite database operation errors
        raise sqlite3.Error(f"Database error: {e}")  # Raising the error for external handling


# Twitter API v2
def get_user_info_v2(username):
    """
    Fetch user information using Twitter API v2.

    Parameters:
    - username: The Twitter username of the target user.

    Returns:
    - A dictionary containing the user's information.
    """
    url = f"https://api.twitter.com/2/users/by/username/{username}?user.fields=public_metrics,pinned_tweet_id,withheld"
    headers = {"Authorization": f"Bearer {BEARER_TOKEN}"}
    response = requests.get(url, headers=headers)
    return response.json()


# Twitter API v1.1
def get_user_info_v1(username):
    """
    Fetch user information using Twitter API v1.1.

    Parameters:
    - username: The Twitter username of the target user.

    Returns:
    - A dictionary containing the user's information.

    Raises:
    - Exception: An exception is raised if the request returns an error status code.
    """
    url = f"https://api.twitter.com/1.1/users/show.json?screen_name={username}&include_entities=true"
    headers = {"Authorization": f"Bearer {BEARER_TOKEN}"}
    response = requests.get(url, headers=headers)
    return response.json()


# Combine data from both APIs
def get_combined_user_info(username):
    """
    Combine user information fetched from Twitter API v1.1 and v2.

    Parameters:
    - username: The Twitter username of the target user.

    Returns:
    - A dictionary containing the combined user information from both API versions.
    """
    info_v2 = get_user_info_v2(username)
    info_v1 = get_user_info_v1(username)

    # Combine the data (update v2 data with v1 data)
    combined_info = info_v2.get('data', {})
    combined_info.update(info_v1)

    return combined_info


def safe_request(method, url, headers, request_cookies, data):
    """

    :param method:
    :param url:
    :param headers:
    :param request_cookies:
    :param data:
    :return:
    """
    try:
        # Sending the HTTP request with the specified method, URL, headers, cookies, and data.
        response = requests.request(method, url, headers=headers, cookies=request_cookies, data=data)
        # log_debug(f"Response status code: {response.status_code}")
        response.raise_for_status()  # Check if the response status code indicates success (200-299 range).
        return response
    except requests.RequestException as e:
        # Log the error if the request fails
        log_error(f"Request failed: {e}")
        return None


def is_account_suspended(impersonator_db_path, twitter_id):
    """

    :param impersonator_db_path:
    :param twitter_id:
    :return:
    """
    try:
        conn = sqlite3.connect(impersonator_db_path)
        cursor = conn.cursor()

        query = "SELECT suspended FROM impersonator_account WHERE twitter_id = ?"
        cursor.execute(query, (twitter_id,))

        result = cursor.fetchone()
        conn.close()

        print(f"Debug: Checking suspended status for twitter_id={twitter_id}, result={result}")  # Debug print

        if result:
            return result[0] == 1  # Return True if account is marked as suspended
        else:
            return False  # Return False if no record is found

    except sqlite3.Error as e:
        print(f"Database error during suspension check: {e}")
        return False  # Return False in case of any error


def get_protected_channels(impersonators_db_path):
    """
    Fetches unique protected channels from the database.

    :return: A list of unique protected channels.
    """
    try:
        conn = sqlite3.connect(impersonators_db_path)
        cursor = conn.cursor()

        # SQL query to select distinct protected channels and their IDs
        query = ("SELECT DISTINCT protected_channel, protected_channel_id FROM impersonator_account WHERE "
                 "protected_channel IS NOT NULL AND protected_channel_id != '0'")
        cursor.execute(query)
        results = cursor.fetchall()
        conn.close()
        # Filter out duplicates based on channel name and ID.
        unique_channels = []
        seen = set()
        for channel, channel_id in results:
            if (channel, channel_id) not in seen:
                seen.add((channel, channel_id))
                unique_channels.append((channel, channel_id))

        return unique_channels

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return []


def validate_user_choice(choice, txt_files):
    """

    :param choice:
    :param txt_files:
    :return:
    """
    if not choice.strip():  # Check for non-empty input.
        print("Invalid input. Please enter a non-empty option.")
        return False
    if choice.isdigit():  # Check if the choice is a valid number within the range of text files.
        choice_number = int(choice)
        if 1 <= choice_number <= len(txt_files):
            return True
        else:
            print(f"Invalid selection. The number should be between 1 and {len(txt_files)} to correspond with the "
                  "listed protected channels.")
            return False
    if choice.upper() == "ALL":  # Handle the case for selecting all channels.
        return True
    if ',' in choice:  # Process comma-separated choices.
        choices = choice.split(',')
        for ch in choices:
            ch = ch.strip()
            if not ch.isdigit() and not any(ch.lower() in txt_file.lower() for txt_file in txt_files):
                print(f"Invalid name: {ch}")
                return False
        return True
    channel_names = [os.path.basename(txt_file).replace(  # Validate against channel names derived from text files.
        'Active-', '').replace('.txt', '').lower() for txt_file in txt_files]
    if choice.lower() in channel_names:
        return True
    print("Invalid input format. Please enter a valid option.")  # Return False for any other invalid input formats.
    return False


def get_twitter_credentials(accounts_db_path, user_email):
    """
    Retrieve Twitter OAuth 1.0a credentials (consumer key, consumer secret, OAuth token, and OAuth token secret)
    from the SQLite database for a specific user's email.

    Args:
        accounts_db_path (str): The path to the SQLite database file.
        user_email (str): The email address of the user whose Twitter credentials are to be retrieved.

    Returns:
        tuple: A tuple containing consumer key (str), consumer secret (str), OAuth token (str), and
               OAuth token secret (str) if found.

    Raises:
        ValueError: If the Twitter consumer key and/or secret are not set in environment variables.
        ValueError: If no credentials are found for the specified email.
        sqlite3.Error: If there's an error in database operations.

    :param accounts_db_path:
    :param user_email:
    :return:
    """
    try:
        # Establish a connection to the SQLite database
        conn = sqlite3.connect(accounts_db_path)  # Establishing a connection to the SQLite database
        cursor = conn.cursor()  # Creating a cursor object to execute SQL commands

        # Query to get the OAuth credentials for a specific user
        query = """SELECT oauth_token, oauth_token_secret
                   FROM OAuth10a_3Legged
                   WHERE email = ?"""
        cursor.execute(query, (user_email,))  # Executing the SQL query with user_email as a parameter

        # Fetch the credentials
        result = cursor.fetchone()  # Fetching the result

        conn.close()  # Closing the database connection

        if result:
            oauth_token, oauth_token_secret = result
            consumer_key = API_AKA_CONSUMER_KEY
            consumer_secret = API_AKA_CONSUMER_KEY_SECRET

            # Validate that consumer key and consumer secret are set in environment variables
            if not consumer_key or not consumer_secret:
                raise ValueError("Twitter consumer key and/or secret are not set in environment variables")

            return consumer_key, consumer_secret, oauth_token, oauth_token_secret
        else:
            raise ValueError("No credentials found for email: " + user_email)

    except sqlite3.Error as e:  # Catching any SQLite database operation errors
        raise sqlite3.Error(f"Database error: {e}")  # Raising the error for external handling


# Make the log_* functions directly accessible when importing the module
__all__ = ['find_root', 'get_databases', 'set_logging', 'log_debug', 'log_info', 'log_warning', 'log_error',
           'log_critical', 'global_cookies', 'generate_custom_transaction_id', 'get_registered_user_id',
           'SQLALCHEMY_DATABASE_URI', 'prompt_for_cookie_update', 'normalize_cookie_data', 'extract_cookie_value',
           'parse_cookies', 'update_cookies', 'list_twitter_accounts_with_emails', 'get_filtered_protected_channels',
           'get_cookies_for_account', 'get_active_impersonator_accounts', 'list_user_emails', 'get_user_id',
           'safe_request', 'is_account_suspended', 'get_protected_channels', 'validate_user_choice',
           'get_twitter_credentials']


def main():
    """
    Main function to run the script.
    """
    while True:
        print("\nChoose an option:")
        print("1. Update Database Cookies")
        print("2. Update Database Structure")
        print("3. Correct Database Content")
        print("4. Twitter Username")
        print("5. Twitter AccountID")
        print("6. Quit")

        choice = input("Enter your choice (1-6): ").strip()

        if choice == '1':
            initialize_cookies_in_database()
            print("Cookies initialized successfully.")
        elif choice == '2':
            update_database_structure()
        elif choice == '3':
            correct_database_content()
        elif choice == '4':
            username = input("Get Account Info by Username: ")
            combined_info = get_combined_user_info(username)
            print(json.dumps(combined_info, indent=4, sort_keys=True))
        elif choice == '5':
            user_id = input("Get Account Info by TwitterID: ")
            url = create_url_by_userid(user_id)
            json_response = connect_to_endpoint(url)
            print(json.dumps(json_response, indent=4, sort_keys=True))
        elif choice == '6':
            print("Exiting the script.")
            break
        else:
            print("Invalid choice. Please enter a number between 1 and 6.")


if __name__ == "__main__":
    main()
