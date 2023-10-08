# Import necessary libraries and modules
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, JSON
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base
from datetime import datetime
from instance import config
from typing import List
import traceback
import requests
import logging
import random
import json
import glob
import time
import os

# Logging setup
log_filename = "TwitterData/SQL-ImpersonatorAccounts/ImpersonatorAccounts.log"
if not os.path.exists(os.path.dirname(log_filename)):
    os.makedirs(os.path.dirname(log_filename))
logging.basicConfig(filename=log_filename, level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

# Directory and database setup
base_dir = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(
    base_dir, "TwitterData", "SQL-ImpersonatorAccounts", "ImpersonatorAccounts.sqlite"
)
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# SQLAlchemy setup
Base = declarative_base()
engine = create_engine(DATABASE_URL)
Session = scoped_session(sessionmaker(bind=engine))

# API setup
BASE_URL = "https://api.twitter.com/2/users/by"

# API tokens
main_token = config.BEARER_TOKEN
backup_token = config.BEARER_TOKEN_V2
tokens_list = [main_token, backup_token]


# Token Manager for handling the token rotation
class TokenManager:
    """
    Manages the rotation and retrieval of API tokens to handle rate limiting.
    Initializes with a list of tokens and provides methods to get the current token
    and rotate to the next token in a round-robin manner.
    """

    # Initialization of TokenManager with a list of tokens
    def __init__(self, tokens):
        self.tokens_list = tokens
        self.current_token_index = 0

    # Get the current token from the list
    def get_current_token(self):
        return self.tokens_list[self.current_token_index]

    # Rotate to the next token in the list
    def rotate_token(self):
        self.current_token_index = (self.current_token_index + 1) % len(self.tokens_list)


# Instantiate the TokenManager with the list of tokens
token_manager = TokenManager(tokens_list)


# Custom JSON encoder to handle non-serializable objects
class SafeEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)


class TwitterAccount(Base):
    __tablename__ = "ImpersonatorAccounts"
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
        self.created_at = datetime.strptime(kwargs.get("created_at"),
                                            '%Y-%m-%dT%H:%M:%S.%fZ') if kwargs.get("created_at") else None
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


# Function to create a new TwitterAccount object and add it to the session
def create_new_account(user_data, session):
    new_account = TwitterAccount(**user_data)
    session.add(new_account)
    logging.info(f"Added new account {user_data['username']}")
    print(f"Added new account {user_data['username']}")
    try:
        session.commit()
        logging.info("Database commit successful.")
    except Exception as e:
        session.rollback()
        logging.error(f"Database commit failed: {e}", exc_info=True)


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
        print(f"{username} is Suspended.")
        try:
            session.commit()
            logging.info("Database commit successful.")
        except Exception as e:
            session.rollback()
            logging.error(f"Database commit failed: {e}", exc_info=True)

    else:
        user_data = {
            'username': username,
            'protected_channel': protected_channel,
            'api_response': error
        }
        new_account = TwitterAccount(**user_data)
        new_account.mark_as_suspended()
        session.add(new_account)
        try:
            session.commit()
            logging.info("Database commit successful.")
        except Exception as e:
            session.rollback()
            logging.error(f"Database commit failed: {e}", exc_info=True)


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

        # Check if the user already exists
        existing_account = session.query(TwitterAccount).filter_by(username=username).first()

        if existing_account:
            # Update existing account
            for key, value in user_data.items():
                setattr(existing_account, key, value)
            logging.info(f"Updated {username} in the database as not found.")
        else:
            # Create new account
            new_account = TwitterAccount(**user_data)
            session.add(new_account)
            logging.info(f"Added {username} to the database as not found.")

        try:
            session.commit()
            logging.info("Database commit successful.")
        except Exception as e:
            session.rollback()
            logging.error(f"Database commit failed: {e}", exc_info=True)

    except Exception as e:
        logging.error(f"Failed to process {username}: {e}", exc_info=True)
        session.rollback()


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

    print(f"{user_data['username']} impersonates {protected_channel}.")
    try:
        session.commit()
        logging.info("Database commit successful.")
    except Exception as e:
        session.rollback()
        logging.error(f"Database commit failed: {e}", exc_info=True)


# Function to connect to the Twitter API endpoint with enhanced error handling and token rotation
def connect_to_endpoint(url, headers, max_retries=5, base_delay=5, max_delay=60):
    retries = 0
    while retries <= max_retries:
        try:
            logging.info(f"Connecting to URL: {url} with headers: {headers}")
            response = requests.get(url, headers=headers)
            response.raise_for_status()  # Raises an HTTPError if the HTTP request returned an unsuccessful status code

            if response.status_code != 429:
                return response.json()

        except requests.HTTPError as e:
            error_message = f"HTTP error occurred for URL {url}: {e}"
            logging.error(f"HTTP error occurred: {e}", exc_info=True)
            print(error_message)  # Printing the error message for immediate feedback

            if e.response.status_code == 429:  # Handling rate limit errors
                token_manager.rotate_token()  # Rotate the token when rate limit exceeded
                delay = min(max_delay, base_delay * (2 ** retries) + random.uniform(0, 1))
                logging.warning(f"Rate limit exceeded, retrying in {delay:.2f} seconds with a new token...")
                time.sleep(delay)
                retries += 1
                continue

            raise  # Re-raise the exception if it is not a rate limit error

        except requests.ConnectionError as e:
            logging.error(f"Connection error occurred: {e}", exc_info=True)
            raise

        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}", exc_info=True)
            raise  # Re-raise the exception for any other errors

        # If retries exceeded, raise an exception
        if retries > max_retries:
            logging.error("Max retries reached for the API request.")
            raise Exception("Max retries reached for the API request.")


# New function to handle API requests with a retry mechanism
def make_api_request(url, headers, retries=3, delay=5):
    for _ in range(retries):
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            logging.error(f"HTTP error occurred: {e}")
            if e.response.status_code == 429:  # Rate limit exceeded
                logging.warning("Rate limit exceeded. Retrying...")
                time.sleep(delay)
                continue
            break  # For other HTTP errors, break the loop and handle the error outside
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            break  # For other errors, break the loop and handle the error outside
    return None  # Return None if the request fails


# This function processes the API response, handling various scenarios like suspended accounts,
# active impersonators, and not found users. It updates the database accordingly.
def process_api_response(response, session, protected_channel):
    if not response:
        logging.error("No response received from the API.")
        return
    logging.info(f"Raw API response: {response}")  # Added this line to log the raw API response
    print("Processing API response...")
    suspended_accounts = []
    active_impersonators = []
    not_found_users = []

    if 'errors' in response:
        for error in response['errors']:
            # Handling specific error types and updating the database accordingly
            detail = error.get('detail', 'No detail provided')
            logging.error(f"API Error: {detail}")

            username = error.get('value')
            account = session.query(TwitterAccount).filter_by(username=username).first()

            if 'has been suspended' in detail:
                process_suspended_user(account, username, error, protected_channel, session)
                continue

            # Handling username not found
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
                        try:
                            session.commit()
                            logging.info("Database commit successful.")
                        except Exception as e:
                            session.rollback()
                            logging.error(f"Database commit failed: {e}", exc_info=True)

                    except Exception as e:
                        logging.error(f"Could not update username: {e}")
                        print(f"Both username {username} and Twitter ID {account.twitter_id} could not be resolved.")
                        account.api_response = error
                        account.unresolvable = True
                        try:
                            session.commit()
                            logging.info("Database commit successful.")
                        except Exception as e:
                            session.rollback()
                            logging.error(f"Database commit failed: {e}", exc_info=True)

                else:
                    # This part should handle the case when the user isn't found and there's no existing account info
                    process_not_found_user(username, error, protected_channel, session)
                continue

    if 'data' in response:
        for user_data in response['data']:
            user_data['protected_channel'] = protected_channel
            user_data['api_response'] = json.dumps(user_data, cls=SafeEncoder)
            account = session.query(TwitterAccount).filter_by(twitter_id=user_data['id']).first()

            if account:
                # print(f"Before update: {account.username}, {account.api_response}")  # Debug print

                if not account.suspended:
                    if account.username != user_data['username']:
                        print(f"{account.username} changed username to {user_data['username']}. Updating Database")
                        account.update_username(user_data['username'])

                account.update_api_response(user_data)
                try:
                    # Ensure that the session is being committed
                    session.commit()
                    logging.info("Database commit successful.")
                except Exception as e:
                    session.rollback()
                    logging.error(f"Database commit failed: {e}", exc_info=True)

                # print(f"After update: {account.username}, {account.api_response}")  # Debug print
                active_impersonators.append(f"{user_data['username']} impersonates {protected_channel}.")
            else:
                create_new_account(user_data, session)
                active_impersonators.append(
                    f"Added new account {user_data['username']} impersonating {protected_channel}")
                try:
                    session.commit()
                    logging.info("Database commit successful.")
                except Exception as e:
                    session.rollback()
                    logging.error(f"Database commit failed: {e}", exc_info=True)

    return suspended_accounts, active_impersonators, not_found_users


# Function to process the user's choice of protected channel
def process_user_choice(choice, txt_files):
    if not choice or not choice.strip():
        print(
            "Invalid input. Please enter a number corresponding to the protected channels, or type 'ALL' to select "
            "all channels.")
        return

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

            usernames = [get_username_from_url(url) for url in urls if url.strip()]
            if not usernames:
                logging.error(f"The usernames list is empty for file {selected_file}.")
                return

            with Session() as session:
                chunks = list(chunked_usernames(usernames))
                for chunk in chunks:
                    url = create_url(chunk)
                    headers = create_headers(token_manager.get_current_token())
                    response_data = connect_to_endpoint(url, headers)

                    suspended_accounts, active_impersonators, not_found_users = process_api_response(response_data,
                                                                                                     session,
                                                                                                     protected_channel)
                    all_suspended_accounts.extend(suspended_accounts)
                    all_active_impersonators.extend(active_impersonators)
                    all_not_found_users.extend(not_found_users)
                    time.sleep(1)

                print("\n".join(all_suspended_accounts))
                print("\n".join(all_active_impersonators))
                print("\n".join(all_not_found_users))
                print(f"All chunks processed for {protected_channel}.")

        except ValueError as e:
            print(f"ValueError occurred: {e}")
            print("Invalid input. Please enter a number.")
        except IndexError:
            print("Invalid selection. Please enter a number corresponding to the available options.")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}", exc_info=True)
            traceback.print_exc()

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
            channel_names = [os.path.basename(txt_file).replace(
                'Active-', '').replace('.txt', '') for txt_file in txt_files]
            if choice in channel_names:
                process_choice(str(channel_names.index(choice) + 1))
            else:
                print(f"Invalid name: {choice}")


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
        'Active-', '').replace(
        '.txt', '').lower() for txt_file in txt_files]
    if choice.lower() in channel_names:
        return True

    print("Invalid input format. Please enter a valid option.")
    return False


# Main function to execute the script
def main():
    create_tables()

    with Session() as outer_session:
        if is_database_empty(outer_session):
            print("\n   [Unique Situation Detected]")
            print("----------------------------------------")
            print("The SQLite database file did not exist or was empty.")
            print("----------------------------------------")

    txt_files_directory = os.path.join(
        base_dir, "TwitterData", "TXT-ImpersonatorAccounts", "ImpersonatorURLs"
    )

    txt_files = glob.glob(f"{txt_files_directory}/Active-*.txt")

    if not txt_files:
        print("No protected channels found.")
        return

    print("Select a protected channel to process:")
    for index, txt_file in enumerate(txt_files, start=1):
        print(f"{index}. {os.path.basename(txt_file).replace('Active-', '').replace('.txt', '')}")

    user_choice = input("Comma separated Nr or Name. Or type ALL: ").strip()
    if validate_user_choice(user_choice, txt_files):
        process_user_choice(user_choice, txt_files)
    else:
        print("Invalid choice. Please try again.")


# Execute the main function if the script is run as the main program
if __name__ == "__main__":
    main()
