"""
    This script is designed to interact with a Twitter account's muted list using the Twitter API, along with managing
    and maintaining a local SQLite database. It automates the process of fetching muted user data from Twitter and
    updating this information in a local database. The script is structured to be user-friendly, allowing users to
    select a specific Twitter account and perform operations related to muted accounts.

    Key Features:
    - Retrieves a list of all muted Twitter accounts for a specified user.
    - Updates the local SQLite database with the latest information about muted accounts.
    - Utilizes OAuth 1.0a for secure Twitter API authentication.
    - Handles various database operations including querying, updating, and inserting data.
    - Provides a user-friendly interface for selecting a Twitter account based on the email associated with it.

    How It Works:
    1. The script first constructs the path to the local SQLite database.
    2. It lists all user emails stored in the database, offering a choice to the user.
    3. Once a user is selected, the script retrieves a corresponding Twitter ID and OAuth credentials from the database.
    4. Using these credentials, it fetches the list of muted accounts from Twitter for the specified user ID.
    5. The script then updates the user's record in the local database with the latest-muted accounts data.
    6. Throughout the process, the script handles exceptions and errors, particularly those related to
       database operations and Twitter API responses.

    Note:
    - The script requires a pre-configured SQLite database with specific tables and structure.
    - It assumes that OAuth credentials and Twitter IDs are already stored in the database.
    - Proper configuration in the 'instance/config.py' file is required for API keys and tokens.
    - The script adheres to Twitter API rate limits and handles pagination for large sets of data.

    Dependencies:
    - requests: For making HTTP requests to the Twitter API.
    - requests_oauthlib: For handling OAuth 1.0a authentication.
    - sqlite3: For SQLite database operations.
    - os: For operating system dependent functionality.
    - datetime: For handling date and time.

    This script is ideal for users or developers who need to manage muted lists for Twitter accounts and maintain a
    record of these lists in a local database.
"""
import requests  # Importing the requests library to make HTTP requests
import sqlite3  # Importing sqlite3 for SQLite database operations
import os  # Importing the os module for interacting with the operating system

from requests_oauthlib import OAuth1  # Importing OAuth1 from requests_oauthlib for OAuth 1.0a authentication
from datetime import datetime  # Importing datetime for handling date and time
from instance import config  # Importing config from the instance package for configuration variables


# Function to construct the database path
#
# The `get_database_path` function constructs the path to the SQLite database file. It ensures that the path is
# correctly formed regardless of the current working directory of the script.
#
# This function does the following:
# 1. Identifies the base directory of the script file using `os.path.dirname` and `os.path.abspath`.
# 2. Joins this base directory with the relative path to the database file ('instance/database.sqlite').
# 3. Checks if the database file exists at the constructed path; if not, it raises a `FileNotFoundError`.
# 4. Returns the absolute path to the database file.
#
# Exception handling is used to manage the case where the database file is not found at the expected location.
#
# This function is crucial for obtaining the correct database path for database operations within the script.
def get_database_path():
    """
    Constructs the path to the SQLite database file.

    The function identifies the base directory of the script file (using os.path.dirname and os.path.abspath)
    and then joins this base directory with the relative path to the database file ('instance/database.sqlite').
    This ensures that the path is correctly formed regardless of the current working directory of the script.

    Raises:
        FileNotFoundError: If the database file does not exist at the constructed path.

    Returns:
        str: The absolute path to the database file.

    :return:
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))  # Getting the directory of the current script file
    db_path = os.path.join(base_dir, "instance", "database.sqlite")  # Creating the path to the database file

    if not os.path.exists(db_path):  # Checking if the database file exists at the path
        raise FileNotFoundError("Database file not found at: " + db_path)  # Raising an error if the file is not found

    return db_path  # Returning the path to the database file


# Function to list all user emails stored in the database
#
# The `list_user_emails` function retrieves and returns a list of email addresses stored in the SQLite database.
#
# This function does the following:
# 1. Establishes a connection to the SQLite database using `sqlite3.connect`.
# 2. Create a cursor object for executing SQL commands.
# 3. Execute an SQL query to select all email addresses from the `All_Users` table.
# 4. Fetches all results from the query execution.
# 5. Closes the database connection.
# 6. Extracts email addresses from the results and returns them as a list.
#
# Exception handling is used to manage potential errors during database operations.
#
# This function is essential for obtaining a list of user emails, which is used in various parts of the script.
def list_user_emails(db_path):
    """
    Lists all user emails stored in the database.

    Args:
        db_path (str): The path to the SQLite database file.

    Returns:
        list: A list of email strings.

    Raises:
        sqlite3.Error: If there's an error in database operations.

    :param db_path:
    :return:
    """
    try:
        conn = sqlite3.connect(db_path)  # Establishing a connection to the SQLite database
        cursor = conn.cursor()  # Creating a cursor object to execute SQL commands

        query = "SELECT email FROM All_Users"  # SQL query to select all emails from the All_Users table
        cursor.execute(query)  # Executing the SQL query

        results = cursor.fetchall()  # Fetching all results from the query execution
        conn.close()  # Closing the database connection

        emails = [email[0] for email in results]  # Extracting email from each tuple in the results
        return emails  # Returning the list of emails

    except sqlite3.Error as e:  # Catching any SQLite database operation errors
        raise sqlite3.Error(f"Database error: {e}")  # Raising the error for external handling


# Function to get the Twitter ID associated with a user's email from the database
#
# The `get_user_id` function retrieves the Twitter ID associated with a given user's email from the SQLite database.
#
# This function does the following:
# 1. Establishes a connection to the SQLite database using `sqlite3.connect`.
# 2. Create a cursor object for executing SQL commands.
# 3. First, it attempts to get the Twitter ID from the `OAuth10a_3Legged` table by executing an SQL query.
# 4. If the Twitter ID is not found in the first table, it tries to get it from the `OAuth20_PKCE` table.
# 5. Closes the database connection.
# 6. Returns the retrieved Twitter ID as an integer, or `None` if not found.
#
# Exception handling is used to manage potential errors during database operations.
#
# This function is essential for obtaining the Twitter ID of a user based on their email, which is used in subsequent
# steps of the script.
def get_user_id(db_path, user_email):
    """
    Retrieves the Twitter ID associated with a given user's email from the SQLite database.

    Args:
        db_path (str): The path to the SQLite database file.
        user_email (str): The email address of the user.

    Returns:
        int or None: The Twitter ID if found, or None if not found.

    Raises:
        sqlite3.Error: If there's an error in database operations.

    :param db_path:
    :param user_email:
    :return:
    """
    try:
        # Establish a connection to the SQLite database
        conn = sqlite3.connect(db_path)  # Establishing a connection to the SQLite database
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


# Function to get Twitter OAuth 1.0a credentials from the database
#
# The `get_twitter_credentials` function retrieves the necessary Twitter OAuth 1.0a credentials (consumer key,
# consumer secret, OAuth token, and OAuth token secret) from the SQLite database for a given user's email. It first
# connects to the database, executes an SQL query to fetch the credentials, and checks if the required consumer key
# and secret are set in environment variables. If everything is in order, it returns the credentials as a tuple.
# If the credentials are not found in the database or if the consumer key/secret is missing, it raises an appropriate
# error.
#
# The try-except block handles potential SQLite database errors and raises them for external handling.
def get_twitter_credentials(db_path, user_email):
    """
    Retrieves Twitter OAuth 1.0a credentials for a specific user's email from the SQLite database.

    Args:
        db_path (str): The path to the SQLite database file.
        user_email (str): The email address of the user.

    Returns:
        tuple or None: A tuple containing consumer key, consumer secret, OAuth token, and OAuth token secret if found,
        or None if not found.

    Raises:
        sqlite3.Error: If there's an error in database operations.
        ValueError: If the consumer key or secret is not set in environment variables.

    :param db_path:
    :param user_email:
    :return:
    """
    try:
        # Establish a connection to the SQLite database
        conn = sqlite3.connect(db_path)  # Establishing a connection to the SQLite database
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
            consumer_key = config.APP_CONSUMER_KEY
            consumer_secret = config.APP_CONSUMER_SECRET

            # Validate that consumer key and consumer secret are set in environment variables
            if not consumer_key or not consumer_secret:
                raise ValueError("Twitter consumer key and/or secret are not set in environment variables")

            return consumer_key, consumer_secret, oauth_token, oauth_token_secret
        else:
            raise ValueError("No credentials found for email: " + user_email)

    except sqlite3.Error as e:  # Catching any SQLite database operation errors
        raise sqlite3.Error(f"Database error: {e}")  # Raising the error for external handling


# Function to retrieve muted accounts for a Twitter user using Twitter API and update the database
#
# The `get_muted_accounts` function interacts with the Twitter API to retrieve a user's muted accounts and subsequently
# updates the SQLite database with this information. It requires two parameters: `credentials` (a tuple containing
# Twitter OAuth credentials) and `user_id` (the Twitter user's ID).
#
# This function handles the following steps:
# 1. Unpacks the Twitter OAuth credentials, including consumer key, consumer secret, OAuth token, and OAuth token secret
# 2. Initializes an empty list, `all_muted_accounts`, to store the muted account information.
# 3. Set the initial value of `next_token` to None to manage paginated responses.
# 4. Enter a loop to handle paginated responses from the Twitter API.
# 5. Constructs the API URL for retrieving muted accounts, including optional pagination information.
# 6. Performs the API request with OAuth1 authentication.
# 7. Check the HTTP response status code.
# 8. If the response is successful (HTTP status code 200), it parses the JSON response.
# 9. Appends the muted accounts data to the `all_muted_accounts` list.
# 10. Check if there's a next pagination token; if not, it exits the loop.
# 11. If the response is not successful, it prints an error message and returns None.
# 12. Finally, it returns the list of muted accounts or None if an error occurred.
#
# Exception handling is included to manage potential errors during the API request and JSON parsing. Any errors are
# printed, and the function returns None to indicate an issue.
#
# This function plays a vital role in the script's functionality, responsible for fetching and updating information
# about muted accounts for a user from the Twitter API.
def get_muted_accounts(credentials, user_id):
    """
    Muting Endpoint (GET_2_users_param_muting):

    Rate Limit: 100 requests per 24 hours per user. With each request, you can fetch up to 1000 muted accounts. This
    means, in a 24-hour period, you can make 100 requests, potentially fetching up to 100,000 (100 requests × 1000
    accounts per request) muted account names for a specific user. Muting Endpoint (GET_2_users_param_muting):

    Rate Limit: 5 requests per 15 minutes per user. With each request, you can also fetch up to 1000 muted accounts.
    This means, in every 15-minute window, you can make 5 requests, potentially fetching up to 5,000 (5 requests × 1000
    accounts per request) muted account names for a specific user. In an hour, this would be 20,000 muted accounts
    (4 × 15-minute windows), and in a 24-hour period, it would be up to 480,000 (24 hours × 20,000 accounts per hour).
    Therefore, your capacity to request data through the mute endpoint is substantial, allowing you to fetch large
    numbers of muted accounts in a day. For the mute endpoint, you have a more frequent opportunity to request data
    but with a smaller number of requests in each window.

    It's important to note that these calculations assume that each request returns the maximum number of accounts
    (1000), which may not always be the case depending on the actual number of muted or blocked accounts associated
    with the user. Also, be aware of the general rate limits on your API key to ensure overall compliant usage.

    :param credentials:
    :param user_id:
    :return:
    """
    # Unpack OAuth 1.0a credentials tuple
    consumer_key, consumer_secret, access_token, access_token_secret = credentials

    # Initialize an empty list to store muted account data and set next_token to None
    all_muted_accounts = []  # List to store muted accounts
    next_token = None  # Pagination token for fetching more data

    # Start a loop to handle pagination and fetching muted accounts
    while True:
        # Construct the Twitter API endpoint URL for fetching muted accounts with a maximum of 1000 results per request
        url = f'https://api.twitter.com/2/users/{user_id}/muting?max_results=1000'

        if next_token:  # If there's a next_token (indicating pagination), add it to the URL
            url += f'&pagination_token={next_token}'

        # Create an OAuth1 authentication object with the credentials
        auth = OAuth1(consumer_key, consumer_secret, access_token, access_token_secret)

        # Make a GET request to the Twitter API to fetch muted accounts
        response = requests.get(url, auth=auth)  # Make a GET request to the Twitter API to fetch muted accounts

        if response.status_code == 200:  # Check if the GET request was successful (HTTP status code 200)
            data = response.json()  # Parse the JSON response

            if 'data' in data:  # Check if the response contains 'data' field
                all_muted_accounts.extend(data['data'])  # Extend the list of muted accounts with the data received

                # Get the next_token for pagination from the response metadata
                next_token = data.get('meta', {}).get('next_token')

                # If there's no next_token, exit the loop
                if not next_token:
                    break
            else:
                # Print an error message and return None if an unexpected data format is received
                print("Unexpected data format received:", data)
                return None
        else:
            # Print an error message with status code and response text and return None in case of an API error
            print("Error retrieving muted accounts:", response.status_code, response.text)
            return None

    # Return the list of muted accounts after fetching all relevant data
    return all_muted_accounts


# The `update_user_reporting_activity` function takes several parameters:
# the database path (`db_path`), the user's email (`user_email`),
# their Twitter ID (`twitter_id`), and a list of muted accounts (`muted_accounts`).
#
# This function is responsible for updating the `UserReportingActivity` table in the SQLite database with information
# about the user's muted accounts. It does the following:
# - Retrieves the user's username from the `All_Users` table based on their email.
# - Converts the list of muted accounts into a comma-separated string and counts the number of muted accounts.
# - Checks if a record already exists for the user in the `UserReportingActivity` table.
# - Formats the current date and time for SQLite storage.
# - If a record exists, it updates the existing record with the new muted accounts and other information.
# - If no record exists, it inserts a new record for the user.
# - Finally, it commits the changes to the database and prints a message to indicate a successful update.
#
# Exception handling is used to manage potential errors during database operations, and the database connection is
# properly closed in the `finally` block.
def update_user_reporting_activity(db_path, user_email, twitter_id, muted_accounts):
    """
    Updates the UserReportingActivity table in the SQLite database with information about muted accounts for a user.

    Args:
        db_path (str): The path to the SQLite database file.
        user_email (str): The email address of the user.
        twitter_id (int): The Twitter ID of the user.
        muted_accounts (list): A list of dictionaries containing information about muted accounts.

    Raises:
        sqlite3.Error: If there's an error in database operations.

    :param db_path:
    :param user_email:
    :param twitter_id:
    :param muted_accounts:
    :return:
    """
    try:
        conn = sqlite3.connect(db_path)  # Establishing a connection to the SQLite database
        cursor = conn.cursor()  # Creating a cursor object to execute SQL commands

        # Retrieve the username for the email
        cursor.execute("SELECT account_name FROM All_Users WHERE email = ?", (user_email,))
        username_result = cursor.fetchone()
        username = username_result[0] if username_result else 'Unknown'

        # Convert the list of muted accounts to a comma-separated string
        muted_str = ','.join([account['username'] for account in muted_accounts])
        muted_count = len(muted_accounts)  # Count the number of muted accounts

        # Check if a record already exists for the user
        cursor.execute("SELECT * FROM UserReportingActivity WHERE email = ?", (user_email,))
        result = cursor.fetchone()

        now_formatted = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Format datetime for SQLite

        if result:
            # Update existing record
            cursor.execute("""UPDATE UserReportingActivity 
                              SET muted = ?, muted_nr = ?, last_updated = ?, username = ?
                              WHERE email = ?""",
                           (muted_str, muted_count, now_formatted, username, user_email))
        else:
            # Insert new record
            cursor.execute("""INSERT INTO UserReportingActivity 
                              (email, twitter_id, username, muted, muted_nr, last_updated) 
                              VALUES (?, ?, ?, ?, ?, ?)""",
                           (user_email, twitter_id, username, muted_str, muted_count, now_formatted))

        conn.commit()  # Commit the changes to the database
        print(f"Updated database for user: {user_email}")

    except sqlite3.Error as e:  # Catching any SQLite database operation errors
        print(f"Database error: {e}")
    finally:
        conn.close()  # Close the database connection


# The `main` function serves as the central control for executing the main functionality of the script.
#
# It follows # these steps:
# 1. Retrieve the path to the SQLite database using `get_database_path`.
# 2. Lists all user emails from the database using `list_user_emails`.
# 3. Prompts the user to select a specific email from the list.
# 4. Retrieve Twitter OAuth credentials for the selected email using `get_twitter_credentials`.
# 5. Get the Twitter ID associated with the selected email using `get_user_id`.
# 6. Fetches muted accounts for the user from Twitter API using `get_muted_accounts`.
# 7. Updates the database with the retrieved muted accounts using `update_user_reporting_activity`.
# 8. Prints messages to indicate the progress and success of each step.
# 9. Handles exceptions and errors, providing informative error messages when needed.
#
# The script's main functionality is encapsulated within this function, and it serves as the entry point for executing
# the entire process. Exception handling ensures that any issues during execution are appropriately reported.
def main():
    """
    The main function of the script.

    This function orchestrates the process of retrieving muted accounts for a selected user and updating the database.
    It involves several steps:

    1. Retrieving the path to the database.
    2. Listing all user emails from the database.
    3. Allowing the user to select a specific email.
    4. Retrieving credentials and the Twitter ID for the selected email.
    5. Fetching the muted accounts from Twitter API for the given Twitter ID.
    6. Updating the database with the retrieved muted accounts.

    Exception handling is used throughout to manage errors and unexpected situations, such as database issues or API
    errors.

    :return:
    """
    try:
        db_path = get_database_path()  # Retrieve the path to the SQLite database
        emails = list_user_emails(db_path)  # Get a list of user emails from the database

        # Prompt the user to select an email
        for idx, email in enumerate(emails, start=1):
            print(f"{idx}. {email}")
        choice = int(input("Select a user by entering the number: "))
        user_email = emails[choice - 1]

        print(f"Retrieving credentials for {user_email}...")
        credentials = get_twitter_credentials(db_path, user_email)  # Retrieve Twitter OAuth credentials

        if credentials:
            user_id = get_user_id(db_path, user_email)  # Get the Twitter ID for the selected user
            if user_id:
                print(f"Retrieving muted accounts for Twitter ID {user_id}...")
                muted_accounts = get_muted_accounts(credentials, user_id)  # Fetch muted accounts from Twitter

                if muted_accounts:
                    print("Updating muted accounts in the database...")
                    update_user_reporting_activity(db_path, user_email, user_id, muted_accounts)  # Update the database
                    print("Retrieved and updated muted accounts successfully.")
                else:
                    print("No muted accounts found or an error occurred during retrieval.")
            else:
                print(f"Twitter ID not set for the selected user: {user_email}")
        else:
            print("Failed to retrieve credentials.")

    except Exception as e:
        print(f"An error occurred: {e}")


# Main execution
if __name__ == "__main__":
    main()
