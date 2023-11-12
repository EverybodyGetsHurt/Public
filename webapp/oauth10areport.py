# requests_oauthlib is a Python library that simplifies OAuth 1 and OAuth 2 authentication for HTTP requests.
# OAuth1Session is specifically used for OAuth 1.0a, a protocol for authenticating API requests.
from requests_oauthlib import OAuth1Session

# Flask is a micro web framework for Python. It provides tools and features to build web applications.
# 'current_app' is a special object in Flask that points to the Flask application handling the current activity.
# 'Blueprint' is a way to organize a Flask application into components, each with its own views and code.
from flask import current_app, Blueprint

# Flask-Login provides user session management for Flask, handling the common tasks of logging in,
# logging out, and remembering users’ sessions over extended periods of time.
# 'login_required' is a decorator to protect views that should only be accessed by logged-in users.
# 'current_user' is a proxy that represents the client-side user.
from flask_login import login_required, current_user

# Importing the User model from the local 'models' module.
# The User model typically encapsulates the database structure for a user entity.
from .models import User

# 'config' is a module that usually contains configuration variables and credentials.
# Importing this module to access such configurations like API keys, database URIs, etc.
from instance import config

# Here, a new Flask Blueprint named 'oauth10areport' is created.
# Blueprints are used in Flask to create modular components in the application.
# '__name__' is a Python special variable that provides the name of the current module.
oauth10areport = Blueprint('oauth10areport', __name__)

# OAuth1Session is assigned to a variable named 'oauth1session'.
# This is done for ease of use in the application and to maintain consistency in naming conventions.
oauth1session = OAuth1Session


# This function, when called, executes several actions against users identified as impersonators on Twitter.
# It uses OAuth for authentication and interacts with Twitter's API to mute, block, and report these users.

@login_required  # Ensures that only authenticated users can access this function.
@oauth10areport.route('/oauth10areportimpersonators')  # Maps the URL '/oauth10areportimpersonators' to this function.
def oauth10areportimpersonators(impersonated_channel, oauth_session):
    """
    This function handles actions against Twitter users identified as impersonators of a specific channel.
    It performs muting, blocking, and reporting operations on these users via the Twitter API.
    Authentication for these operations is managed through OAuth,
    with credentials provided by the application and the user.

    Parameters:
    - impersonated_channel (str):
    The identifier (likely a username or channel name) of the entity being impersonated on Twitter.
    - oauth_session (OAuth1Session):
    An instance of OAuth1Session configured for making authenticated requests to the Twitter API.
    """
    # Function parameters:
    # 'impersonated_channel' - a variable likely representing a specific Twitter channel or user being impersonated.
    # 'oauth_session' - represents an OAuth session, used for making authenticated requests to the Twitter API.

    # Retrieves the current authenticated user's data from the database using their email.
    # 'current_user' is a Flask-Login proxy that represents the client-side user.
    # The 'first()' function is used to get the first result of this query or None if no result is found.
    user = User.query.filter_by(email=current_user.email).first()

    # Initializes variables for OAuth tokens. These tokens are necessary for authenticated requests to Twitter's API.
    oauth10a_token = None
    oauth10a_token_secret = None
    # Checks if the user has OAuth 1.0a tokens stored (necessary for Twitter API authentication).
    if user.oauth10a:
        # Assuming the user has only one set of OAuth 1.0a tokens, the first item in the list is retrieved.
        oauth10a = user.oauth10a[0]
        # Extracting the token and token secret from the retrieved data.
        oauth10a_token = oauth10a.oauth_token
        oauth10a_token_secret = oauth10a.oauth_token_secret

    # Creating an OAuth1Session instance, which is used to make authenticated HTTP requests.
    # This session will be authenticated with the application's consumer key and secret,
    # along with the user's token and token secret.
    oauth = oauth_session(
        config.APP_CONSUMER_KEY,
        client_secret=config.APP_CONSUMER_SECRET,
        resource_owner_key=oauth10a_token,
        resource_owner_secret=oauth10a_token_secret,
    )

    # Opening and reading a file that presumably contains a list of impersonators.
    # The file name is dynamically generated based on the 'impersonated_channel' variable.
    with open(current_app.instance_path + f"\\Active-{impersonated_channel}.txt", "r") as file:
        # The file's content is split on '=' and the second part, which is
        # assumed to be the list of impersonators, is further split by ','.
        contents = file.read().split("=")
        impersonators_list = contents[1].split(",")

    response_list = []  # Initializes a list to collect responses from the Twitter API.

    # Iterates over each identified impersonator to take the necessary actions.
    for impersonator in impersonators_list:
        # The following sections handle muting, blocking, and reporting each impersonator on Twitter.

        # Mute the impersonator.
        # Constructs the URL for the mute endpoint and sends a POST request.
        # Successful and failed attempts are handled separately for better error tracking and response management.
        mute_url = f"https://api.twitter.com/1.1/mutes/users/create.json?screen_name={impersonator}"
        try:
            response = oauth.post(mute_url)
            response.raise_for_status()
            yield f'Muted user with screen name: {impersonator}'
        except Exception as e:
            yield f'Error muting user {impersonator}: {e}'

        # Block the impersonator.
        # Similar to muting, but the request is sent to the block endpoint.
        block_url = f"https://api.twitter.com/1.1/blocks/create.json?screen_name={impersonator}"
        try:
            response = oauth.post(block_url)
            response.raise_for_status()
            yield f'Blocked user with screen name: {impersonator}'
        except Exception as e:
            yield f'Error blocking user {impersonator}: {e}'

        # Report the impersonator as spam.
        # This is a crucial step in combating impersonation on Twitter.
        report_url = f"https://api.twitter.com/1.1/users/report_spam.json?screen_name={impersonator}"
        response = oauth.post(report_url)
        if response.status_code != 200:
            yield f'Request returned an error: {response.status_code} {response.text}'
        else:
            yield f'Reported user with screen name: {impersonator}'

        # The response for each action is converted to JSON and stored in the response list.
        json_response = response.json()
        response_list.append(json_response)

    return response_list  # Returns the aggregated list of responses for all actions taken.


# This function is designed to find and return a list of users impersonating a specific channel.
# It's a placeholder function with a structure similar to 'oauth10areportimpersonators',but its
# full implementation is pending.
def impersonatingusers(impersonated_channel, current_user, oauth_session):
    """
    This function aims to identify and handle users impersonating a specific Twitter channel.
    It is structured to mute, block, and potentially report these impersonating users.
    The function requires the completion of its core logic for identifying impersonators,
    which is expected to be tailored to the specific needs of the application.

    Parameters:
    - impersonated_channel (str): The Twitter channel being impersonated.
    - current_user (User object): The currently authenticated user, typically obtained
                                  through Flask-Login's current_user proxy.
    - oauth_session (OAuth1Session): A configured OAuth1Session for making authenticated
                                     requests to the Twitter API.

    Returns:
    - list: A collection of responses from the Twitter API regarding the actions taken
            against the identified impersonators.
    """
    # Function parameters are similar to 'oauth10areportimpersonators'.
    # 'impersonated_channel' - identifies the channel being impersonated.
    # 'current_user' - represents the logged-in user.
    # 'oauth_session' - for authenticated requests to the Twitter API.

    # The function begins by attempting to retrieve OAuth 1.0a tokens associated with
    # the current user. These tokens are necessary for authenticated interactions
    # with the Twitter API.
    oauth10a_token = None
    oauth10a_token_secret = None
    if current_user.oauth10a:
        # Assuming each user has a single OAuth10a token pair, it retrieves the token
        # and secret. This assumes a one-to-one relationship between users and OAuth tokens.
        oauth10a = current_user.oauth10a[0]
        oauth10a_token = oauth10a.oauth_token
        oauth10a_token_secret = oauth10a.oauth_token_secret

    # Next, the function sets up an OAuth1Session with the necessary credentials.
    # This session will be used for all subsequent requests to the Twitter API, ensuring
    # that each request is properly authenticated.
    oauth = oauth_session(
        config.APP_CONSUMER_KEY,
        client_secret=config.APP_CONSUMER_SECRET,
        resource_owner_key=oauth10a_token,
        resource_owner_secret=oauth10a_token_secret,
    )

    # The function then reads a list of suspected impersonators from a file.
    # The file's name is dynamically constructed using the `impersonated_channel` parameter.
    # The file is expected to be in a specific format where the impersonators' names are
    # listed after an '=' sign, separated by commas.
    with open(current_app.instance_path + f"Active-{impersonated_channel}.txt", "r") as file:
        contents = file.read().split("=")
        impersonators_list = contents[1].split(",")

    response_list = []  # Initializes a list to store responses from the Twitter API.

    # The core of the function is a loop that iterates over each identified impersonator.
    # For each impersonator, the function attempts to mute, block, and report them using
    # the Twitter API. Each of these actions involves sending a POST request to a specific
    # Twitter API endpoint.
    for impersonator in impersonators_list:
        # Mute the impersonator.
        # The mute URL is constructed using the impersonator's screen name.
        # A POST request is then sent to this URL. If successful, a confirmation message is added to the response list.
        # If there's an error (e.g., network issues, invalid response), it's caught and logged.
        mute_url = f"https://api.twitter.com/1.1/mutes/users/create.json?screen_name={impersonator}"
        try:
            response = oauth.post(mute_url)
            response.raise_for_status()  # Checks for HTTP request errors.
            response_list.append(f'Muted user with screen name: {impersonator}')
        except Exception as e:
            response_list.append(f'Error muting user {impersonator}: {e}')

        # Report the impersonator.
        # The reporting process is similar to muting, but it uses a different API endpoint. The response is
        # also checked for non-successful HTTP status codes, indicating potential issues with the request.
        report_url = f"https://api.twitter.com/1.1/users/report_spam.json?screen_name={impersonator}"
        response = oauth.post(report_url)
        if response.status_code != 200:
            response_list.append(f'Request returned an error: {response.status_code}, {response.text}')
        else:
            response_list.append(f'Reported user with screen name: {impersonator}')

        # After each action, the response from the Twitter API is converted to JSON and stored.
        # This allows for later analysis or logging of the actions taken by the function.
        json_response = response.json()
        response_list.append(json_response)

    return response_list  # The function returns the list of responses from the Twitter API.
