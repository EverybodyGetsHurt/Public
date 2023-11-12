# TESTING TODO:
# OKIf a known account (with previous information like ID) changes username, the script notices that the name changed if
# the old name couldnt be found anymore, but uses the twitter_id which is unchangeable and forever, to get the new name.
#
# OKIf an account which was not being found for 2 runs of the script, it gets an unresolvable value. At the end of
# the script the code will gather all the selected protected_channels from the menu and make chunks of 100
# unresolvable user names, and checks if any of the accounts became active again.
#
# OKIf an account is Suspended it updated the value and displays it as a Suspended account.
#
# OKIf a username is changed for a second and more times after, it must keep the old names in a comma separated list.
#
# OKIf one of the 2 developer tokens hit the twitter rate limit it automatically switches to the second token, until the
# token gets rate limit, then it switches back to the first, if the first token is still rate limited, we currently get
# an error response saying both tokens are rate limited. TODO: Catch the error and give a custom terminal print.
#
#
#
#
#

# Import necessary libraries and modules
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, JSON, func
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base
from logging.handlers import RotatingFileHandler
from datetime import datetime
from instance import config
from typing import List
import traceback
import requests
import logging
import json
import glob
import time
import os

# Logging setup
log_filename = os.path.join("TwitterData", "SQL-ImpersonatorAccounts", "ImpersonatorAccounts.log")
if not os.path.exists(os.path.dirname(log_filename)):
    os.makedirs(os.path.dirname(log_filename))
logger = logging.getLogger()  # Creating a custom logger
logger.setLevel(logging.DEBUG)  # You can set this to the lowest level of logging messages you want to handle
handler = RotatingFileHandler(log_filename, maxBytes=int(49.9 * 1024 * 1024), backupCount=1, encoding='utf-8')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
handler.setFormatter(formatter)  # Add formatter to handler
logger.addHandler(handler)  # Add handler to logger
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

# Directory, database and SQLAlchemy setup
base_dir = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(base_dir, "TwitterData", "SQL-ImpersonatorAccounts", "ImpersonatorAccounts.sqlite")
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
Base = declarative_base()
engine = create_engine(DATABASE_URL)
Session = scoped_session(sessionmaker(bind=engine))

# API setup and tokens
BASE_URL = "https://api.twitter.com/2/users/by"
main_token = config.BEARER_TOKEN
backup_token = config.BEARER_TOKEN_V2
tokens_list = [main_token, backup_token]


# Token Manager for handling the token rotation
class TokenManager:
    def __init__(self, tokens):
        self.tokens_list = tokens
        self.current_token_index = 0
        self.rate_limited_tokens = set()

    def get_current_token(self):
        return self.tokens_list[self.current_token_index]

    def rotate_token(self):
        self.current_token_index = (self.current_token_index + 1) % len(self.tokens_list)
        masked_token = mask_token(f'Bearer {self.tokens_list[self.current_token_index]}')
        logging.debug(f"Rotated to token {self.current_token_index}: {masked_token}")

    def mark_token_as_rate_limited(self, token):
        self.rate_limited_tokens.add(token)
        masked_token = mask_token(f'Bearer {token}')
        logging.debug(f"Marked token as rate-limited: {masked_token}")

    def all_tokens_rate_limited(self):
        all_rate_limited = len(self.rate_limited_tokens) == len(self.tokens_list)
        logging.debug(f"All tokens rate-limited: {all_rate_limited}")
        return all_rate_limited

    def reset_rate_limited_tokens(self):
        self.rate_limited_tokens.clear()


token_manager = TokenManager(tokens_list)


def mask_token(authorization_header):
    token = authorization_header.split(' ')[1]  # Extract the actual token from the header
    masked_token = '*' * 18 + token[-5:]  # Mask all characters of the token except for the last 5
    return masked_token


# Custom JSON encoder to handle non-serializable objects
class SafeEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)


# Class for the SQL-Alchemy database schema for ImpersonatorAccounts
class TwitterAccount(Base):
    __tablename__ = "impersonator_account"
    id = Column(Integer, primary_key=True, index=True)
    twitter_id = Column(String, unique=True)
    protected_channel = Column(String, index=True)
    username = Column(String, nullable=False, unique=True)
    name = Column(String)
    created_at = Column(DateTime)
    description = Column(String)
    followers_count = Column(Integer)
    following_count = Column(Integer)
    tweet_count = Column(Integer)
    listed_count = Column(Integer)
    suspended = Column(Boolean, default=False)
    suspended_date = Column(DateTime)
    username_changed = Column(Integer, default=0)
    previous_username = Column(String)
    username_changed_date = Column(DateTime)
    unresolvable = Column(Boolean, default=False)
    api_response = Column(JSON)
    api_response_updated_at = Column(DateTime)
    previous_api_response = Column(JSON)
    previous_api_response_updated_at = Column(DateTime)
    url = Column(String)
    profile_image_url = Column(String)

    def __init__(self, **kwargs):
        self.twitter_id = kwargs.get("id")
        self.protected_channel = kwargs.get("protected_channel")
        self.username = kwargs.get("username")
        self.name = kwargs.get("name")
        self.created_at = datetime.strptime(
            kwargs.get("created_at"), '%Y-%m-%dT%H:%M:%S.%fZ') if kwargs.get("created_at") else None
        self.description = kwargs.get("description")
        self.followers_count = kwargs.get("public_metrics", {}).get("followers_count")
        self.following_count = kwargs.get("public_metrics", {}).get("following_count")
        self.tweet_count = kwargs.get("public_metrics", {}).get("tweet_count")
        self.listed_count = kwargs.get("public_metrics", {}).get("listed_count")
        self.suspended = False
        self.suspended_date = None
        self.username_changed = False
        self.username_changed_to = None
        self.username_changed_date = None
        self.unresolvable = False
        self.api_response = kwargs.get("api_response")
        self.api_response_updated_at = datetime.now()  # Set the current time
        self.url = kwargs.get("url")
        self.profile_image_url = kwargs.get("profile_image_url")

    def mark_as_suspended(self, date=None):
        if not self.suspended:
            logging.info(f"Marking {self.username} as suspended.")
            self.suspended = True
            self.suspended_date = date or datetime.now()
            logging.info(f"Marked {self.username} as suspended at {self.suspended_date}.")
        else:
            logging.info(f"{self.username} is already marked as suspended.")

    def update_username(self, new_username):
        print(f"Updating username from {self.username} to {new_username}")
        if self.previous_username:
            self.previous_username += f",{self.username}"  # Append the old username with a comma
        else:
            self.previous_username = self.username  # If it's the first change, just assign the old username
        self.username = new_username
        self.username_changed += 1
        self.username_changed_date = datetime.now()

    def update_api_response(self, new_response):
        # print(f"Updating API response")  # Debug print
        self.previous_api_response = self.api_response
        self.previous_api_response_updated_at = self.api_response_updated_at
        self.api_response = json.dumps(new_response, cls=SafeEncoder)
        self.api_response_updated_at = datetime.now()

    def __repr__(self):
        return f"<TwitterAccount(username={self.username}, twitter_id={self.twitter_id}, suspended={self.suspended})>"


# Function to split the list of usernames into chunks for batch processing
def chunked_usernames(usernames: List[str], chunk_size: int = 100):
    for i in range(0, len(usernames), chunk_size):
        yield usernames[i:i + chunk_size]


# Function made to reduce repetitive code
def commit_session(session):
    try:
        session.commit()
        logging.info("Database commit successful.")
        return True
    except Exception as e:
        session.rollback()
        logging.error(f"Database commit failed: {e}", exc_info=True)
        return False


# Function to create a new TwitterAccount object and add it to the session
def create_new_account(user_data, session):
    # Query for an existing account by twitter_id or a case-insensitive match for username
    existing_account = session.query(TwitterAccount).filter(
        (TwitterAccount.twitter_id == user_data["id"]) |
        (func.lower(TwitterAccount.username) == func.lower(user_data["username"]))
    ).first()

    if existing_account:
        # Update the existing account with the new data
        for key, value in user_data.items():
            if key == 'id':
                # Map 'id' from user_data to 'twitter_id' in TwitterAccount
                setattr(existing_account, 'twitter_id', value)
            elif key != 'created_at':
                # Update other fields except 'created_at' and primary key 'id'
                setattr(existing_account, key, value)

        # Special handling for 'created_at' to ensure it's a datetime object
        if 'created_at' in user_data and user_data['created_at']:
            existing_account.created_at = datetime.strptime(user_data['created_at'], '%Y-%m-%dT%H:%M:%S.%fZ')

    else:
        # Create a new account if no existing account is found
        # Correctly map 'id' from user_data to 'twitter_id' in the new account
        user_data['twitter_id'] = user_data.pop('id')
        new_account = TwitterAccount(**user_data)
        session.add(new_account)
        logging.info(f"Added new account {user_data['username']}")

    # Commit the changes to the database
    if not commit_session(session):
        print("An error occurred while committing to the database.")


# Function to create headers for the API request
def create_headers(bearer_token):
    headers = {"Authorization": f"Bearer {bearer_token}"}
    return headers


# Function to create the database tables
def create_tables():
    Base.metadata.create_all(engine)


# Function to create the URL for the API request
def create_url(usernames):
    usernames = ",".join(usernames)
    url = (f"{BASE_URL}?usernames={usernames}&user.fields=created_at,description,id,name,profile_image_url,"
           f"public_metrics,url,username,verified")
    return url


# Function to retrieve a TwitterAccount object by Twitter ID
def get_account_by_twitter_id(twitter_id, session):
    return session.query(TwitterAccount).filter_by(twitter_id=twitter_id).first()


# Function to extract the protected channel name from the filename
def get_protected_channel_from_filename(filename):
    protected_channel = filename.replace("Active-", "").replace(".txt", "")
    return protected_channel


# Function to extract the username from the Twitter URL
def get_username_from_url(url):
    return url.strip().split("/")[-1]


# Function to retrieve all impersonator accounts for a specific protected channel
def get_impersonators_for_protected_channel(session, protected_channel):
    impersonators_query = session.query(TwitterAccount).filter_by(protected_channel=protected_channel)
    return impersonators_query.all()


# Function to check if the database is empty
def is_database_empty(session=None):
    if not session:
        session = Session()
    return session.query(TwitterAccount).first() is None


# Function to process a suspended user
def process_suspended_user(account, username, error, protected_channel, session):
    if account:
        account.mark_as_suspended()
        account.api_response = error
        print(f"Status Suspended: {username}")

        if not commit_session(session):
            print("An error occurred while committing to the database.")

    else:
        user_data = {
            'username': username,
            'protected_channel': protected_channel,
            'api_response': error
        }
        new_account = TwitterAccount(**user_data)
        new_account.mark_as_suspended()
        session.add(new_account)

        if not commit_session(session):
            print("An error occurred while committing to the database.")


# Function to process a user that was not found
def process_not_found_user(username, error, protected_channel, session):
    logging.info(f"Processing not found user: {username}")

    try:
        user_data = {
            'username': username,
            'protected_channel': protected_channel,
            'api_response': error,
            'unresolvable': True
        }

        existing_account = session.query(TwitterAccount).filter_by(username=username).first()

        if existing_account:
            # Update existing account
            for key, value in user_data.items():
                setattr(existing_account, key, value)
            logging.info(f"Updated {username} in the database as not found.")
        else:
            new_account = TwitterAccount(**user_data)
            session.add(new_account)
            logging.info(f"Added {username} to the database as not found.")

        if not commit_session(session):
            print(f"An error occurred while committing {username} to the database.")

    except Exception as e:
        logging.error(f"Failed to process {username}: {e}", exc_info=True)
        print(f"An error occurred while processing {username}.")


# Function to process an active user
def process_active_user(account, user_data, protected_channel, session):
    user_data['protected_channel'] = protected_channel
    user_data['api_response'] = json.dumps(user_data, cls=SafeEncoder)

    if account:
        if not account.suspended and account.username != user_data['username']:

            print(f"{account.username} changed username to {user_data['username']}")

            account.username = user_data['username']

        account.update_api_response(user_data)
    else:
        create_new_account(user_data, session)

    print(f"{protected_channel} is impersonated by {user_data['username']}")
    if not commit_session(session):
        print("An error occurred while committing to the database.")


# Function to connect to the Twitter API endpoint with enhanced error handling and token rotation
def connect_to_endpoint(url, headers, max_retries=1):
    retries = 0
    masked_token = None  # Initialize masked_token before the try block
    while retries <= max_retries:
        try:
            masked_token = mask_token(headers['Authorization'])
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
                    raise Exception("All tokens are rate-limited. Halting operation.")

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

        except requests.ConnectionError as e:
            logging.error(f"Connection error occurred: {e}", exc_info=True)
            raise

        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}", exc_info=True)
            raise

        if retries > max_retries:
            logging.error("Max retries reached for the API request.")
            raise Exception("Max retries reached for the API request.")


# Funtion to handle API requests with a retry mechanism
def make_api_request(url, headers, retries=3, delay=1):
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


# Function to process the API response, handling various scenarios like active/suspended/not-found accounts.
def process_api_response(response, session, protected_channel):
    if not response:
        logging.error("No response received from the API.")
        return
    logging.info(f"Raw API response: {response}")
    print(f"\n_____________________________________________\nProcessing API response... for {protected_channel}\n"
          f"_____________________________________________")
    suspended_accounts = []
    active_impersonators = []
    not_found_users = []
    if 'errors' in response:
        for error in response['errors']:
            detail = error.get('detail', 'No detail provided')
            logging.error(f"API Error: {detail}")

            username = error.get('value')
            account = session.query(TwitterAccount).filter_by(username=username).first()
            if 'has been suspended' in detail:
                process_suspended_user(account, username, error, protected_channel, session)
                continue

            if 'Could not find user with usernames' in detail or 'not be found' in detail.lower():
                if account and account.twitter_id:
                    url = f"https://api.twitter.com/2/users/{account.twitter_id}"
                    headers = create_headers(token_manager.get_current_token())
                    try:
                        new_user_data = connect_to_endpoint(url, headers)
                        new_username = new_user_data['data']['username']
                        print(f"Username {username} not found. Updated to {new_username} using Twitter ID.")
                        account.update_username(new_username)
                        account.update_api_response(new_user_data['data'])
                        if not commit_session(session):
                            print("An error occurred while committing to the database.")

                    except Exception as e:
                        logging.error(f"Could not update username: {e}")
                        print(f"Both username {username} and Twitter ID {account.twitter_id} could not be resolved.")
                        account.api_response = error
                        account.unresolvable = True
                        if not commit_session(session):
                            print("An error occurred while committing to the database.")

                else:
                    process_not_found_user(username, error, protected_channel, session)
                continue

    if 'data' in response:
        for user_data in response['data']:
            user_data['protected_channel'] = protected_channel
            user_data['api_response'] = json.dumps(user_data, cls=SafeEncoder)
            account = session.query(TwitterAccount).filter_by(twitter_id=user_data['id']).first()

            if account:
                if not account.suspended:
                    if account.username != user_data['username']:
                        print(
                            f"\n_____________________________________________\nProcessing API response... for "
                            f"{protected_channel}\n_____________________________________________\n{account.username} ch"
                            f"anged username to {user_data['username']}")
                        account.update_username(user_data['username'])
                account.update_api_response(user_data)
                if not commit_session(session):
                    print("An error occurred while committing to the database.")
                active_impersonators.append(f"{protected_channel} is impersonated by: {user_data['username']}")
            else:
                create_new_account(user_data, session)
                active_impersonators.append(
                    f"Added new impersonator for {protected_channel}: {user_data['username']}")
                if not commit_session(session):
                    print("An error occurred while committing to the database.")

    return suspended_accounts, active_impersonators, not_found_users


def process_unresolvable_user(session, reactivated_usernames, usernames_chunk):
    for username in usernames_chunk:
        url = create_url([username])
        headers = create_headers(token_manager.get_current_token())
        response_data = connect_to_endpoint(url, headers)

        if response_data and 'data' in response_data:
            new_data = response_data['data'][0]
            twitter_id = new_data.get("id")

            # Find an existing account by Twitter ID or username
            account = session.query(TwitterAccount).filter(
                (TwitterAccount.twitter_id == twitter_id) |
                (func.lower(TwitterAccount.username) == func.lower(username))
            ).first()

            if account:
                # Update existing account with new data from Twitter API
                account.twitter_id = twitter_id  # Ensure only the twitter_id is updated, not the id
                # Update other fields as necessary but not the id
                account.username = new_data.get("username")
                account.name = new_data.get("name")
                account.description = new_data.get("description")
                account.profile_image_url = new_data.get("profile_image_url")
                account.url = new_data.get("url")
                account.followers_count = new_data.get("public_metrics", {}).get("followers_count")
                account.following_count = new_data.get("public_metrics", {}).get("following_count")
                account.tweet_count = new_data.get("public_metrics", {}).get("tweet_count")
                account.listed_count = new_data.get("public_metrics", {}).get("listed_count")
                account.created_at = datetime.strptime(new_data.get("created_at"), '%Y-%m-%dT%H:%M:%S.%fZ') if new_data.get("created_at") else None
                account.unresolvable = False
                account.api_response = json.dumps(new_data, cls=SafeEncoder)
                account.api_response_updated_at = datetime.now()
                logging.info(f"Updated existing account with new data for username {username}")
            else:
                # Create a new account if no existing record is found
                new_account_data = {key: new_data[key] for key in new_data if key != 'id'}
                new_account_data['twitter_id'] = twitter_id
                new_account_data['unresolvable'] = False
                new_account = TwitterAccount(**new_account_data)
                session.add(new_account)
                logging.info(f"Created new account for username {username}")

            reactivated_usernames.append(new_data.get("username"))
            logging.info(f"Account {new_data.get('username')} is now resolvable and updated.")

            if not commit_session(session):
                print("An error occurred while committing to the database.")
        else:
            logging.info(f"Account {username} is still unresolvable.")


# Function to process the user's choice of protected channel
def process_user_choice(choice, txt_files):
    if not choice or not choice.strip():
        print("Invalid input. Please enter a number or name corresponding to the protected channels,"
              " or type 'ALL' to select all channels.")
        return

    # Initialize the list for collecting unresolvable usernames across all channels
    unresolvable_usernames = []

    def process_choice(inner_choice):
        all_suspended_accounts = []
        all_active_impersonators = []
        all_not_found_users = []

        try:
            choice_number = int(inner_choice)
            selected_file = txt_files[choice_number - 1]
            protected_channel = os.path.basename(selected_file).replace('Active-', '').replace('.txt', '')
            with open(selected_file, 'r') as file:
                urls = [line.strip() for line in file if line.strip()]

            usernames = [get_username_from_url(url).lower() for url in urls if url.strip()]
            if not usernames:
                logging.error(f"The usernames list is empty for file {selected_file}.")
                return

            errors, seen_usernames, duplicate_usernames = [], set(), set()
            for username in usernames:
                if username in seen_usernames:
                    duplicate_usernames.add(username)
                seen_usernames.add(username)

            if duplicate_usernames:
                duplicate_usernames = list(duplicate_usernames)
                formatted_usernames = ', '.join(duplicate_usernames[:2]) + ',\n' + ',\n'.join(
                    [', '.join(duplicate_usernames[i:i + 5]) for i in range(2, len(duplicate_usernames), 5)])
                errors.append(f"Error: The following usernames are duplicated: {formatted_usernames}")

            invalid_usernames = [username for username in usernames if len(username) > 15]
            if invalid_usernames:
                formatted_usernames = ', '.join(invalid_usernames[:2]) + ',\n' + ',\n'.join(
                    [', '.join(invalid_usernames[i:i + 5]) for i in range(2, len(invalid_usernames), 5)])
                errors.append(f"Error: The following usernames are too long: {formatted_usernames}")

            if errors:
                print(f"\n____________________________________________________________________________\nProcessing TXT "
                      f"content... for {protected_channel}\n__________________________________________________________"
                      f"__________________\nError(s) found. Correct the Active-{protected_channel}.txt file and retry.")
                for error in errors:
                    print(error)
                return

            with (Session() as session):
                # Collect unresolvable usernames
                unresolvables = session.query(TwitterAccount).filter_by(
                    unresolvable=True, protected_channel=protected_channel).all()
                for account in unresolvables:
                    unresolvable_usernames.append(account.username)

                # Existing logic to process usernames
                chunks = list(chunked_usernames(usernames))
                for chunk in chunks:
                    url = create_url(chunk)
                    headers = create_headers(token_manager.get_current_token())
                    response_data = connect_to_endpoint(url, headers)

                    if response_data is not None:
                        suspended_accounts, active_impersonators, not_found_users = process_api_response(
                            response_data, session, protected_channel)
                    else:
                        logging.error("Response data is None, skipping...")

                    try:
                        all_suspended_accounts.extend(suspended_accounts)
                        all_active_impersonators.extend(active_impersonators)
                        all_not_found_users.extend(not_found_users)
                    except UnboundLocalError:
                        print(f"\n____________________________________________________________________________\nProcess"
                              f"ing API request... for {protected_channel}\n___________________________________________"
                              f"_________________________________\nError: The request failed because both tokens are ra"
                              f"te-limited.\nError: Could not process information for {protected_channel}.\nInformation"
                              f" update Failed.\nPlease try again later...")
                        logging.warning("The request failed because both tokens are rate-limited.")
                        return

                    time.sleep(1)

                print(f"\n_____________________________________________\nAll information processed for "
                      f"{protected_channel}:\n_____________________________________________")
                if all_suspended_accounts:
                    print("\n".join(all_suspended_accounts))
                if all_active_impersonators:
                    print("\n".join(all_active_impersonators))
                if all_not_found_users:
                    print("\n".join(all_not_found_users))

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
                channel_names = [os.path.basename(txt_file).replace(
                    'Active-', '').replace('.txt', '') for txt_file in txt_files]
                if ch in channel_names:
                    process_choice(str(channel_names.index(ch) + 1))
                else:
                    print(f"Invalid name: {ch}")
    else:
        if choice.isdigit():
            process_choice(choice)
        else:
            channel_names = [os.path.basename(txt_file).replace('Active-', '').replace(
                '.txt', '') for txt_file in txt_files]
            if choice in channel_names:
                process_choice(str(channel_names.index(choice) + 1))
            else:
                print(f"Invalid name: {choice}")

    # Process unresolvable usernames at the end
    reactivated_usernames = []
    with (Session() as session):
        for usernames_chunk in chunked_usernames(unresolvable_usernames, 100):
            process_unresolvable_user(session, reactivated_usernames, usernames_chunk)

    # Output for reactivated accounts
    if reactivated_usernames:
        print("\n_____________________________________________")
        print("Reactivated impersonators across all channels")
        print("_____________________________________________")
        for username in reactivated_usernames:
            print(f"Impersonator reactivated: {username}")


def validate_user_choice(choice, txt_files):
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


# Main function to execute the script
def main():
    try:
        create_tables()

        with Session() as outer_session:
            if is_database_empty(outer_session):
                print("\n   [Unique Situation Detected]")
                print("----------------------------------------")
                print("The SQLite database file did not exist or was empty.")
                print("----------------------------------------")

        txt_files_directory = os.path.join(base_dir, "TwitterData", "TXT-ImpersonatorAccounts", "ImpersonatorURLs")
        txt_files = glob.glob(f"{txt_files_directory}/Active-*.txt")
        if not txt_files:
            print("No protected channels found.")
            return

        print("\nSelect a protected channel to process:")
        for index, txt_file in enumerate(txt_files, start=1):
            print(f"{index}. {os.path.basename(txt_file).replace('Active-', '').replace('.txt', '')}")

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
