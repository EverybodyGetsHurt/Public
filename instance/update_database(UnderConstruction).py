"""
    Placeholder
"""
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, JSON, func, exc
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base
from datetime import datetime
from logging.handlers import RotatingFileHandler
from instance import config
from typing import List
import sqlalchemy
import traceback
import requests
import logging
import json
import glob
import time
import sys
import os

# Directory setup
base_dir = os.path.dirname(os.path.abspath(__file__))

# Logging setup
log_filename = os.path.join(base_dir, "..", "logs", "ImpersonatorAccounts.log")
if not os.path.exists(os.path.dirname(log_filename)):
    os.makedirs(os.path.dirname(log_filename))
logger = logging.getLogger()  # Creating a custom logger
logger.setLevel(logging.DEBUG)  # You can set this to the lowest level of logging messages you want to handle
handler = RotatingFileHandler(log_filename, maxBytes=int(49.9 * 1024 * 1024), backupCount=1, encoding='utf-8')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
handler.setFormatter(formatter)  # Add formatter to handler
logger.addHandler(handler)  # Add handler to logger
# logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)  # Show all the database interaction in the output

# Database and SQLAlchemy setup
DATABASE_PATH = os.path.join(base_dir, "ImpersonatorAccounts.sqlite")
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
Base = declarative_base()
engine = create_engine(DATABASE_URL)
Session = scoped_session(sessionmaker(bind=engine))

# API setup and tokens
main_token = config.BEARER_TOKEN
backup_token = config.BEARER_TOKEN_V2
tokens_list = [main_token, backup_token]


# Token Manager for handling the token rotation
class TokenManager:
    """
        TokenManager
    """

    def __init__(self, tokens):
        self.tokens_list = tokens
        self.current_token_index = 0
        self.rate_limited_tokens = set()

    def get_current_token(self):
        """

        :return:
        """
        return self.tokens_list[self.current_token_index]

    def rotate_token(self):
        """

        :return:
        """
        self.current_token_index = (self.current_token_index + 1) % len(self.tokens_list)
        masked_token = mask_token(f'Bearer {self.tokens_list[self.current_token_index]}')
        logging.debug(f"Rotated to token {self.current_token_index}: {masked_token}")

    def mark_token_as_rate_limited(self, token):
        """

        :param token:
        :return:
        """
        self.rate_limited_tokens.add(token)
        masked_token = mask_token(f'Bearer {token}')
        logging.debug(f"Marked token as rate-limited: {masked_token}")

    def all_tokens_rate_limited(self):
        """

        :return:
        """
        all_rate_limited = len(self.rate_limited_tokens) == len(self.tokens_list)
        logging.debug(f"All tokens rate-limited: {all_rate_limited}")
        return all_rate_limited

    def reset_rate_limited_tokens(self):
        """

        :return:
        """
        self.rate_limited_tokens.clear()


token_manager = TokenManager(tokens_list)


def mask_token(authorization_header):
    """

    :param authorization_header:
    :return:
    """
    token = authorization_header.split(' ')[1]  # Extract the actual token from the header
    masked_token = '*' * 18 + token[-5:]  # Mask all characters of the token except for the last 5
    return masked_token


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
class TwitterAccount(Base):
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
        self.twitter_id = kwargs.get("id")
        self.username = kwargs.get("username")
        self.name = kwargs.get("name")
        self.followers_count = kwargs.get("public_metrics", {}).get("followers_count")
        self.following_count = kwargs.get("public_metrics", {}).get("following_count")
        self.tweet_count = kwargs.get("public_metrics", {}).get("tweet_count")
        self.username_changed = False
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

    def update_username(self, new_username):
        """
        Update the account's username and track changes.
        """
        if self.username != new_username:
            # Append the old username to the previous_username list
            if self.previous_username:
                self.previous_username += ',' + self.username
            else:
                self.previous_username = self.username

            # Update username and change-related attributes
            self.username = new_username
            self.username_changed = True
            self.username_changed_date = datetime.now()

    def update_api_response(self, new_response):
        """
        Update the account's API response.
        """
        # Convert new_response to JSON if it's not already a string
        if not isinstance(new_response, str):
            new_response = json.dumps(new_response, cls=SafeEncoder)

        # Update api_response and related attributes
        self.previous_api_response = self.api_response
        self.previous_api_response_updated_at = self.api_response_updated_at
        self.api_response = new_response
        self.api_response_updated_at = datetime.now()
        # Ensure that new_response is converted to JSON only if it's not already a JSON string
        if not isinstance(new_response, str):
            self.api_response = json.dumps(new_response, cls=SafeEncoder)
        else:
            self.api_response = new_response
        self.api_response_updated_at = datetime.now()

    def __repr__(self):
        return f"<TwitterAccount(username={self.username}, twitter_id={self.twitter_id}, suspended={self.suspended})>"


# Function to split the list of usernames into chunks for batch processing
def chunked_usernames(usernames: List[str], chunk_size: int = 100):
    """

    :param usernames:
    :param chunk_size:
    :return:
    """
    for i in range(0, len(usernames), chunk_size):
        yield usernames[i:i + chunk_size]


# Function made to reduce repetitive code
def commit_session(session):
    """

    :param session:
    :return:
    """
    try:
        session.commit()
        logging.info("Database commit successful.")
        return True
    except Exception as e:
        session.rollback()
        logging.error(f"Database commit failed: {e}", exc_info=True)
        return False


# Function to check if the database is empty
def is_database_empty(session=None):
    """

    :param session:
    :return:
    """
    if not session:
        session = Session()
    return session.query(TwitterAccount).first() is None


# Function to create the database tables
def create_tables():
    """

    :return:
    """
    Base.metadata.create_all(engine)


# Function to extract the protected channel name and id from the filename
def get_protected_channel_name_and_id_from_filename(filename):
    """
    Extracts the protected channel name and ID from the filename.

    :param filename: The filename from which to extract the information.
    :return: A tuple containing the protected channel name and ID.
    """
    # Extract the channel name and ID from the filename format 'ChannelName(ChannelID).txt'
    base_name = os.path.basename(filename).replace(".txt", "")
    protected_channel, protected_channel_id = base_name.split("(")
    protected_channel_id = protected_channel_id.replace(")", "")
    return protected_channel, protected_channel_id


# Function to retrieve all impersonator accounts for a specific protected channel
def get_impersonators_for_protected_channel(session, protected_channel):
    """

    :param session:
    :param protected_channel:
    :return:
    """
    impersonators_query = session.query(TwitterAccount).filter_by(protected_channel=protected_channel)
    return impersonators_query.all()


# Function to retrieve a TwitterAccount object by Twitter ID
def get_account_by_twitter_id(twitter_id, session):
    """

    :param twitter_id:
    :param session:
    :return:
    """
    return session.query(TwitterAccount).filter_by(twitter_id=twitter_id).first()


# Function to extract the username from the Twitter URL
def get_username_from_url(url):
    """

    :param url:
    :return:
    """
    return url.strip().split("/")[-1]


# Function to create headers for the API request
def create_headers(bearer_token):
    """

    :param bearer_token:
    :return:
    """
    headers = {"Authorization": f"Bearer {bearer_token}"}
    return headers


# Function to create the URL for the API request
def create_url(request_type, data):
    """
    Constructs the URL for the API request based on the request type and data provided.

    :param request_type: Type of request ('username' or 'twitter_id').
    :param data: A list of usernames or Twitter IDs.
    :return: Constructed URL for the API request.
    """
    base_url = config.UPDATE_DATABASE_BASE_URL

    if request_type == 'username':
        usernames = ",".join(data)
        url = (f"{base_url}?usernames={usernames}&user.fields=created_at,description,id,name,profile"
               f"_image_url,public_metrics,url,username,verified")
    elif request_type == 'twitter_id':
        twitter_ids = ",".join(data)
        url = (f"{base_url}?ids={twitter_ids}&user.fields=created_at,description,id,name,profile"
               f"_image_url,public_metrics,url,username,verified")
    else:
        raise ValueError("Invalid request type. Expected 'username' or 'twitter_id'.")

    return url


def create_or_update_account(user_data, session):
    """
    Creates a new account or updates an existing one in the database based on the provided user data.

    This function checks if an account with the given Twitter ID, username, or previous username already exists in the
    database. If it does, the function updates the existing account with the new data. If not, it creates a new
    account with the provided data.

    Args:
        user_data (dict): A dictionary containing data about a Twitter account. Expected keys include 'id' (Twitter ID),
                        'username', 'created_at', and other fields corresponding to the TwitterAccount model attributes.
        session (scoped_session): The SQLAlchemy session used to interact with the database.

    The function handles the 'created_at' field specifically, converting it to a datetime object using the
    `parse_datetime` function.

    Returns:
        None. However, it logs information about the operation's success or failure. It logs a debug message about
        whether it's updating an existing account or creating a new one, and an info or error message based on the
        success of the database commit operation.

    The function ensures that the account's information in the database is up-to-date with the latest data from
    the Twitter API or other sources.
    """
    try:
        logging.debug(f"Processing account with user data: {user_data}")

        twitter_id = user_data.get('id')
        username = user_data.get('username')

        # Handle 'created_at' field
        created_at_str = user_data.get('created_at', '')
        user_data['created_at'] = parse_datetime(created_at_str)

        # Check for an existing account with the twitter_id, username, or previous_username
        existing_account = session.query(TwitterAccount).filter(
            (TwitterAccount.twitter_id == twitter_id) |
            (func.lower(TwitterAccount.username) == func.lower(username)) |
            (TwitterAccount.previous_username.contains(username))
        ).first()

        if existing_account:
            # Update the existing account
            logging.debug(f"Updating existing account for twitter_id: {twitter_id}")
            for key, value in user_data.items():
                if hasattr(existing_account, key) and key not in ['id', 'protected_channel_id']:
                    setattr(existing_account, key, value)
        else:
            # Create a new account
            logging.debug(f"Creating new account for twitter_id: {twitter_id}")
            new_account = TwitterAccount(**user_data)
            session.add(new_account)

        # Commit the session
        if commit_session(session):
            logging.info(f"Account {'updated' if existing_account else 'created'} in the database successfully.")
        else:
            logging.error("Error committing to the database.")

    except sqlalchemy.exc.SQLAlchemyError as e:
        logging.error(f"SQLAlchemy error occurred: {e}", exc_info=True)
    except Exception as e:
        logging.error(f"Unexpected error occurred: {e}", exc_info=True)


def parse_datetime(datetime_str):
    """ Parse the datetime string from the API response. """
    if isinstance(datetime_str, str) and datetime_str:
        try:
            return datetime.fromisoformat(datetime_str.rstrip("Z"))
        except ValueError as e:
            logging.error(f"Error parsing created_at: {e}, value: {datetime_str}")
    return None


def connect_to_endpoint(url, headers, max_retries=1):
    """
    Connects to the Twitter API endpoint with error handling, token rotation, and rate limit management.

    :param url: The URL to connect to.
    :param headers: Request headers.
    :param max_retries: Maximum number of retries for the request.
    :return: The JSON response from the API or None if all attempts fail.
    """
    retries = 0
    masked_token = mask_token(headers['Authorization'])  # Initialize masked_token before the try block

    while retries <= max_retries:
        try:
            logging.info(f"Connecting to URL: {url} with token: {masked_token}")
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            if response.status_code != 429:
                return response.json()

        except requests.HTTPError as e:
            current_token = token_manager.get_current_token()

            if e.response.status_code == 429:
                print(f"\n____________________________________________________________________________\nGenerating API "
                      f"request... Failed\n____________________________________________________________________________"
                      f"\nRate-Limit hit for Token: {masked_token}\nSwitching Token...")
                token_manager.mark_token_as_rate_limited(current_token)

                if token_manager.all_tokens_rate_limited():
                    logging.error("All tokens are rate-limited. Halting operation.")
                    print("Token switch failed.\nThe script is now shutting down...\n\n++++++++++++++++++++++++++++++++"
                          "++++++++++++++++++++++++++++++++++++++++++++\nAll tokens are rate-limited. Halting operation"
                          ".\n++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
                    sys.exit(0)

                token_manager.rotate_token()
                headers['Authorization'] = f'Bearer {token_manager.get_current_token()}'
                masked_token = mask_token(headers['Authorization'])  # Update the masked token
                print("Token switch successful.\nRetrying Request...")
                retries += 1
                continue
            else:
                error_message = f"HTTP error occurred for URL {url} with token {masked_token}: {e}"
                logging.error(f"HTTP error occurred: {e}", exc_info=True)
                print(error_message)
                raise

        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}", exc_info=True)
            raise

        if retries > max_retries:
            logging.error("Max retries reached for the API request.")
            raise Exception("Max retries reached for the API request.")

    return None


def calculate_wait_time(response):
    """
    Calculates the wait time based on the 'x-rate-limit-reset' header from the response.

    :param response: The response object from the request.
    :return: The number of seconds to wait before the rate limit resets.
    """
    rate_limit_reset = int(response.headers.get('x-rate-limit-reset', 0))
    current_time = int(time.time())
    return max(rate_limit_reset - current_time, 1)


def make_api_request(url, retries=3, delay=1):
    """
    Makes an API request with a retry mechanism.

    :param url: The URL for the API request.
    :param retries: Number of times to retry the request in case of failure.
    :param delay: Initial delay between retries in seconds.
    :return: The JSON response from the API or None if the request fails.
    """
    attempt = 0
    while attempt < retries:
        headers = create_headers(token_manager.get_current_token())
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            if response.status_code == 429:  # Rate limit exceeded
                handle_rate_limit(response, attempt)
            else:
                logging.error(f"HTTP error on attempt {attempt + 1} for URL {url}: {e}", exc_info=True)
        except Exception as e:
            logging.error(f"An unexpected error occurred on attempt {attempt + 1}: {e}", exc_info=True)

        attempt += 1
        time.sleep(delay * attempt)  # Exponential backoff

    logging.error("Max retries reached for the API request.")
    return None


def handle_rate_limit(response, attempt):
    """
    Handles rate limit situations by waiting and rotating tokens if necessary.

    :param response: The response object from the request.
    :param attempt: Current attempt number.
    """
    if token_manager.all_tokens_rate_limited():
        wait_time = calculate_wait_time(response)
        logging.warning(f"All tokens are rate-limited. Waiting for {wait_time} seconds before attempt {attempt + 1}.")
        time.sleep(wait_time)
        token_manager.reset_rate_limited_tokens()
    else:
        logging.warning(f"Token rate-limited. Rotating token and retrying attempt {attempt + 1}.")
        token_manager.mark_token_as_rate_limited(token_manager.get_current_token())
        token_manager.rotate_token()


def process_api_response(response, session, protected_channel, protected_channel_id):
    """

    :param response:
    :param session:
    :param protected_channel:
    :param protected_channel_id:
    :return:
    """
    if not response:
        logging.error("No response received from the API.")
        return

    suspended_header, change_header, unresolvable_header, active_header = False, False, False, False
    username_changes = []  # List to store details of username changes
    active_accounts = []  # List to store active accounts

    # Processing errors in the response
    if 'errors' in response:
        for error in response['errors']:
            detail = error.get('detail', '').lower()
            username = error.get('value')
            account = session.query(TwitterAccount).filter(
                (TwitterAccount.username.ilike(username)) |
                (TwitterAccount.previous_username.contains(username))
            ).first()

            if 'suspended' in detail:
                if not suspended_header:
                    print(f"\n_____________________________________________\nProcess API response... "
                          f"for {protected_channel}:\n_____________________________________________")
                    suspended_header = True
                process_suspended_user(account, username, error, protected_channel, protected_channel_id, session)
            elif 'not found' in detail:
                if not unresolvable_header:
                    print(f"\n_____________________________________________\nProcess API response... "
                          f"for {protected_channel}:\n_____________________________________________")
                    unresolvable_header = True
                process_not_found_user(username, error, protected_channel, protected_channel_id, session, account)
            else:
                change_detail = process_username_change(account, username, session, protected_channel)
                if change_detail:  # Only add non-None changes
                    username_changes.append(change_detail)

    # Collect data in the response for later processing
    if 'data' in response:
        for user_data in response['data']:
            account = get_account_by_twitter_id(user_data['id'], session)
            if account and account.username.lower() != user_data['username'].lower():
                change_detail = process_username_change(account, user_data['username'], session, protected_channel)
                if change_detail:
                    if not change_header:
                        print(f"\n_____________________________________________\nUsername changes detected "
                              f"for {protected_channel}:\n_____________________________________________")
                        change_header = True
                    username_changes.append(change_detail)
                    print(change_detail)
            active_accounts.append(user_data)

    # Print Active Accounts after processing username changes
    if active_accounts:
        print(f"\n_____________________________________________\nAll information processed "
              f"for {protected_channel}:\n_____________________________________________")
        for user_data in active_accounts:
            print(f"{protected_channel} is impersonated by: {user_data['username']} (ID:{user_data['id']})")
            process_active_user(get_account_by_twitter_id(user_data['id'], session), user_data, protected_channel,
                                protected_channel_id, session)


def process_api_errors(errors, session, protected_channel, protected_channel_id):
    """
    Processes the errors part of the API response.
    """
    for error in errors:
        detail = error.get('detail', 'No detail provided')
        logging.error(f"API Error: {detail}")

        username = error.get('value')
        account = session.query(TwitterAccount).filter(
            func.lower(TwitterAccount.username) == func.lower(username) |
            TwitterAccount.previous_username.contains(username)
        ).first()

        if 'suspended' in detail.lower() and account:
            process_suspended_user(account, username, error, protected_channel, protected_channel_id, session)
        elif 'not found' in detail.lower():
            process_not_found_user(username, error, protected_channel, protected_channel_id, session, account)
        else:
            logging.info(f"No account processing required for username: {username} with error detail: {detail}")
            print(f"No action taken for username: {username}")


def process_not_found_user(username, error, protected_channel, protected_channel_id, session, existing_account=None):
    """
    Processes a user that was not found in the API response.
    If no account exists, creates a new account and marks it as unresolvable on the second encounter.
    """
    logging.info(f"Processing not found user: {username}")

    if existing_account:
        if not existing_account.unresolvable:
            existing_account.unresolvable = True
            existing_account.api_response = error
            if existing_account.protected_channel_id is None:
                existing_account.protected_channel_id = protected_channel_id
            print(f"Unresolvable Account: {username}")
    else:
        new_account_data = {
            'username': username,
            'protected_channel': protected_channel,
            'protected_channel_id': protected_channel_id,
            'api_response': error,
            # Mark as unresolvable only if encountered again
            'unresolvable': False
        }
        new_account = TwitterAccount(**new_account_data)
        session.add(new_account)
        print(f"New Account Created (Pending Unresolvable Status): {username} - for {protected_channel}")
    commit_session(session)


def process_suspended_user(account, username, error, protected_channel, protected_channel_id, session):
    """
    Processes a user account marked as suspended. If no account exists, creates a new suspended account.
    """
    if account:
        if not account.suspended:
            account.mark_as_suspended()
            account.api_response = json.dumps(error, cls=SafeEncoder)
            if account.protected_channel_id is None:
                account.protected_channel_id = protected_channel_id
            print(f"Status Suspended: {username.ljust(20)} (ID:{account.twitter_id})")
        else:
            print(f"Already Suspended: {username.ljust(20)} (ID:{account.twitter_id})")
    else:
        new_account_data = {
            'username': username,
            'suspended': True,
            'api_response': json.dumps(error, cls=SafeEncoder),
            'protected_channel': protected_channel,
            'protected_channel_id': protected_channel_id,
            'suspended_date': datetime.now()
        }
        new_account = TwitterAccount(**new_account_data)
        session.add(new_account)
        commit_session(session)
        print(f"New Suspended Account: {username.ljust(20)} - Account Created")
    logging.info(f"Processed suspended user: {username}")


def process_username_change(account, new_username, session, protected_channel):
    """
    Handles changes in a user's username.
    If a new username matches an unresolvable account, remove the unresolvable entry and update the username.
    """
    if account.username.lower() != new_username.lower():
        logging.info(f"Username change detected for {account.username} to {new_username} in {protected_channel}")

        # Check for an unresolvable account with the new username
        unresolvable_account = session.query(TwitterAccount).filter(
            func.lower(TwitterAccount.username) == func.lower(new_username),
            TwitterAccount.unresolvable is True
        ).first()

        if unresolvable_account:
            # Remove the unresolvable account as the username is now being adopted by an active account
            session.delete(unresolvable_account)
            logging.info(f"Removed unresolvable account with username {new_username} to accommodate username change.")

        # Check if there is a real username change
        if account.username != new_username:
            # Store the old username in the previous_username field
            if account.previous_username:
                account.previous_username += ',' + account.username
            else:
                account.previous_username = account.username

            # Update the username of the current account
            account.username = new_username

            # Update the username_changed column with the count of previous usernames
            account.username_changed = len(account.previous_username.split(',')) - 1
            account.username_changed_date = datetime.now()

        if commit_session(session):
            return (f"Username updated: {account.previous_username.split(',')[-1]} to "
                    f"{new_username} for account ID:{account.twitter_id}")
        else:
            logging.error(f"Error committing username change for {account.username}")
    else:
        logging.info(f"No username change detected for {account.username}")

    return None


# Define a flag to indicate if unresolvable accounts have been printed for a channel
unresolvable_accounts_printed = {}


def process_unresolvable_user(db_session, usernames_chunk, protected_channel_id, protected_channel):
    """
    Processes users marked as unresolvable by checking if they have become resolvable.
    """
    global reactivated_usernames  # Declare that you want to use the global variable

    url = create_url('username', usernames_chunk)
    headers = create_headers(token_manager.get_current_token())
    response_data = connect_to_endpoint(url, headers)

    if response_data and 'data' in response_data:
        for user_data in response_data['data']:
            twitter_id = user_data.get("id")
            username = user_data.get("username")

            account = db_session.query(TwitterAccount).filter(
                (TwitterAccount.twitter_id == twitter_id) |
                (func.lower(TwitterAccount.username) == func.lower(username))
            ).first()

            if account:
                account.twitter_id = twitter_id
                account.update_username(username)
                account.update_api_response(user_data)
                account.unresolvable = False
                account.protected_channel_id = protected_channel_id
                print(f"Reactivated Unresolvable: {username} (ID:{twitter_id}) for {protected_channel}")
            else:
                new_account_data = user_data
                new_account_data['unresolvable'] = False
                new_account_data['protected_channel'] = protected_channel
                new_account_data['protected_channel_id'] = protected_channel_id
                new_account = TwitterAccount(**new_account_data)
                db_session.add(new_account)
                print(f"Created Reactivated Account: {username} (ID:{twitter_id}) for {protected_channel}")

            reactivated_usernames.append(username)

            if not commit_session(db_session):
                logging.error(f"An error occurred while committing {username} to the database.")


def process_active_user(account, user_data, protected_channel, protected_channel_id, session):
    """
    Processes an active user account.
    """
    logging.debug(f"Processing active user: {user_data['username']}")

    if account:
        logging.info(f"Updating existing account for {user_data['username']}")
        account.update_username(user_data['username'])
        account.update_api_response(user_data)
        # print(f"Updated Active User: {user_data['username']} (ID:{account.twitter_id}) for {protected_channel}")
        account.unresolvable = False
        if account.protected_channel_id is None:
            account.protected_channel_id = protected_channel_id

    else:
        logging.info(f"Creating new account for {user_data['username']}")
        user_data['protected_channel'] = protected_channel
        user_data['protected_channel_id'] = protected_channel_id
        new_account = TwitterAccount(**user_data)
        session.add(new_account)
        print(f"Created New Active User: {user_data['username']} (ID:{user_data['id']}) for {protected_channel}")

    if not commit_session(session):
        logging.error(f"Error committing the account {user_data['username']} to the database.")
        print(f"Failed to update or create active user {user_data['username']}.")


# Define reactivated_usernames here
reactivated_usernames = []


def process_user_choice(choice, txt_files):
    """
    Process the user's choice of protected channels.
    """
    if not choice or not choice.strip():
        print(
            "Invalid input. Please enter a number or name corresponding to the protected channels, or type 'ALL' to sel"
            "ect all channels.")
        return

    def process_choice(inner_choice):
        """
        Process the choice made by the user.
        """
        try:
            choice_number = int(inner_choice)
            selected_file = txt_files[choice_number - 1]
            local_protected_channel, local_protected_channel_id = get_protected_channel_name_and_id_from_filename(
                selected_file)
            with open(selected_file, 'r') as chosen_file:
                urls = [line.strip() for line in chosen_file if line.strip()]

            usernames = [get_username_from_url(url).lower() for url in urls if url.strip()]
            if not usernames:
                logging.error(f"The usernames list is empty for file {selected_file}.")
                return

            errors, seen_usernames, duplicate_usernames = [], set(), set()
            for username in usernames:  # Renamed uname to username
                if username in seen_usernames:
                    duplicate_usernames.add(username)
                seen_usernames.add(username)

            if duplicate_usernames:
                formatted_usernames = ', '.join(duplicate_usernames[:2]) + ',\n' + ',\n'.join(
                    [', '.join(duplicate_usernames[i:i + 5]) for i in range(2, len(duplicate_usernames), 5)])
                errors.append(f"Error: The following usernames are duplicated: {formatted_usernames}")

            invalid_usernames = [username for username in usernames if len(username) > 15]
            if invalid_usernames:
                formatted_usernames = ', '.join(invalid_usernames[:2]) + ',\n' + ',\n'.join(
                    [', '.join(invalid_usernames[i:i + 5]) for i in range(2, len(invalid_usernames), 5)])
                errors.append(f"Error: The following usernames are too long: {formatted_usernames}")

            if errors:
                print(
                    f"\n____________________________________________________________________________\nProcessing TXT "
                    f"content... for {local_protected_channel}\n_______________________________________________________"
                    f"_____________________\nError(s) found. Correct the Active-{local_protected_channel}.txt file and "
                    f"retry.")
                for error in errors:
                    print(error)
                return

            with Session() as db_session:
                unresolvables = db_session.query(TwitterAccount).filter_by(
                    unresolvable=True, protected_channel=local_protected_channel).all()
                unresolvable_usernames = [account.username for account in unresolvables]

                # Display unresolvable accounts for the selected channel
                print("\n_____________________________________________")
                print(f"Process API response... for {local_protected_channel}:")
                print("_____________________________________________")
                for unresolvable_username in unresolvable_usernames:  # Renamed uname to unresolvable_username
                    print(f"Unresolvable Account: {unresolvable_username}")

                chunks = list(chunked_usernames(usernames))
                for chunk in chunks:
                    url = create_url('username', chunk)
                    headers = create_headers(token_manager.get_current_token())
                    response_data = connect_to_endpoint(url, headers)

                    if response_data is not None:
                        process_api_response(response_data, db_session, local_protected_channel,
                                             local_protected_channel_id)

                for process_usernames_chunk in chunked_usernames(unresolvable_usernames, 100):
                    process_unresolvable_user(db_session, process_usernames_chunk, reactivated_usernames,
                                              local_protected_channel_id)

        except ValueError as e:
            print(f"ValueError occurred: {e}\nInvalid input. Please enter a number.")
        except IndexError:
            print("Invalid selection. Please enter a number corresponding to the available options.")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}", exc_info=True)
            traceback.print_exc()

    if choice.upper() == "ALL":
        for txt_file in txt_files:
            # Extract the protected channel name
            protected_channel, _ = get_protected_channel_name_and_id_from_filename(os.path.basename(txt_file))
            process_choice(str(txt_files.index(txt_file) + 1))

    elif ',' in choice:
        choices = choice.split(',')
        for ch in choices:
            ch = ch.strip()
            if ch.isdigit():
                process_choice(ch)
            else:
                channel_names = [os.path.basename(txt_file).replace('Active-', '').replace('.txt', '') for txt_file in
                                 txt_files]
                if ch in channel_names:
                    process_choice(str(channel_names.index(ch) + 1))
                else:
                    print(f"Invalid name: {ch}")
    else:
        if choice.isdigit():
            process_choice(choice)
        else:
            channel_names = [os.path.basename(txt_file).replace('Active-', '').replace('.txt', '') for txt_file in
                             txt_files]
            if choice in channel_names:
                process_choice(str(channel_names.index(choice) + 1))
            else:
                print("Invalid input. Please enter a valid number or channel name.")
                return

    # After processing all channels, display reactivated accounts if any
    if reactivated_usernames:
        print("\n_____________________________________________")
        print(f"Reactivated Accounts for all channels:")
        print("_____________________________________________")
        for uname in reactivated_usernames:
            print(f"Reactivated Account: {uname}")


def validate_user_choice(choice, txt_files):
    """

    :param choice:
    :param txt_files:
    :return:
    """
    if not choice.strip():
        print("Invalid input. Please enter a non-empty option.")
        return False

    if choice.isdigit():
        choice_number = int(choice)
        if 1 <= choice_number <= len(txt_files):
            return True
        else:
            print(f"Invalid selection. The number should be between 1 and {len(txt_files)} to correspond with the "
                  "listed protected channels.")
            return False

    if choice.upper() == "ALL":
        return True

    if ',' in choice:
        choices = choice.split(',')
        for ch in choices:
            ch = ch.strip()
            if not ch.isdigit() and not any(ch.lower() in txt_file.lower() for txt_file in txt_files):
                print(f"Invalid name: {ch}")
                return False
        return True

    channel_names = [os.path.basename(txt_file).replace(
        'Active-', '').replace('.txt', '').lower() for txt_file in txt_files]
    if choice.lower() in channel_names:
        return True

    print("Invalid input format. Please enter a valid option.")
    return False


def main():
    """
    Main function to execute the script.
    """
    try:
        create_tables()

        with Session() as outer_session:
            if is_database_empty(outer_session):
                print("\n   [Unique Situation Detected]")
                print("----------------------------------------")
                print("The SQLite database file did not exist or was empty.")
                print("----------------------------------------")

        txt_files_directory = os.path.join(base_dir, "..", "TwitterData", "TXT-ImpersonatorAccounts")
        txt_files = glob.glob(f"{txt_files_directory}/*.txt")
        if not txt_files:
            print("No protected channels found.")
            return

        print("\nSelect a protected channel to process:")
        for index, txt_file in enumerate(txt_files, start=1):
            # Corrected function name for extracting protected channel and ID
            protected_channel, _ = get_protected_channel_name_and_id_from_filename(os.path.basename(txt_file))
            print(f"{index}. {protected_channel}")

        user_choice = input("\nMake a choice by entering Number(s) or Name(s) comma separated. Or type ALL: ").strip()
        if validate_user_choice(user_choice, txt_files):
            process_user_choice(user_choice, txt_files)
        else:
            print("Invalid choice. Please try again.")

    except KeyboardInterrupt:
        print("Script interrupted by user.")
        logging.warning("Script interrupted by user.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        logging.error(f"An unexpected error occurred: {e}", exc_info=True)


if __name__ == "__main__":
    main()
