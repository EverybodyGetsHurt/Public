import requests
import sqlite3
import os

from requests_oauthlib import OAuth1
from datetime import datetime
from instance import config


# Function to construct the database path
def get_database_path():
    # Set up the path to the database.sqlite file
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "instance", "database.sqlite")

    # Check if the database file exists
    if not os.path.exists(db_path):
        raise FileNotFoundError("Database file not found at: " + db_path)

    return db_path


def list_user_emails(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Query to list all emails
        query = "SELECT email FROM All_Users"
        cursor.execute(query)

        # Fetch all emails
        results = cursor.fetchall()
        conn.close()

        emails = [email[0] for email in results]  # Extract email from each tuple
        return emails

    except sqlite3.Error as e:
        raise sqlite3.Error(f"Database error: {e}")


def get_user_id(db_path, user_email):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # First, try to get the Twitter ID from the OAuth10a_3Legged table
        query = "SELECT twitter_id FROM OAuth10a_3Legged WHERE email = ?"
        cursor.execute(query, (user_email,))
        result = cursor.fetchone()

        if not result:
            # If not found, try to get the Twitter ID from the OAuth20_PKCE table
            query = "SELECT twitter_id FROM OAuth20_PKCE WHERE email = ?"
            cursor.execute(query, (user_email,))
            result = cursor.fetchone()

        conn.close()

        if result and result[0] is not None:
            return int(result[0])
        else:
            print(f"No Twitter ID found for email: {user_email}")
            return None

    except sqlite3.Error as e:
        raise sqlite3.Error(f"Database error: {e}")


# Function to get Twitter OAuth 1.0a credentials from the database
def get_twitter_credentials(db_path, user_email):
    # Connect to the SQLite database
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Query to get the OAuth credentials for a specific user
        query = """SELECT oauth_token, oauth_token_secret
                   FROM OAuth10a_3Legged
                   WHERE email = ?"""
        cursor.execute(query, (user_email,))

        # Fetch the credentials
        result = cursor.fetchone()
        conn.close()

        if result:
            oauth_token, oauth_token_secret = result
            consumer_key = config.APP_CONSUMER_KEY
            consumer_secret = config.APP_CONSUMER_SECRET

            if not consumer_key or not consumer_secret:
                raise ValueError("Twitter consumer key and/or secret are not set in environment variables")

            return consumer_key, consumer_secret, oauth_token, oauth_token_secret
        else:
            raise ValueError("No credentials found for email: " + user_email)

    except sqlite3.Error as e:
        raise sqlite3.Error(f"Database error: {e}")


def get_blocked_accounts(credentials, user_id):
    consumer_key, consumer_secret, access_token, access_token_secret = credentials

    all_blocked_accounts = []
    next_token = None
    while True:
        url = f'https://api.twitter.com/2/users/{user_id}/blocking?max_results=1000'
        if next_token:
            url += f'?pagination_token={next_token}'

        auth = OAuth1(consumer_key, consumer_secret, access_token, access_token_secret)
        response = requests.get(url, auth=auth)

        if response.status_code == 200:
            data = response.json()
            if 'data' in data:
                all_blocked_accounts.extend(data['data'])
                next_token = data.get('meta', {}).get('next_token')
                if not next_token:
                    break
            else:
                print("Unexpected data format received:", data)
                return None
        else:
            print("Error retrieving blocked accounts:", response.status_code, response.text)
            return None

    return all_blocked_accounts


def update_user_reporting_activity_for_blocked(db_path, user_email, twitter_id, blocked_accounts):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT account_name FROM All_Users WHERE email = ?", (user_email,))
        username_result = cursor.fetchone()
        username = username_result[0] if username_result else 'Unknown'

        # Ensure that blocked_accounts is a list of dictionaries before processing
        if not all(isinstance(account, dict) and 'username' in account for account in blocked_accounts):
            raise ValueError("Invalid format for blocked accounts data")

        blocked_str = ','.join([account['username'] for account in blocked_accounts])
        blocked_count = len(blocked_accounts)

        cursor.execute("SELECT * FROM UserReportingActivity WHERE email = ?", (user_email,))
        result = cursor.fetchone()
        now_formatted = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if result:
            cursor.execute("""UPDATE UserReportingActivity 
                              SET blocked = ?, blocked_nr = ?, last_updated = ?, username = ?
                              WHERE email = ?""",
                           (blocked_str, blocked_count, now_formatted, username, user_email))
        else:
            cursor.execute("""INSERT INTO UserReportingActivity 
                              (email, twitter_id, username, blocked, blocked_nr, last_updated) 
                              VALUES (?, ?, ?, ?, ?, ?)""",
                           (user_email, twitter_id, username, blocked_str, blocked_count, now_formatted))

        conn.commit()
        print(f"Updated database for user: {user_email} with blocked accounts")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()


def main():
    try:
        db_path = get_database_path()
        emails = list_user_emails(db_path)

        for idx, email in enumerate(emails, start=1):
            print(f"{idx}. {email}")
        choice = int(input("Select a user by entering the number: "))
        user_email = emails[choice - 1]

        print(f"Retrieving credentials for {user_email}...")
        credentials = get_twitter_credentials(db_path, user_email)

        if credentials:
            user_id = get_user_id(db_path, user_email)
            if user_id:
                print(f"Retrieving blocked accounts for Twitter ID {user_id}...")
                blocked_accounts = get_blocked_accounts(credentials, user_id)

                if blocked_accounts:
                    print("Updating blocked accounts in the database...")
                    update_user_reporting_activity_for_blocked(db_path, user_email, user_id, blocked_accounts)
                    print("Retrieved and updated blocked accounts successfully.")
                else:
                    print("No blocked accounts found or error occurred during retrieval.")
            else:
                print(f"Twitter ID not set for the selected user: {user_email}")
        else:
            print("Failed to retrieve credentials.")

    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
