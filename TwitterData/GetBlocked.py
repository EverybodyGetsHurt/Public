"""Pretty-Much-Perfect"""
import os  # Importing the os module for interacting with the operating system
import sys  # Needed for the User Interrupt catching
import time  # Facilitates time-related operations, like adding delays between API requests.
import sqlite3  # Importing sqlite3 for SQLite database operations
import logging  # Import the logging module (TODO: Replace by config.py logging functions)
import requests  # Importing the requests library to make HTTP requests
from datetime import datetime  # Importing datetime for handling date and time
from requests_oauthlib import OAuth1  # Importing OAuth1 from requests_oauthlib for OAuth 1.0a authentication
from instance.config import find_root, get_databases, list_user_emails, get_twitter_credentials, get_user_id

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def log_api_call(url, response):
    """
    Log details of an API call.

    Args:
        url (str): The URL of the API request.
        response (requests.Response): The response object from requests library.
    """
    logging.info(f"API Request URL: {url}")
    logging.info(f"Status Code: {response.status_code}")
    rate_limit_remaining = response.headers.get('x-rate-limit-remaining')
    rate_limit_reset = response.headers.get('x-rate-limit-reset')
    logging.info(f"Rate Limit Remaining: {rate_limit_remaining}")
    if rate_limit_reset:
        reset_time = datetime.fromtimestamp(int(rate_limit_reset))
        logging.info(f"Rate Limit Resets At: {reset_time}")
    if response.status_code != 200:
        logging.error(f"Error Response: {response.text}")
    else:
        logging.info("Request successful.")


def get_blocked_accounts(credentials, user_id, user_email):
    """

    :param credentials:
    :param user_id:
    :param user_email:
    :return:
    """
    consumer_key, consumer_secret, access_token, access_token_secret = credentials
    all_blocked_accounts = []
    next_token = None
    rate_limit_threshold = 0  # Threshold for rate limit
    rate_limit_reset_time = None  # Initialize to None

    while True:
        url = f'https://api.twitter.com/2/users/{user_id}/blocking?max_results=1000'
        if next_token:
            url += f'&pagination_token={next_token}'
        auth = OAuth1(consumer_key, consumer_secret, access_token, access_token_secret)
        response = requests.get(url, auth=auth)
        log_api_call(url, response)

        # Check for rate limit before proceeding
        rate_limit_remaining = int(response.headers.get('x-rate-limit-remaining', '0'))
        if rate_limit_remaining <= rate_limit_threshold or response.status_code == 429:
            # Only update the reset time if it hasn't been set yet, or we've hit a rate limit error
            if rate_limit_reset_time is None or response.status_code == 429:
                rate_limit_reset_time = int(response.headers.get('x-rate-limit-reset', '0'))

            sleep_time = max(rate_limit_reset_time - int(time.time()) + 5, 0)  # Add extra 5 seconds
            logging.info(f"Rate limit reached. Sleeping for {sleep_time} seconds.")
            time.sleep(sleep_time)
            # Reset the rate_limit_reset_time after sleeping
            rate_limit_reset_time = None
            continue  # After sleeping, retry the request

        if response.status_code == 200:
            data = response.json()
            logging.info(f"Raw response data: {data}")  # Log the raw response data
            if 'data' in data:
                for account in data['data']:
                    all_blocked_accounts.append((account['id'], account['username']))
                next_token = data.get('meta', {}).get('next_token')
                if not next_token:
                    break
            else:
                logging.error("Unexpected data format received.")
                return None
        else:
            logging.error(f"Error retrieving blocked accounts: {response.status_code}")
            return None

    # Write the blocked accounts with header to the log file
    project_root = find_root()
    logs_dir = os.path.join(project_root, 'logs')
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    log_path = os.path.join(logs_dir, 'GetBlocked.log')
    with open(log_path, 'a') as log_file:
        log_file.write(f"\n============================================================================================"
                       f"============================\nBlocked accounts for {user_email} (Twitter ID: {user_id})"
                       f" - Total: {len(all_blocked_accounts)}\n======================================================="
                       f"=================================================================\n")
        for account_id, username in all_blocked_accounts:
            log_file.write(f"{username}:{account_id}\n")
        log_file.write("\n")  # Add a newline for separation between different users

    return all_blocked_accounts


def update_user_blocking_activity(db_path, user_email, twitter_id, blocked_accounts):
    """

    :param db_path:
    :param user_email:
    :param twitter_id:
    :param blocked_accounts:
    :return:
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT account_name FROM All_Users WHERE email = ?", (user_email,))
        username_result = cursor.fetchone()
        username = username_result[0] if username_result else 'Unknown'

        blocked_str = ','.join([f"{username}:{account_id}" for account_id, username in blocked_accounts])
        blocked_count = len(blocked_accounts)
        cursor.execute("SELECT * FROM UserReportingActivity WHERE email = ?", (user_email,))
        result = cursor.fetchone()
        now_formatted = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if result:
            cursor.execute(
                """UPDATE UserReportingActivity SET blocked = ?, blocked_nr = ?, last_updated = ?, username = ? WHERE 
                email = ?""",
                (blocked_str, blocked_count, now_formatted, username, user_email))
        else:
            cursor.execute(
                """INSERT INTO UserReportingActivity (email, twitter_id, username, blocked, blocked_nr, last_updated) 
                VALUES (?, ?, ?, ?, ?, ?)""",
                (user_email, twitter_id, username, blocked_str, blocked_count, now_formatted))
        conn.commit()
        print(f"Updated database for user: {user_email}")
    finally:
        conn.close()


def main():
    """
    Main function to process user selection and update blocked accounts in the database.
    """
    try:
        accounts_db_path, impersonators_db_path = get_databases()  # Get both database paths
        emails = list_user_emails()  # Use the correct database path

        print("" * 2 + "=" * 126)  # Print a line of underscores with 2 empty lines before it
        print(f"         Retrieve all current Blocked accounts from the API and update the database")
        print("=" * 126 + "\n")  # Print another line of underscores with one empty line below it

        # Displaying all user emails
        for idx, email in enumerate(emails, start=1):
            print(f"{idx}. {email}")

        # User input for selection
        user_input = input(f"\nSelect a user by entering the number, "
                           "multiple numbers separated by commas, or 'all': ").strip().lower()

        # Determine the list of emails to process
        selected_emails = emails if user_input == "all" else [emails[int(i.strip()) - 1] for i in user_input.split(',')
                                                              if i.strip().isdigit()]

        # Process each selected email
        for user_email in selected_emails:
            try:
                print(f"\n======================================================================\nRetrieving credential"
                      f"s for {user_email}...\n======================================================================")
                credentials = get_twitter_credentials(accounts_db_path, user_email)
                user_id = get_user_id(accounts_db_path, user_email)

                if user_id and credentials:
                    print(f"Retrieving blocked accounts for Twitter ID {user_id}...")
                    blocked_accounts = get_blocked_accounts(credentials, user_id, user_email)

                    if blocked_accounts:
                        print("Updating blocked accounts in the database...")
                        update_user_blocking_activity(accounts_db_path, user_email, user_id, blocked_accounts)
                        print(f"Retrieved and updated blocked accounts successfully.\n================================="
                              f"=================================")
                    else:
                        print(f"No blocked accounts found or an error occurred during retrieval.\n====================="
                              f"===================================================")
                else:
                    print(f"Twitter ID not set or credentials missing for the selected user: {user_email}\n==========="
                          f"================================================================")
                    continue  # Skip to the next user if credentials or Twitter ID are missing
            except ValueError as ve:
                print(f"Warning: {ve} - Skipping to next user.\n==============================================="
                      f"==============================")
                continue  # Skip to next user in case of missing credentials
            except Exception as e:
                print(f"An error occurred while processing {user_email}:\n{e}\n======================================="
                      f"====================================\n")
                continue  # Continue to the next email in case of an error

    except KeyboardInterrupt:
        print("\n\n" + "+" * 40)
        print("+++     USER INTERRUPTED SCRIPT      +++")
        print("+" * 40)
        sys.exit(0)
    except Exception as e:
        print(f"An error occurred in main function:\n{e}\n========================================================="
              f"==========\n")


if __name__ == "__main__":
    main()
