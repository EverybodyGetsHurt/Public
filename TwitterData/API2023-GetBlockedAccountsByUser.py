"""
    This script is designed for managing and updating a Twitter user's blocked accounts list through the Twitter API,
    along with maintaining a local SQLite database for these records. It automates the process of fetching data for
    blocked Twitter accounts associated with a specific user and updates this information in a local database.
    The script is user-centric and allows easy management of blocked accounts for selected Twitter accounts.

    Key Features:
    - Retrieves a comprehensive list of all blocked Twitter accounts for a specified user.
    - Seamlessly updates the local SQLite database with the current information on blocked accounts.
    - Employs OAuth 1.0a for secure authentication to access the Twitter API.
    - Conducts various database operations, including fetching, updating, and inserting user-related data.
    - Offers an intuitive interface for users to select a Twitter account based on associated email addresses.

    Workflow:
    1. The script begins by constructing the path to the local SQLite database.
    2. It then lists all user emails from the database, presenting the user with a selection choice.
    3. Upon user selection, the script fetches the corresponding Twitter ID and OAuth credentials from the database.
    4. Using these credentials, it accesses the Twitter API to obtain the list of blocked accounts for the that user ID.
    5. Finally, the script updates the database record for the selected user with the latest list of blocked accounts.
    6. The script includes error handling for database operations and Twitter API responses, ensuring robust execution.

    Important Considerations:
    - The script requires an already set up SQLite database with specific tables and format.
    - It assumes pre-stored OAuth credentials and Twitter IDs in the database.
    - Configuration in 'instance/config.py' for API keys and tokens is necessary for successful execution.
    - The script is designed to respect Twitter API's rate limits and handles pagination for extensive data sets.

    Dependencies:
    - requests: Used for HTTP requests to the Twitter API.
    - requests_oauthlib: For handling OAuth 1.0a authentication.
    - sqlite3: For managing SQLite database operations.
    - os: To handle file and directory operations in a platform-independent manner.
    - datetime: For managing date and time operations.

    This script is tailored for users or developers needing to manage blocked lists for Twitter accounts, providing a
    convenient method to maintain and update these lists in a local database.
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
    Retrieve the Twitter ID associated with a user's email from the SQLite database.

    Args:
        db_path (str): The path to the SQLite database file.
        user_email (str): The email address of the user whose Twitter ID is to be retrieved.

    Returns:
        int or None: The Twitter ID as an integer if found, or None if not found.

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
# consumer secret, OAuth token, and OAuth token secret) from the SQLite database for a given user's email.
#
# This function does the following:
# 1. Establishes a connection to the SQLite database using `sqlite3.connect`.
# 2. Create a cursor object for executing SQL commands.
# 3. Executes an SQL query to fetch the OAuth credentials for the specified user.
# 4. Fetches the credentials from the database and closes the database connection.
# 5. Validates the retrieved consumer key and secret from environment variables.
# 6. Returns the credentials as a tuple containing consumer key, consumer secret, OAuth token, and OAuth token secret.
#
# Exception handling is used to manage potential errors during database operations and credential validation.
#
# This function is essential for obtaining the required Twitter OAuth credentials for making API requests.
def get_twitter_credentials(db_path, user_email):
    """
    Retrieve Twitter OAuth 1.0a credentials (consumer key, consumer secret, OAuth token, and OAuth token secret)
    from the SQLite database for a specific user's email.

    Args:
        db_path (str): The path to the SQLite database file.
        user_email (str): The email address of the user whose Twitter credentials are to be retrieved.

    Returns:
        tuple: A tuple containing consumer key (str), consumer secret (str), OAuth token (str), and
               OAuth token secret (str) if found.

    Raises:
        ValueError: If the Twitter consumer key and/or secret are not set in environment variables.
        ValueError: If no credentials are found for the specified email.
        sqlite3.Error: If there's an error in database operations.

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


# Function to retrieve blocked accounts for a Twitter user
#
# The `get_blocked_accounts` function fetches a list of blocked accounts for a specific Twitter user using the
# Twitter API.
#
# This function does the following:
# 1. Constructs the API request URL based on the user's Twitter ID.
# 2. Makes requests to the Twitter API to fetch blocked accounts, with pagination handled until all data is retrieved.
# 3. Parses the API response and extracts the blocked accounts' information.
# 4. Returns a list of blocked accounts in dictionary format.
#
# It also provides information about rate limits and usage considerations for making requests to the Twitter API.
#
# This function is vital for obtaining a user's blocked accounts, which can be used for further processing.
def get_blocked_accounts(credentials, user_id):
    """
    Retrieve a list of blocked accounts for a specific Twitter user using the Twitter API.

    Args:
        credentials (tuple): A tuple containing consumer key (str), consumer secret (str),
                            access token (str), and access token secret (str) for OAuth 1.0a authentication.
        user_id (int): The Twitter user's ID for whom to fetch blocked accounts.

    Returns:
        list: A list of blocked accounts in dictionary format.

    Note:
        This function respects Twitter API rate limits and handles pagination for extensive data sets.



    Muting Endpoint (GET_2_users_param_muting):

    Rate Limit: 100 requests per 24 hours per user. With each request, you can fetch up to 1000 muted accounts. This
    means, in a 24-hour period, you can make 100 requests, potentially fetching up to 100,000 (100 requests × 1000
    accounts per request) muted account names for a specific user. Blocking Endpoint (GET_2_users_param_blocking):

    Rate Limit: 5 requests per 15 minutes per user. With each request, you can also fetch up to 1000 blocked accounts.
    This means, in every 15-minute window, you can make 5 requests, potentially fetching up to 5,000 (5 requests × 1000
    accounts per request) blocked account names for a specific user. In an hour, this would be 20,000 blocked accounts
    (4 × 15-minute windows), and in a 24-hour period, it would be up to 480,000 (24 hours × 20,000 accounts per hour).
    Therefore, your capacity to request data through the mute endpoint is substantial, allowing you to fetch large
    numbers of muted accounts in a day. For the block endpoint, you have a more frequent opportunity to request data
    but with a smaller number of requests in each window.

    It's important to note that these calculations assume that each request returns the maximum number of accounts
    (1000), which may not always be the case depending on the actual number of muted or blocked accounts associated
    with the user. Also, be aware of the general rate limits on your API key to ensure overall compliant usage.

    :param credentials:
    :param user_id:
    :return:
    """
    # Unpack OAuth 1.0a credentials tuple
    consumer_key, consumer_secret, access_token, access_token_secret = credentials  # Unpack credentials tuple

    # Initialize variables
    all_blocked_accounts = []  # List to store blocked accounts
    next_token = None  # Pagination token for fetching more data

    # Start a loop to handle pagination and fetching blocked accounts
    while True:
        # Construct the Twitter API endpoint URL for fetching blocked accounts with maximum 1000 results per request
        url = f'https://api.twitter.com/2/users/{user_id}/blocking?max_results=1000'

        if next_token:  # If there's a next_token (indicating pagination), add it to the URL
            url += f'&pagination_token={next_token}'

        # Create an OAuth1 authentication object with the credentials
        auth = OAuth1(consumer_key, consumer_secret, access_token, access_token_secret)

        # Make a GET request to the Twitter API to fetch blocked accounts
        response = requests.get(url, auth=auth)  # Make a GET request to the Twitter API to fetch blocked accounts

        if response.status_code == 200:  # Check if the GET request was successful (HTTP status code 200)
            data = response.json()  # Parse the JSON response

            if 'data' in data:  # Check if the response contains 'data' field
                all_blocked_accounts.extend(data['data'])  # Extend the list of blocked accounts with the data received

                # Get the next_token for pagination from the response metadata, or exit the loop
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
            print("Error retrieving blocked accounts:", response.status_code, response.text)
            return None

    # Return the list of blocked accounts after fetching all relevant data
    return all_blocked_accounts


# Function to update user reporting activity with blocked accounts
#
# The `update_user_reporting_activity_for_blocked` function updates the `UserReportingActivity` table in the SQLite
# database with information about a user's blocked accounts. It is a variation of the original
# `update_user_reporting_activity` function, adapted for blocked accounts.
#
# This function does the following:
# 1. Establishes a connection to the SQLite database.
# 2. Retrieve the user's username from the `All_Users` table based on their email.
# 3. Validates that the `blocked_accounts` input is in the correct format.
# 4. Converts the list of blocked accounts into a comma-separated string and counts the number of blocked accounts.
# 5. Check if a record already exists for the user in the `UserReportingActivity` table.
# 6. Formats the current date and time for SQLite storage.
# 7. If a record exists, it updates the existing record with the new blocked accounts and other information.
# 8. If no record exists, it inserts a new record for the user.
# 9. Finally, it commits the changes to the database and prints a message to indicate a successful update.
#
# Exception handling is used to manage potential errors during database operations, and the database connection is
# properly closed in the `finally` block.
#
# This function is crucial for updating the database with a user's blocked accounts.
def update_user_reporting_activity_for_blocked(db_path, user_email, twitter_id, blocked_accounts):
    """
    Update the 'UserReportingActivity' table in the SQLite database with information about a user's blocked accounts.

    Args:
        db_path (str): The path to the SQLite database file.
        user_email (str): The email address of the user.
        twitter_id (int): The Twitter ID associated with the user.
        blocked_accounts (list): A list of blocked accounts in dictionary format.

    Note:
        This function is similar to 'update_user_reporting_activity' but is modified for handling blocked accounts data.

    :param db_path:
    :param user_email:
    :param twitter_id:
    :param blocked_accounts:
    :return:
    """
    # Same as 'update_user_reporting_activity' but with modifications for blocked accounts
    try:
        conn = sqlite3.connect(db_path)  # Establish a connection to the SQLite database
        cursor = conn.cursor()  # Create a cursor object to execute SQL commands

        cursor.execute("SELECT account_name FROM All_Users WHERE email = ?", (user_email,))
        username_result = cursor.fetchone()
        username = username_result[0] if username_result else 'Unknown'

        # Ensure that blocked_accounts is a list of dictionaries before processing
        if not all(isinstance(account, dict) and 'username' in account for account in blocked_accounts):
            raise ValueError("Invalid format for blocked accounts data")

        # Convert usernames to a comma-separated string
        blocked_str = ','.join([account['username'] for account in blocked_accounts])
        blocked_count = len(blocked_accounts)  # Get the number of blocked accounts

        cursor.execute("SELECT * FROM UserReportingActivity WHERE email = ?", (user_email,))
        result = cursor.fetchone()
        now_formatted = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Format the current date and time

        if result:
            # Update the existing record in 'UserReportingActivity' table
            cursor.execute("""UPDATE UserReportingActivity 
                              SET blocked = ?, blocked_nr = ?, last_updated = ?, username = ?
                              WHERE email = ?""",
                           (blocked_str, blocked_count, now_formatted, username, user_email))
        else:
            # Insert a new record in 'UserReportingActivity' table
            cursor.execute("""INSERT INTO UserReportingActivity 
                              (email, twitter_id, username, blocked, blocked_nr, last_updated) 
                              VALUES (?, ?, ?, ?, ?, ?)""",
                           (user_email, twitter_id, username, blocked_str, blocked_count, now_formatted))

        conn.commit()  # Commit the changes to the database
        print(f"Updated database for user: {user_email} with blocked accounts")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()  # Close the database connection


# Main function to perform the user reporting activity update
#
# The `main` function is the entry point of the script. It performs the following steps:
# 1. Retrieve the database path using `get_database_path`.
# 2. Lists user emails using `list_user_emails` and displays them to the user.
# 3. Prompts the user to select a user by entering a number.
# 4. Retrieves Twitter credentials for the selected user using `get_twitter_credentials`.
# 5. Retrieve the Twitter ID for the selected user using `get_user_id`.
# 6. Call `get_blocked_accounts` to fetch blocked accounts.
# 7. Call `update_user_reporting_activity_for_blocked` to update the database with blocked accounts information.
#
# The `main` function handles user interactions and orchestrates the entire process.
def main():
    """
    Main function to retrieve and update blocked accounts data for a user.

    This function interacts with the user to select a user by email, retrieve Twitter credentials,
    fetch blocked accounts, and update the database with the blocked accounts data.

    :return:
    """
    try:
        db_path = get_database_path()  # Get the path to the SQLite database
        emails = list_user_emails(db_path)  # List all user emails from the database

        for idx, email in enumerate(emails, start=1):
            print(f"{idx}. {email}")  # Display a numbered list of user emails
        choice = int(input("Select a user by entering the number: "))  # Prompt user to select a user by number
        user_email = emails[choice - 1]  # Get the selected user's email

        print(f"Retrieving credentials for {user_email}...")  # Print a message about credential retrieval
        credentials = get_twitter_credentials(db_path, user_email)  # Get Twitter credentials for the user

        if credentials:
            user_id = get_user_id(db_path, user_email)  # Get the Twitter ID for the selected user
            if user_id:
                # Print a message about fetching blocked accounts
                print(f"Retrieving blocked accounts for Twitter ID {user_id}...")
                # Fetch blocked accounts using Twitter credentials
                blocked_accounts = get_blocked_accounts(credentials, user_id)

                if blocked_accounts:
                    # Print a message about updating blocked accounts
                    print("Updating blocked accounts in the database...")

                    # Update the database with blocked accounts data
                    update_user_reporting_activity_for_blocked(db_path, user_email, user_id, blocked_accounts)
                    print("Retrieved and updated blocked accounts successfully.")  # Print a success message
                else:
                    # Print a message if no blocked accounts found
                    print("No blocked accounts found or error occurred during retrieval.")
            else:
                # Print an error message if Twitter ID is not set
                print(f"Twitter ID not set for the selected user: {user_email}")
        else:
            print("Failed to retrieve credentials.")  # Print an error message if credentials retrieval failed

    except Exception as e:
        print(f"An error occurred: {e}")  # Print an error message if any exception occurs


if __name__ == "__main__":
    main()  # Execute the main function if the script is run directly
