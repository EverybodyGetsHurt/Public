import requests
import sqlite3
import os
from requests_oauthlib import OAuth1
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


def get_muted_accounts(credentials, user_id):
    consumer_key, consumer_secret, access_token, access_token_secret = credentials

    # Twitter API v2 endpoint for getting list of muted accounts
    url = f'https://api.twitter.com/2/users/{user_id}/muting'

    # Setting up OAuth
    auth = OAuth1(consumer_key, consumer_secret, access_token, access_token_secret)

    # Making the request
    response = requests.get(url, auth=auth)

    if response.status_code == 200:
        # Parse and return the data if the request is successful
        return response.json()
    else:
        # Handle errors
        return response.status_code, response.text

# Main execution
if __name__ == "__main__":
    try:
        db_path = get_database_path()
        user_email = "xxxxxxxxxxxxxxxxxxxxxxxxxx"
        credentials = get_twitter_credentials(db_path, user_email)

        if credentials:
            # Assuming you have the numerical user ID
            user_id = "v"  # Replace with the actual user ID
            muted_accounts = get_muted_accounts(credentials, user_id)
            print(muted_accounts)
        else:
            print("Failed to retrieve credentials.")

    except Exception as e:
        print(f"An error occurred: {e}")
