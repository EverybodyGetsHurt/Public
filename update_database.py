from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import sessionmaker, scoped_session, relationship, declarative_base
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
logging.basicConfig(filename=log_filename, level=logging.DEBUG)
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
main_bearer_token = config.BEARER_TOKEN
backup_bearer_token = config.BEARER_TOKEN_V2

# API limits
# https://developer.twitter.com/en/docs/twitter-api/rate-limits#v2-limits


class TwitterAccount(Base):
    __tablename__ = "twitter_accounts"
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
    rechecked_suspended_state = Column(DateTime)
    username_changed = Column(Boolean, default=False)
    username_changed_to = Column(String)
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
        self.rechecked_suspended_state = None
        self.username_changed = False
        self.username_changed_to = None
        self.username_changed_date = None
        self.unresolvable = False
        self.api_response = kwargs.get("api_response")
        self.api_response_updated_at = datetime.now()  # Set the current time
        self.url = kwargs.get("url")
        self.profile_image_url = kwargs.get("profile_image_url")

    def mark_as_suspended(self, date=None):
        """
        Mark the account as suspended.
        """
        if not self.suspended:  # Add this condition
            logging.info(f"Marking {self.username} as suspended.")
            self.suspended = True
            self.suspended_date = date or datetime.now()
            logging.info(f"Marked {self.username} as suspended at {self.suspended_date}.")
        else:
            logging.info(f"{self.username} is already marked as suspended.")

    def mark_as_unsuspended(self):
        """
        Mark the account as unsuspended.
        """
        self.suspended = False
        self.suspended_date = None
        self.rechecked_suspended_state = datetime.now()

    def update_username(self, new_username):
        """
        Update the username of the account.
        """
        self.username_changed = True
        self.username_changed_to = new_username
        self.username_changed_date = datetime.now()

    def update_api_response(self, new_response):
        """
        Update the API response.
        """
        self.previous_api_response = self.api_response
        self.previous_api_response_updated_at = self.api_response_updated_at
        self.api_response = new_response
        self.api_response_updated_at = datetime.now()

    def __repr__(self):
        """
        String representation of the Twitter account.
        """
        return f"<TwitterAccount(username={self.username}, twitter_id={self.twitter_id}, suspended={self.suspended})>"


class OAuth10a(Base):
    __tablename__ = "oauth10a_accounts"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    previous_twitter_account_info = Column(String)
    twitter_account_id = Column(String, ForeignKey("twitter_accounts.twitter_id"))
    twitter_account = relationship("TwitterAccount", backref="oauth10a")


class SafeEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)


def chunked_usernames(usernames: List[str], chunk_size: int = 100):
    """Yield successive n-sized chunks from a list."""
    for i in range(0, len(usernames), chunk_size):
        yield usernames[i:i + chunk_size]


def create_new_account(user_data, session):
    new_account = TwitterAccount(**user_data)
    session.add(new_account)
    logging.info(f"Added new account {user_data['username']}")
    print(f"Added new account {user_data['username']}")
    session.commit()


def create_headers(bearer_token):
    headers = {"Authorization": f"Bearer {bearer_token}"}
    return headers


def create_tables():
    Base.metadata.create_all(engine)


def create_url(usernames):
    usernames = ",".join(usernames)
    url = (f"{BASE_URL}?usernames={usernames}&user.fields=created_at,description,id,name,profile_image_url,"
           f"public_metrics,url,username,verified")
    return url


def delete_user(user_id, session):
    account = session.query(TwitterAccount).filter_by(twitter_id=user_id).first()
    if account:
        session.delete(account)
        session.commit()


def get_account_by_twitter_id(twitter_id, session):
    return session.query(TwitterAccount).filter_by(twitter_id=twitter_id).first()


def get_protected_channel_from_filename(filename):
    protected_channel = filename.replace("Active-", "").replace(".txt", "")
    return protected_channel


def get_username_from_url(url):
    return url.strip().split("/")[-1]


def get_impersonators_for_protected_channel(session, protected_channel):
    impersonators_query = session.query(TwitterAccount).filter_by(protected_channel=protected_channel)
    return impersonators_query.all()


def is_database_empty(session=None):
    if not session:
        session = Session()
    return session.query(TwitterAccount).first() is None


def all_impersonators(session, filename):
    protected_channel = get_protected_channel_from_filename(filename)

    with open(filename, "r") as file:
        urls = file.readlines()
        # Print the content of the URLs list
        print(f"URLs: {urls}")

    usernames_from_file = [get_username_from_url(url) for url in urls if url.strip()]

    for username in usernames_from_file:
        db_impersonator = (
            session.query(TwitterAccount).filter_by(username=username).first()
        )
        if db_impersonator:
            if db_impersonator.protected_channel != protected_channel:
                db_impersonator.protected_channel = protected_channel
                session.commit()
        else:
            session.add(
                TwitterAccount(
                    username=username,
                    protected_channel=protected_channel,
                    followers_count=None,
                    following_count=None,
                    tweet_count=None,
                )
            )
            session.commit()

    all_impersonator_accounts = get_impersonators_for_protected_channel(
        session, protected_channel
    )
    return all_impersonator_accounts


def connect_to_endpoint(url, headers, max_retries=5, base_delay=5, max_delay=60):
    retries = 0
    while retries <= max_retries:
        response = requests.get(url, headers=headers)
        if response.status_code != 429:  # Not a rate limit error
            response.raise_for_status()  # Raise an exception for other HTTP errors
            return response.json()

        # Handle rate limit error with exponential backoff
        retries += 1
        delay = min(max_delay, (base_delay * (2 ** retries)) + random.uniform(0, 1))
        logging.warning(f"Rate limit exceeded, retrying in {delay:.2f} seconds...")
        time.sleep(delay)

    # If it reaches here, it means it has retried max_retries times already
    raise Exception("Max retries reached for the API request")


def exponential_backoff_retry(max_retries, base_delay, max_delay):
    retries = 0
    while retries <= max_retries:
        try:
            # Your API request code here
            pass  # Replace with the actual code

        except requests.HTTPError as e:
            if e.response.status_code == 429:  # Rate limit exceeded
                delay = min(max_delay, (base_delay * 2 ** retries) + random.uniform(0, 1))
                logging.warning(f"Rate limit exceeded, retrying in {delay} seconds...")
                time.sleep(delay)
                retries += 1
            else:
                logging.error(f"HTTP error occurred: {e}")
                break  # Or handle other HTTP errors as needed
        else:
            break  # Break the loop if the request is successful


def process_api_response(response, session, protected_channel):
    processed_data = []  # Create a list to store processed data

    if 'errors' in response:
        for error in response['errors']:
            detail = error.get('detail', 'No detail provided')
            logging.error(f"API Error: {detail}")

            username = error.get('value')
            account = session.query(TwitterAccount).filter_by(username=username).first()

            if 'has been suspended' in detail:
                if account:
                    account.mark_as_suspended()
                    account.api_response = error
                    session.commit()
                    processed_data.append(f"{username} is Suspended.")
                else:
                    user_data = {
                        'username': username,
                        'protected_channel': protected_channel,
                        'api_response': error,
                    }
                    new_account = TwitterAccount(**user_data)
                    new_account.mark_as_suspended()
                    session.add(new_account)
                    session.commit()
                    processed_data.append(f"Added and marked new account {username} as suspended.")

            elif 'could not be found' in detail:
                if account:
                    url = f"https://api.twitter.com/2/users/{account.twitter_id}"
                    headers = create_headers(main_bearer_token)
                    try:
                        new_user_data = connect_to_endpoint(url, headers)
                        new_username = new_user_data['data']['username']
                        account.update_username(new_username)
                        account.update_api_response(new_user_data['data'])
                        session.commit()
                        processed_data.append(f"Username {username} not found. Updated to {new_username} using "
                                              f"Twitter ID.")
                    except Exception as e:
                        logging.error(f"Could not update username: {e}")
                else:
                    user_data = {
                        'username': username,
                        'protected_channel': protected_channel,
                        'api_response': error,
                    }
                    new_account = TwitterAccount(**user_data)
                    new_account.unresolvable = True
                    session.add(new_account)
                    session.commit()
                    processed_data.append(f"Added new account {username} with username not found.")

    if 'data' in response:
        for user_data in response['data']:
            user_data['protected_channel'] = protected_channel
            user_data['api_response'] = json.dumps(user_data, cls=SafeEncoder)
            account = session.query(TwitterAccount).filter_by(twitter_id=user_data['id']).first()

            if account:
                if not account.suspended and account.username != user_data['username']:
                    account.username = user_data['username']
                    processed_data.append(f"{account.username} changed username to {user_data['username']} trying to "
                                          f"avoid getting Suspended. Updating Database.")

                account.update_api_response(user_data)
                session.commit()
                processed_data.append(f"{user_data['username']} impersonates {protected_channel}.")
            else:
                create_new_account(user_data, session)
                session.commit()

    return processed_data  # Return the processed data at the end of the function


def main():
    create_tables()

    with Session() as outer_session:
        if is_database_empty(outer_session):
            print("\n   [Unique Situation Detected]")
            print("----------------------------------------")
            print("The SQLite database file did not exist or was empty.")
            print("----------------------------------------")

    create_tables()

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

    def process_choice(choice):
        all_processed_data = []  # Collecting all processed data here
        protected_channel = "unknown channel"  # Initialize with a default value

        try:
            choice_number = int(choice)
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
                    headers = create_headers(main_bearer_token)
                    response_data = connect_to_endpoint(url, headers)
                    processed_data = process_api_response(response_data, session, protected_channel)
                    all_processed_data.extend(processed_data)
                    time.sleep(1)

                print("\n".join(all_processed_data))
                print(f"All chunks processed for {protected_channel}.")

        except ValueError as e:
            print(f"ValueError occurred: {e}")
            print("Invalid input. Please enter a number.")
        except IndexError:
            print("Invalid selection. Please enter a number corresponding to the available options.")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}", exc_info=True)
            traceback.print_exc()
        finally:
            print(
                f"Operation completed for {protected_channel if 'protected_channel' in locals() else 'unknown channel'}.")

    if user_choice.upper() == "ALL":
        for txt_file in txt_files:
            process_choice(str(txt_files.index(txt_file) + 1))
    elif ',' in user_choice:
        choices = user_choice.split(',')
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
        process_choice(user_choice)


if __name__ == "__main__":
    main()
