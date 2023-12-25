"""
    TODO: It seems to add the protected_channel_id for the last account in the menu selection to many database entries.
      The issue seems to be the fact that the last selected account (when more then 1 s selected) is added to some
       accounts. We dont know why it takes the last one when multiple accounts are selected, but it is tested to be
       always the last one of the multiple or all selection.
       UPDATE: IT HAPPENS FOR THE ONES WHERE THE ACCOUNT NAME CHANGED

"""
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, JSON, func
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base
from datetime import datetime, timezone, timedelta
from logging.handlers import RotatingFileHandler
from instance import config
from typing import List
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

    def update_username(self, new_username):
        """

        :param new_username:
        :return:
        """
        if self.username != new_username:
            # Concatenate previous_username with the current username if not empty
            self.previous_username = (self.previous_username + ',' if self.previous_username else '') + self.username
            self.username = new_username
            self.username_changed = True
            self.username_changed_date = datetime.now()

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


def create_new_account(user_data, session):
    """
    Creates a new account or updates an existing one in the database based on the given user data.

    :param user_data: The data for the user account.
    :param session: The database session.
    :return: None
    """
    # Query for an existing account by twitter_id or a case-insensitive match for username
    existing_account = session.query(TwitterAccount).filter(
        (TwitterAccount.twitter_id == user_data.get("id")) |
        (func.lower(TwitterAccount.username) == func.lower(user_data.get("username")))
    ).first()

    if existing_account:
        # Update the existing account with the new data
        for key, value in user_data.items():
            if hasattr(existing_account, key):
                setattr(existing_account, key, value)

        # Special handling for 'created_at' to ensure it's a datetime object
        if 'created_at' in user_data and user_data['created_at']:
            existing_account.created_at = datetime.strptime(user_data['created_at'], '%Y-%m-%dT%H:%M:%S.%fZ')

        # Handle the protected_channel_id if it's provided in user_data
        if 'protected_channel_id' in user_data:
            existing_account.protected_channel_id = user_data['protected_channel_id']

    else:
        # Create a new account if no existing account is found
        # Correctly map 'id' from user_data to 'twitter_id' in the new account
        user_data['twitter_id'] = user_data.pop('id', None)

        # Handle the protected_channel_id if it's not provided in user_data
        if 'protected_channel_id' not in user_data:
            user_data['protected_channel_id'] = None

        new_account = TwitterAccount(**user_data)
        session.add(new_account)
        logging.info(f"Added new account {user_data.get('username', 'unknown')}")

    # Commit the changes to the database
    if not commit_session(session):
        print("An error occurred while committing to the database.")


# Function to create headers for the API request
def create_headers(bearer_token):
    """

    :param bearer_token:
    :return:
    """
    headers = {"Authorization": f"Bearer {bearer_token}"}
    return headers


# Function to create the database tables
def create_tables():
    """

    :return:
    """
    Base.metadata.create_all(engine)


# Function to create the URL for the API request
def create_url(usernames):
    """

    :param usernames:
    :return:
    """
    usernames = ",".join(usernames)
    url = (f"{config.UPDATE_DATABASE_BASE_URL}?usernames={usernames}&user.fields=created_at,description,id,name,profile"
           f"_image_url,public_metrics,url,username,verified")
    return url


# Function to retrieve a TwitterAccount object by Twitter ID
def get_account_by_twitter_id(twitter_id, session):
    """

    :param twitter_id:
    :param session:
    :return:
    """
    return session.query(TwitterAccount).filter_by(twitter_id=twitter_id).first()


# Function to extract the protected channel name from the filename
def get_protected_channel_from_filename(filename):
    """

    :param filename:
    :return:
    """
    # Extract the channel name and ID from the new filename format 'Username(Twitter_ID).txt'
    base_name = os.path.basename(filename).replace(".txt", "")
    protected_channel, twitter_id = base_name.split("(")
    twitter_id = twitter_id.replace(")", "")
    return protected_channel, twitter_id


# Function to extract the username from the Twitter URL
def get_username_from_url(url):
    """

    :param url:
    :return:
    """
    return url.strip().split("/")[-1]


# Function to retrieve all impersonator accounts for a specific protected channel
def get_impersonators_for_protected_channel(session, protected_channel):
    """

    :param session:
    :param protected_channel:
    :return:
    """
    impersonators_query = session.query(TwitterAccount).filter_by(protected_channel=protected_channel)
    return impersonators_query.all()


# Function to check if the database is empty
def is_database_empty(session=None):
    """

    :param session:
    :return:
    """
    if not session:
        session = Session()
    return session.query(TwitterAccount).first() is None


def process_suspended_user(account, username, error, protected_channel, protected_channel_id, session):
    """

    :param account:
    :param username:
    :param error:
    :param protected_channel:
    :param protected_channel_id:
    :param session:
    :return:
    """
    if not hasattr(process_suspended_user, "header_printed"):
        process_suspended_user.header_printed = False

    if not process_suspended_user.header_printed:
        print(f"\n_____________________________________________\nProcess API response... for {protected_channel}:\n____"
              "_________________________________________")
        process_suspended_user.header_printed = True

    if account:
        logging.info(f"Existing account found for username: {username}, ID: {account.twitter_id}")
        if not account.suspended:
            account.mark_as_suspended()
            account.api_response = json.dumps(error, cls=SafeEncoder)  # Update the API response
            if account.protected_channel_id is None:
                account.protected_channel_id = protected_channel_id
            print(f"Updated and marked as suspended: {username}")
        else:
            logging.info(f"{username} is already marked as suspended.")
            # Update the API response even if already suspended
            account.api_response = json.dumps(error, cls=SafeEncoder)
    else:
        logging.info(f"No existing account found for username: {username}. Creating and marking as suspended.")
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
        print(f"Created and marked as suspended: {username}")

    # Commit the changes to the database
    if not commit_session(session):
        print("An error occurred while committing to the database.")


def process_username_change(account, new_username, session):
    """
    Processes a change in username for a given account.

    :param account: The existing account object.
    :param new_username: The new username.
    :param session: The database session.
    """
    if account.username != new_username:
        logging.info(f"Username change detected for {account.username} to {new_username}")

        # Check if there is an existing account with the new username
        existing_account_with_new_username = session.query(TwitterAccount).filter(
            TwitterAccount.username == new_username
        ).first()

        # If an existing account with the new username is found, mark it as unresolvable
        if existing_account_with_new_username:
            existing_account_with_new_username.unresolvable = True
            logging.info(
                f"Marked existing account with username {new_username} as unresolvable due to username conflict.")

        # Update the username of the current account
        account.update_username(new_username)

        if not commit_session(session):
            print("An error occurred while committing the username change to the database.")
    else:
        logging.info(f"No username change detected for {account.username}")


# Function to process a user that was not found
def process_not_found_user(username, error, protected_channel, protected_channel_id, session):
    """

    :param username:
    :param error:
    :param protected_channel:
    :param protected_channel_id:
    :param session:
    :return:
    """
    logging.info(f"Processing not found user: {username}")

    try:
        # Check for an existing account with the same username or in previous_username
        existing_account = session.query(TwitterAccount).filter(
            (func.lower(TwitterAccount.username) == func.lower(username)) |
            (TwitterAccount.previous_username.contains(username))
        ).first()

        if existing_account:
            logging.info(f"Existing account found for username: {username}, ID: {existing_account.twitter_id}")
            existing_account.unresolvable = True
            existing_account.api_response = error
            if existing_account.protected_channel_id is None:
                existing_account.protected_channel_id = protected_channel_id
        else:
            logging.info(f"No existing account found for username: {username}. Creating a new unresolvable account.")
            user_data = {
                'username': username,
                'protected_channel': protected_channel,
                'protected_channel_id': protected_channel_id,
                'api_response': error,
                'unresolvable': True
            }
            new_account = TwitterAccount(**user_data)
            session.add(new_account)

        if not commit_session(session):
            print(f"An error occurred while committing {username} to the database.")

    except Exception as e:
        logging.error(f"Failed to process {username}: {e}", exc_info=True)
        print(f"An error occurred while processing {username}.")


def process_active_user(account, user_data, protected_channel, protected_channel_id, session):
    """
    Processes an active user account.

    :param account: The existing account object.
    :param user_data: The user data retrieved from the API.
    :param protected_channel: The name of the protected channel.
    :param protected_channel_id: The ID of the protected channel.
    :param session: The database session.
    :return: None
    """
    user_data['protected_channel'] = protected_channel
    # Set protected_channel_id only if it's empty
    if account and account.protected_channel_id is None:
        user_data['protected_channel_id'] = protected_channel_id
    elif not account:
        user_data['protected_channel_id'] = protected_channel_id
    user_data['api_response'] = json.dumps(user_data, cls=SafeEncoder)

    if account:
        process_username_change(account, user_data['username'], session)
        account.update_api_response(user_data)
        print(f"{protected_channel} is impersonated by {user_data['username']}")
    else:
        create_new_account(user_data, session)

    if not commit_session(session):
        print("An error occurred while committing to the database.")


# Function to connect to the Twitter API endpoint with enhanced error handling and token rotation
def connect_to_endpoint(url, headers, max_retries=1):
    retries = 0
    while retries <= max_retries:
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            if response.status_code != 429:
                return response.json()

        except requests.HTTPError as e:
            masked_token = mask_token(headers['Authorization'])
            if e.response.status_code == 429:
                rate_limit_remaining = response.headers.get('x-rate-limit-remaining')
                rate_limit_reset = e.response.headers.get('x-rate-limit-reset')
                if rate_limit_reset:
                    reset_time_utc = datetime.fromtimestamp(int(rate_limit_reset), timezone.utc)
                    reset_time_gmt1 = reset_time_utc + timedelta(hours=1)  # Adjusting for GMT+1
                    now = datetime.now(timezone.utc)
                    time_diff = reset_time_utc - now
                    hours = time_diff.seconds // 3600
                    minutes = (time_diff.seconds // 60) % 60
                    seconds = time_diff.seconds % 60
                    time_diff_str = f"{hours}h:{minutes}m:{seconds}s"

                    print(f"\n____________________________________________________________________________\n"
                          f"Generating API request... Failed\n"
                          f"____________________________________________________________________________\n"
                          f"Rate-Limit hit for Token: {masked_token}\n"
                          f"Rate Limit Remaining: {rate_limit_remaining}\n"
                          f"Rate Limit Resets In: {time_diff_str}\n"
                          f"Rate Limit Resets At: {reset_time_gmt1.strftime('%Y-%m-%d %H:%M:%S GMT+1')}\nSwitching Toke"
                          f"n...")

                    token_manager.mark_token_as_rate_limited(token_manager.get_current_token())
                    if token_manager.all_tokens_rate_limited():
                        sleep_time = max(time_diff.total_seconds() + 5, 0)  # Add extra 5 seconds
                        sleep_hours = int(sleep_time // 3600)
                        sleep_minutes = int((sleep_time // 60) % 60)
                        sleep_seconds = int(sleep_time % 60)
                        sleep_time_str = f"{sleep_hours}h:{sleep_minutes}m:{sleep_seconds}s"

                        print(f"\n____________________________________________________________________________\nAll tok"
                              f"ens are rate-limited. Sleeping for: {sleep_time_str}\n_________________________________"
                              f"___________________________________________\nSleeping until: "
                              f"{reset_time_gmt1.strftime('%Y-%m-%d %H:%M:%S GMT+1')}")
                        time.sleep(sleep_time)
                        token_manager.reset_rate_limited_tokens()  # Reset rate-limited tokens after sleeping
                        continue  # Continue the loop to retry the request
                    else:
                        token_manager.rotate_token()
                        headers['Authorization'] = f'Bearer {token_manager.get_current_token()}'
                        continue  # Continue the loop to retry with the next token
                else:
                    print("Rate limit reset time is unknown. Exiting.")
                    sys.exit(0)

            else:
                error_message = f"HTTP error occurred for URL {url} with token {masked_token}: {e}"
                logging.error(error_message, exc_info=True)
                print(error_message)
                raise

        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}", exc_info=True)
            raise

        if retries > max_retries:
            logging.error("Max retries reached for the API request.")
            raise Exception("Max retries reached for the API request.")

    return None


# Funtion to handle API requests with a retry mechanism
def make_api_request(url, headers, retries=3, delay=1):
    """

    :param url:
    :param headers:
    :param retries:
    :param delay:
    :return:
    """
    for _ in range(retries):
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            logging.error(f"HTTP error occurred: {e}")
            if e.response.status_code == 429:  # Rate limit exceeded
                retry_after = int(e.response.headers.get('Retry-After', delay))  # Get Retry-After header value
                logging.warning(f"Rate limit exceeded. Retrying in {retry_after} seconds...")
                time.sleep(retry_after)
                continue
            break  # For other HTTP errors, break the loop and handle the error outside
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            break  # For other errors, break the loop and handle the error outside
    return None  # Return None if the request fails


def process_api_response(response, session, protected_channel, protected_channel_id, first_call=True):
    """

    :param response:
    :param session:
    :param protected_channel:
    :param protected_channel_id:
    :param first_call:
    :return:
    """
    if not response:
        logging.error("No response received from the API.")
        return [], [], []
    logging.info(f"Raw API response: {response}")

    suspended_accounts = []
    active_impersonators = []
    not_found_users = []

    if first_call:
        print(f"\n_____________________________________________\nProcess API response... "
              f"for {protected_channel}:\n_____________________________________________")

    if 'errors' in response:
        for error in response['errors']:
            detail = error.get('detail', 'No detail provided')
            logging.error(f"API Error: {detail}")

            username = error.get('value')

            # Perform a case-insensitive search for the existing account
            account = session.query(TwitterAccount).filter(
                func.lower(TwitterAccount.username) == func.lower(username)).first()

            if 'User has been suspended' in detail:
                if account:
                    # Update the existing account's status to "suspended"
                    account.suspended = True
                    session.commit()
                    # Format the username to be left-justified within 18 characters
                    formatted_username = username.ljust(18)
                    suspended_accounts.append(f"Status Suspended: {formatted_username} (ID:{account.twitter_id})")
                    print(f"Status Suspended: {formatted_username} (ID:{account.twitter_id})")
                continue

            if 'Could not find user with usernames' in detail or 'not be found' in detail.lower():
                if account and account.twitter_id:
                    url = f"https://api.twitter.com/2/users/{account.twitter_id}"
                    headers = create_headers(token_manager.get_current_token())
                    try:
                        new_user_data = connect_to_endpoint(url, headers)
                        new_username = new_user_data['data']['username']
                        process_username_change(account, new_username, session)
                        account.update_api_response(new_user_data['data'])
                    except Exception as e:
                        logging.error(f"Could not update username: {e}")
                        # Format the username to be left-justified within 18 characters
                        formatted_username = username.ljust(18)
                        print(f"Account Inactive: {formatted_username} (ID:{account.twitter_id})")
                        account.api_response = error
                        account.unresolvable = True
                        if not commit_session(session):
                            print("An error occurred while committing to the database.")

                else:
                    process_not_found_user(username, error, protected_channel, protected_channel_id, session)
                continue

    if 'data' in response:
        for user_data in response['data']:
            # Ensure protected_channel_id is a single value, not a list
            if isinstance(protected_channel_id, list):
                logging.error(f"Invalid protected_channel_id type (list) "
                              f"for {protected_channel}. Expected a single value.")
                continue  # Skip this iteration
            user_data['protected_channel'] = protected_channel
            user_data['api_response'] = json.dumps(user_data, cls=SafeEncoder)

            # Perform a case-insensitive search for the existing account
            account = session.query(TwitterAccount).filter(
                func.lower(TwitterAccount.username) == func.lower(user_data['username'])).first()

            if account:
                if not account.suspended:
                    # Format both usernames to be left-justified within 18 characters
                    formatted_old_username = account.username.ljust(18)
                    formatted_new_username = user_data['username'].ljust(18)

                    if account.username != user_data['username']:
                        print(
                            f"\n_____________________________________________\nProcessing API response... for "
                            f"{protected_channel}\n_____________________________________________\n"
                            f"{formatted_old_username} changed username to {formatted_new_username}")
                        account.update_username(user_data['username'])

                account.update_api_response(user_data)
                session.commit()

                # Format the username in the active impersonators list
                formatted_impersonator_username = user_data['username'].ljust(18)
                active_impersonators.append(f"{protected_channel} is impersonated by: "
                                            f"{formatted_impersonator_username} (ID:{account.twitter_id})")

            else:
                create_new_account(user_data, session)
                active_impersonators.append(
                    f"Added new impersonator for {protected_channel}: {user_data['username']}")
                session.commit()

    return suspended_accounts, active_impersonators, not_found_users


def process_unresolvable_user(session, reactivated_usernames, usernames_chunk):
    """
    Processes unresolvable users by checking if they have become resolvable.

    :param session: The database session.
    :param reactivated_usernames: List to store usernames that have become resolvable.
    :param usernames_chunk: Chunk of usernames to process.
    :return: None
    """
    # Create URL for the chunk of usernames
    url = create_url(usernames_chunk)
    headers = create_headers(token_manager.get_current_token())
    response_data = connect_to_endpoint(url, headers)

    if response_data and 'data' in response_data:
        for new_data in response_data['data']:
            twitter_id = new_data.get("id")
            username = new_data.get("username")

            # Find an existing account by Twitter ID or username
            account = session.query(TwitterAccount).filter(
                (TwitterAccount.twitter_id == twitter_id) |
                (func.lower(TwitterAccount.username) == func.lower(username))
            ).first()

            if account:
                # Update the existing account with new data from Twitter API
                account.twitter_id = twitter_id
                account.username = new_data.get("username")
                account.name = new_data.get("name")
                account.description = new_data.get("description")
                account.profile_image_url = new_data.get("profile_image_url")
                account.url = new_data.get("url")
                account.followers_count = new_data.get("public_metrics", {}).get("followers_count")
                account.following_count = new_data.get("public_metrics", {}).get("following_count")
                account.tweet_count = new_data.get("public_metrics", {}).get("tweet_count")
                account.listed_count = new_data.get("public_metrics", {}).get("listed_count")
                account.created_at = datetime.strptime(
                    new_data.get("created_at"), '%Y-%m-%dT%H:%M:%S.%fZ') if new_data.get("created_at") else None
                account.unresolvable = False
                account.api_response = json.dumps(new_data, cls=SafeEncoder)
                account.api_response_updated_at = datetime.now()
                # No update to protected_channel_id
                logging.info(f"Updated existing account with new data for username {username}")
            else:
                # Create a new account if no existing record is found
                new_account_data = {key: new_data[key] for key in new_data if key != 'id'}
                new_account_data['twitter_id'] = twitter_id
                new_account_data['unresolvable'] = False
                # No inclusion of protected_channel_id
                new_account = TwitterAccount(**new_account_data)
                session.add(new_account)
                logging.info(f"Created new account for username {username}")

            reactivated_usernames.append(new_data.get("username"))
            logging.info(f"Account {new_data.get('username')} is now resolvable and updated.")

        if not commit_session(session):
            print("An error occurred while committing to the database.")
    else:
        for username in usernames_chunk:
            logging.info(f"Account {username} is still unresolvable.")


# Function to process the user's choice of the protected channel
def process_user_choice(choice, txt_files):
    """

    :param choice:
    :param txt_files:
    :return:
    """
    if not choice or not choice.strip():
        print("Invalid input. Please enter a number or name corresponding to the protected channels,"
              " or type 'ALL' to select all channels.")
        return

    # Initialize the list for collecting unresolvable usernames across all channels
    unresolvable_usernames = []
    reactivated_usernames = []  # List to store reactivated usernames

    def process_choice(inner_choice):
        """

        :param inner_choice:
        :return:
        """
        all_suspended_accounts = []
        all_active_impersonators = []
        all_not_found_users = []

        try:
            choice_number = int(inner_choice)
            selected_file = txt_files[choice_number - 1]
            local_protected_channel, local_protected_channel_id = get_protected_channel_from_filename(selected_file)
            with open(selected_file, 'r') as chosen_file:
                urls = [line.strip() for line in chosen_file if line.strip()]

            usernames = [get_username_from_url(url).lower() for url in urls if url.strip()]
            if not usernames:
                logging.error(f"The usernames list is empty for file {selected_file}.")
                return

            errors, seen_usernames, duplicate_usernames = [], set(), set()
            for uname in usernames:
                if uname in seen_usernames:
                    duplicate_usernames.add(uname)
                seen_usernames.add(uname)

            if duplicate_usernames:
                duplicate_usernames = list(duplicate_usernames)
                formatted_usernames = ', '.join(duplicate_usernames[:2]) + ',\n' + ',\n'.join(
                    [', '.join(duplicate_usernames[i:i + 5]) for i in range(2, len(duplicate_usernames), 5)])
                errors.append(f"Error: The following usernames are duplicated: {formatted_usernames}")

            invalid_usernames = [uname for uname in usernames if len(uname) > 15]
            if invalid_usernames:
                formatted_usernames = ', '.join(invalid_usernames[:2]) + ',\n' + ',\n'.join(
                    [', '.join(invalid_usernames[i:i + 5]) for i in range(2, len(invalid_usernames), 5)])
                errors.append(f"Error: The following usernames are too long: {formatted_usernames}")

            if errors:
                print(f"\n____________________________________________________________________________\nProcessing TXT "
                      f"content... for {local_protected_channel}\n_____________________________________________________"
                      f"_______________________\nError(s) found. Correct the Active-{local_protected_channel}.txt file "
                      f"and retry.")
                for error in errors:
                    print(error)
                return
            with Session() as db_session:
                # Now use 'db_session' in place of 'session' inside this block
                unresolvables = db_session.query(TwitterAccount).filter_by(
                    unresolvable=True, protected_channel=local_protected_channel).all()
                for account in unresolvables:
                    # Process usernames
                    unresolvable_usernames.append(account.username)

                    # Existing logic to process usernames
                chunks = list(chunked_usernames(usernames))
                for chunk in chunks:
                    url = create_url(chunk)
                    headers = create_headers(token_manager.get_current_token())
                    response_data = connect_to_endpoint(url, headers)

                    if response_data is not None:
                        # Update 'session' to 'db_session' in the function call
                        suspended_accounts, active_impersonators, not_found_users = process_api_response(
                            response_data, db_session, local_protected_channel, local_protected_channel_id)
                    else:
                        logging.error("Response data is None, skipping...")

                    try:
                        all_suspended_accounts.extend(suspended_accounts)
                        all_active_impersonators.extend(active_impersonators)
                        all_not_found_users.extend(not_found_users)
                    except UnboundLocalError:
                        print(f"\n____________________________________________________________________________\nProcess"
                              f"ing API request... for {local_protected_channel}\n_____________________________________"
                              f"_______________________________________\nError: The request failed because both tokens "
                              f"are rate-limited.\nError: Could not process information for {local_protected_channel}."
                              f"\nInformation update Failed.\nPlease try again later...")
                        logging.warning("The request failed because both tokens are rate-limited.")
                        return
                time.sleep(0)  # To avoid hitting rate limits

                # Output processed information
                print(f"\n_____________________________________________\nAll information processed for "
                      f"{local_protected_channel}:\n_____________________________________________")
                if all_active_impersonators:
                    print("\n".join(all_active_impersonators))
                if all_not_found_users:
                    print("\n".join(all_not_found_users))

                # Process unresolvable usernames at the end
                for process_usernames_chunk in chunked_usernames(unresolvable_usernames, 100):
                    # Call process_unresolvable_user without local_protected_channel_id and local_protected_channel
                    process_unresolvable_user(db_session, reactivated_usernames, process_usernames_chunk)

        except ValueError as e:
            print(f"ValueError occurred: {e}\nInvalid input. Please enter a number.")
        except IndexError:
            print("Invalid selection. Please enter a number corresponding to the available options.")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}", exc_info=True)
            traceback.print_exc()

    # Process each selected channel
    if choice.upper() == "ALL":
        for txt_file in txt_files:
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
                print(f"Invalid name: {choice}")

    # Process unresolvable usernames at the end
    reactivated_usernames = []
    with Session() as session:
        for filename in txt_files:
            with open(filename, 'r') as file:
                file_usernames = [get_username_from_url(line.strip()) for line in file if line.strip()]
                file_unresolvables = [uname for uname in file_usernames if uname.lower() in unresolvable_usernames]
                for usernames_chunk in chunked_usernames(file_unresolvables, 100):
                    # Call process_unresolvable_user without protected_channel_id and protected_channel
                    process_unresolvable_user(session, reactivated_usernames, usernames_chunk)

    # Output for reactivated accounts
    if reactivated_usernames:
        print("\n_____________________________________________")
        print("Reactivated impersonators across all channels")
        print("_____________________________________________")
        for username in reactivated_usernames:
            print(f"Impersonator reactivated: {username}")


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

    :return:
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
        # Update the pattern to match the new filename format
        txt_files = glob.glob(f"{txt_files_directory}/*.txt")
        if not txt_files:
            print("No protected channels found.")
            return

        print("\nSelect a protected channel to process:")
        for index, txt_file in enumerate(txt_files, start=1):
            # Extract the protected channel and Twitter ID from the filename
            protected_channel, _ = get_protected_channel_from_filename(os.path.basename(txt_file))
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
