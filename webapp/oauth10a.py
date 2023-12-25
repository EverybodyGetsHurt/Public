# Standard and third-party libraries are imported to provide necessary functionalities for OAuth implementation,
# web application handling, and database operations. These imports lay the foundation for various features such as
# JSON handling, URL parsing, cryptographic functions, logging, OAuth authentication, Flask web framework utilities,
# and database interaction.

# Specifically: - 'json', 'urllib.parse', 'base64', 'hashlib', 'logging', and 'secrets' are standard libraries used
# for data encoding, logging, and security purposes. - 'Datetime', 'timedelta', 'wraps', and 'GeneratorType' provide
# date/time handling, decorator creation, and type checking. - 'Oauth2', 'flask', 'flask_login', and 'sqlalchemy' are
# third-party libraries essential for OAuth processes, web server setup, user session management, and database
# interaction. - Local imports from '.error', '.models', '.oauth10areport', and 'instance.config' integrate custom
# error handling, database models, specific functionalities, and configuration settings into the application.
import base64  # For base64 encoding, commonly used in OAuth.
import hashlib  # To hash data, such as in PKCE (Proof Key for Code Exchange).
import json  # For JSON encoding and decoding.
import logging  # For logging information and errors.
import secrets  # For generating cryptographically strong random numbers, such as tokens.
import urllib.parse  # To parse URLs and query strings.
from datetime import datetime, timedelta, timezone  # For handling date and time.
from functools import wraps  # To create decorators.
from types import GeneratorType  # To identify generator types.

# Third-party imports for OAuth and Flask.
import oauth2 as oauth
from flask import (Flask, Blueprint, render_template, request, url_for, session, flash, redirect)
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

# Local application imports
from instance.config import (API_AKA_CONSUMER_KEY, API_AKA_CONSUMER_KEY_SECRET, REQUEST_TOKEN_URL,
                             ACCESS_TOKEN_URL, AUTHORIZE_URL)  # OAuth's configuration.
# Local application imports for handling errors and database interaction.
from .error import TwitterAPIError
from .models import db, OAuth10a, User  # Database models including the OAuth10a model.
from .oauth10areport import impersonatingusers  # Function to report impersonating users.

# The logging setup ensures that all critical information and errors are recorded to a log file.
# This is vital for monitoring the application's behavior, troubleshooting issues, and maintaining a record
# of events for audit and analysis purposes. The specified format includes timestamps, log severity levels,
# and the message content.
logging.basicConfig(filename='/home/benemortasia/benemortasia/oauth1.0a-logfile.log', level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(message)s')

# Dictionary to temporarily store OAuth tokens and secrets during sessions.
oauth_store = {}

# Initializing the main Flask application and a specific Blueprint for OAuth 1.0a routes. The Flask app is configured
# with settings from a configuration file, and a secret key is set for secure session handling. The Blueprint
# 'oauth10a' is used to organize and register routes related to OAuth 1.0a processes, enhancing the modularity and
# maintainability of the application.
app = Flask(__name__, instance_relative_config=True)
app.config.from_pyfile('config.py', silent=True)
app.secret_key = app.config['API_AKA_CONSUMER_KEY_SECRET']
oauth10a = Blueprint('oauth10a', __name__)


# The needs_token_refresh decorator is used to ensure that the OAuth token is refreshed
# automatically if it's older than 30 days. It's applied to routes that require OAuth token for API access.
# 30 days is a common practice for token expiration, ensuring that tokens are not overly exposed to potential misuse.
# The 'oauth_instance' is expected to be a part of the kwargs when the decorated function is called.
def refresh_oauth_token(oauth_instance):
    # A placeholder for OAuth token refresh logic
    # And implement your token refresh logic here.
    # For example, you might need to send a request to the OAuth server to refresh the token
    # and then update the oauth_instance with the new token details.
    return oauth_instance


# The 'refresh_oauth_token' function and 'needs_token_refresh' decorator are designed to handle the automatic refreshing
# of Expired OAuth tokens. This is crucial to ensure continuous access to resources protected by OAuth,
# as tokens typically have an expiration date for security reasons.
def needs_token_refresh():
    # The decorator 'needs_token_refresh' is applied to routes requiring up-to-date OAuth tokens. It checks if the
    # token is older than 30 days and refreshes it if necessary, leveraging the 'refresh_oauth_token' function. This
    # approach automates the token refresh process, reducing the risk of using expired tokens and improving user
    # experience.
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            # Check if the OAuth token needs to be refreshed.
            if kwargs.get('oauth_instance') and kwargs.get('oauth_instance').last_token_refresh_date:
                thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
                if kwargs.get('oauth_instance').last_token_refresh_date < thirty_days_ago:
                    # Refresh the OAuth token
                    kwargs['oauth_instance'] = refresh_oauth_token(kwargs.get('oauth_instance'))
            return view_func(*args, **kwargs)

        return wrapped

    return decorator


# The defined routes (such as '/oauth10aindex', '/oauth10acallback', '/oauth10areportimpersonators')
# are part of the OAuth 1.0a authentication and reporting process. They handle various stages of OAuth authentication,
# from initiating the process, handling callbacks with authentication data, to reporting potential impersonators.
@login_required
# The '@login_required' decorator ensures that these routes are only accessible to users authenticated.
# Adding a layer of security and user-specific context to the operations.
@oauth10a.route('/oauth10aindex')
def oauth10aindex():
    # This route is responsible for initiating the OAuth 1.0a authentication process. It generates a request token
    # and redirects the user to the Twitter authorization URL where they can grant access to the application.

    # The callback URL for the application is generated, ensuring it uses HTTPS for enhanced security.
    app_callback_url = url_for('oauth10a.oauth10acallback', _external=True, user=current_user, _scheme="https")
    # The OAuth consumer is created using the application's consumer key and secret.
    consumer = oauth.Consumer(API_AKA_CONSUMER_KEY, API_AKA_CONSUMER_KEY_SECRET)
    client = oauth.Client(consumer)
    # A request is made to Twitter's request token URL to obtain a request token.
    resp, content = client.request(REQUEST_TOKEN_URL, "POST", body=urllib.parse.urlencode({
        "oauth10a.oauth10acallback": app_callback_url}))
    # If the request is unsuccessful, a TwitterAPIError is raised with the HTTP status code.
    if resp['status'] != '200':
        raise TwitterAPIError(int(resp['status']))
    # The content of the response is parsed to extract the request token and secret.
    request_token = dict(urllib.parse.parse_qsl(content))
    try:
        oauth_token = request_token[b'oauth_token'].decode('utf-8', 'ignore')
        oauth_token_secret = request_token[b'oauth_token_secret'].decode('utf-8', 'ignore')
    except UnicodeDecodeError as e:
        # This specific error is caught to handle scenarios where the decoding of the OAuth token or secret fails.
        # It's essential to diagnose why this error might be occurring as it could potentially halt the OAuth process.
        logging.error(f"Unicode decode error: {str(e)}")
        return render_template('error.html', error_message="Unicode decode error", user=current_user)
    # The request token secret is hashed and stored.
    oauth_secret_hash = generate_password_hash(oauth_token_secret)
    oauth_store[oauth_token] = oauth_secret_hash
    # The request token secret is also stored in the user's session.
    session['oauth_token_secret'] = oauth_token_secret
    # Log debugging information including the request token and callback URL.
    logging.debug(f"Request Token: {request_token}")
    logging.debug(f"App Callback URL: {app_callback_url}")
    # The user is redirected to the Twitter authorization URL with the request token included in the query parameters.
    return render_template('oauth10aindex.html', authorize_url=AUTHORIZE_URL, oauth_token=oauth_token,
                           request_token_url=REQUEST_TOKEN_URL, user=current_user, app_callback_uri=app_callback_url)


@login_required
@oauth10a.route('/oauth10acallback')
def oauth10acallback():
    if current_user.is_authenticated:
        email = current_user.email
    else:
        email = None

    oauth_token = request.args.get('oauth_token')
    oauth_verifier = request.args.get('oauth_verifier')
    oauth_denied = request.args.get('denied')

    if oauth_denied:
        if oauth_denied in session:
            del session[oauth_denied]
        return render_template('error.html', error_message="OAuth request was denied", user=current_user)

    if not oauth_token or not oauth_verifier:
        return render_template('error.html', error_message="Callback parameters missing", user=current_user)

    oauth_token_secret = session.get('oauth_token_secret')
    if not oauth_token_secret:
        return render_template('error.html', error_message="Missing OAuth token secret", user=current_user)

    consumer = oauth.Consumer(API_AKA_CONSUMER_KEY, API_AKA_CONSUMER_KEY_SECRET)
    token = oauth.Token(oauth_token, oauth_token_secret)
    token.set_verifier(oauth_verifier)
    client = oauth.Client(consumer, token)

    resp, content = client.request(ACCESS_TOKEN_URL, "POST")
    if resp['status'] != '200':
        return render_template('error.html', error_message="Error obtaining access token", user=current_user)

    access_token_data = dict(urllib.parse.parse_qsl(content.decode('utf-8')))
    real_oauth_token = access_token_data.get('oauth_token')
    real_oauth_token_secret = access_token_data.get('oauth_token_secret')

    token = oauth.Token(key=real_oauth_token, secret=real_oauth_token_secret)
    client = oauth.Client(consumer, token)
    resp, content = client.request('https://api.twitter.com/1.1/account/verify_credentials.json', "GET")

    if resp.status != 200:
        return render_template('error.html', error_message="Error fetching user data", user=current_user)

    response_data = json.loads(content.decode('utf-8'))
    screen_name = response_data.get('screen_name', 'Unknown')
    user_id = response_data.get('id_str', 'Unknown')

    # Check and update or create OAuth10a record
    existing_oauth_record = OAuth10a.query.filter_by(email=email).first()
    if existing_oauth_record:
        existing_oauth_record.twitter_id = user_id
        existing_oauth_record.account_name = screen_name
        existing_oauth_record.oauth_token = real_oauth_token
        existing_oauth_record.oauth_token_secret = real_oauth_token_secret
        existing_oauth_record.oauth_verifier = oauth_verifier
    else:
        new_oauth_record = OAuth10a(
            email=email,
            twitter_id=user_id,
            account_name=screen_name,
            oauth_token=real_oauth_token,
            oauth_token_secret=real_oauth_token_secret,
            oauth_verifier=oauth_verifier,
            date_created=datetime.now(timezone.utc)
        )
        db.session.add(new_oauth_record)

    # Check and update or create User record
    existing_user_record = User.query.filter_by(email=email).first()
    if not existing_user_record:
        new_user = User(
            email=email,
            twitter_id=user_id,
            account_name=screen_name,
            # Additional fields like password, etc.
        )
        db.session.add(new_user)
    else:
        existing_user_record.twitter_id = user_id
        existing_user_record.account_name = screen_name

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        # Log error and display an error message
        return render_template('error.html', error_message="Database error", user=current_user)

    # Generate code verifier and challenge for PKCE
    code_verifier = ''.join(secrets.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~') for _ in range(128))
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).decode().rstrip('=')
    state = secrets.token_hex(128)

    session['code_verifier'] = code_verifier
    session['state'] = state

    authorization_url = (
        f"https://twitter.com/i/oauth2/authorize"
        f"?response_type=code"
        f"&client_id={app.config['CLIENT_ID_AKA_CONSUMER_KEY']}"
        f"&redirect_uri={app.config['REDIRECT_URI']}"
        f"&scope=tweet.read users.read mute.read mute.write block.read block.write offline.access"
        f"&state={state}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
    )

    return render_template(
        'oauth10acallback.html',
        screen_name=screen_name,
        user_id=user_id,
        name=response_data.get('name', 'Unknown'),
        friends_count=response_data.get('friends_count', 'Unavailable'),
        statuses_count=response_data.get('statuses_count', 'Unavailable'),
        followers_count=response_data.get('followers_count', 'Unavailable'),
        user=current_user,
        email=email,
        authorization_url=authorization_url
    )


# This function handles any IntegrityError exceptions that might occur during the process of adding and committing
# a new OAuth10a object to the database. It checks for specific unique constraint violations and updates the
# existing database record accordingly.
def handle_integrity_error(e, set_to_database):
    # Rollback the session to a clean state after an exception occurs
    db.session.rollback()
    # Convert the exception message to a string to search for specific errors
    error_message = str(e)
    # Check if the error message contains a specific unique constraint violation for the oauth_token_secret
    if "UNIQUE constraint failed: oauth10a.oauth_token_secret" in error_message:
        # Update the existing database entry with the new information
        update_existing_entry(set_to_database)
    # Check if the error message contains a unique constraint violation for the twitter_id
    elif 'UNIQUE constraint failed: oauth10a.twitter_id' in error_message:
        # Update the existing record with the new information and store the previous account information
        update_existing_record(set_to_database)
    else:
        # If the error doesn't match the expected unique constraint violations, render an error template
        return render_template('error.html', error_message=error_message, user=current_user)


# This function is specifically for updating the OAuth token information in the database when a unique
# constraint violation is detected, ensuring that the user’s OAuth tokens are always up-to-date.

# This function is specifically for updating the OAuth token information in the database when a unique
# constraint violation is detected, ensuring that the user’s OAuth tokens are always up-to-date.
def update_existing_entry(set_to_database):
    """
    This function, 'update_existing_entry', is designed to update OAuth token information in the database for an
    existing entry. It's particularly useful when a unique constraint violation occurs, indicating that an attempt
    was made to insert a duplicate record. This scenario is common in OAuth workflows where tokens may need to be
    refreshed or updated.

    :param set_to_database: An instance of the OAuth10a model, containing the new OAuth data that needs to be updated
    in the database.

    Process: 1. Query the database for an existing OAuth10a entry that matches both the oauth_token and
    oauth_token_secret from the 'set_to_database' instance. This step is crucial to identify the specific record that
    needs to be updated. 2. If such an entry exists, it means that the OAuth token already exists in the database but
    needs to be updated with new information (like a refreshed token or a new verifier). 3. The function then updates
    various fields of the existing database entry with the new data from 'set_to_database'. This includes the
    oauth_verifier, account_name, oauth_token, and oauth_token_secret. These updates ensure that the database entry
    reflects the most current state of the OAuth token. 4. The date_created field in the existing entry is also
    updated to reflect the date when the new token information was set. 5. Additionally, the last_token_refresh_date
    is set to the current datetime. This field is critical for tracking when the token was last refreshed,
    which is an essential part of managing OAuth tokens' lifecycle. 6. Finally, the changes are committed to the
    database, making the update effective immediately.

    Importance:
    - Ensures that the database always has the latest OAuth token information, which is crucial for maintaining
      a secure and functional OAuth implementation.
    - Helps in avoiding issues related to expired or stale OAuth tokens by ensuring that the latest token data is
      always stored and used.
    - Aids in maintaining data integrity in the database by preventing duplicate records and resolving unique
      constraint violations efficiently.
    """
    existing_entry = OAuth10a.query.filter_by(
        oauth_token_secret=set_to_database.oauth_token_secret,
        oauth_token=set_to_database.oauth_token
    ).first()
    if existing_entry:
        # Update the existing record with the new data.
        existing_entry.oauth_verifier = set_to_database.oauth_verifier
        existing_entry.account_name = set_to_database.account_name
        existing_entry.oauth_token = set_to_database.oauth_token
        existing_entry.oauth_token_secret = set_to_database.oauth_token_secret
        existing_entry.date_created = set_to_database.date_created
        # Update the last token refresh date to the current time.
        existing_entry.last_token_refresh_date = datetime.now(timezone.utc)

        # Commit the changes to the database.
        db.session.commit()


# This function is for updating the user's record when a unique constraint violation on twitter_id is detected.
# It keeps the history of the user’s previous Twitter account information for reference.
def update_existing_record(set_to_database):
    """
    Updates an existing OAuth10a record in the database when a unique constraint violation on twitter_id is detected.
    This function serves two main purposes: 1. It maintains the integrity of the database by ensuring that each
    Twitter ID is associated with only one record. 2. It preserves a history of the user's previous Twitter account
    information, which can be useful for tracking changes over time or auditing purposes.

    :param set_to_database: An instance of OAuth10a containing the updated information to be saved.
    """
    existing_record = OAuth10a.query.filter_by(twitter_id=set_to_database.twitter_id).first()  # Updated this line
    if existing_record:
        # Check if the twitter_id of the existing record is different from the new data.
        # If so, it indicates that the user's Twitter ID has changed, and the previous data should be archived.
        if existing_record.twitter_id != set_to_database.twitter_id:  # Updated this line
            # Create a dictionary to store the previous state of the record.
            previous_info = {
                "twitter_id": existing_record.twitter_id,  # Updated this line
                "account_name": existing_record.account_name,
                "oauth_token": existing_record.oauth_token,
                "oauth_token_secret": existing_record.oauth_token_secret,
                "oauth_verifier": existing_record.oauth_verifier,
                "date_created": existing_record.date_created.strftime('%Y-%m-%d %H:%M:%S')
            }

            # Check if there is already existing data in the 'previous_twitter_account_info' column.
            # This column is intended to store a history of changes as a JSON array.
            if existing_record.previous_twitter_account_info:
                # Parse the existing JSON data into a Python list.
                existing_data = json.loads(existing_record.previous_twitter_account_info)
                # Append the new historical data to the list.
                if isinstance(existing_data, list):
                    existing_data.append(previous_info)
                else:
                    # If the existing data is not a list (which shouldn't happen in normal circumstances),
                    # create a new list containing the current and new historical data.
                    existing_data = [existing_data, previous_info]
                # Convert the updated list back into JSON format and store it.
                existing_record.previous_twitter_account_info = json.dumps(existing_data)
            else:
                # If there is no existing history, start a new history list with the current historical data.
                existing_record.previous_twitter_account_info = json.dumps([previous_info])

        # Update the record with the new information
        existing_record.twitter_id = set_to_database.twitter_id  # Updated this line
        existing_record.email = set_to_database.email  # Ensuring the email is also updated.
        existing_record.account_name = set_to_database.account_name
        existing_record.oauth_token = set_to_database.oauth_token
        existing_record.oauth_token_secret = set_to_database.oauth_token_secret
        existing_record.oauth_verifier = set_to_database.oauth_verifier
        # Update the last token refresh date to the current time.
        existing_record.last_token_refresh_date = datetime.now(timezone.utc)

        # Commit the changes to the database.
        db.session.commit()


# The oauth10areport route returns a webpage containing a report of the OAuth 1.0a authentication
# and user data retrieved from Twitter.
@login_required
@oauth10a.route('/oauth10areportimpersonators')
def oauth10areport():
    """
    This route, 'oauth10areportimpersonators', serves a web page that presents a report based on OAuth 1.0a
    authentication and user data acquired from Twitter. The function is protected with @login_required, ensuring that
    only authenticated users can access this report.

    The route uses Flask's 'render_template' function to render the 'oauth10areport.html' template. This HTML
    template will be dynamically populated with data passed to it, such as the current user's information. The
    template can display various details such as the authentication status, user details fetched from Twitter,
    and any other relevant data processed in the backend.
    """
    # This route returns a web page containing a report. The exact content and format of the report are
    # determined by the 'oauth10areport.html' template and any data passed to it during rendering.
    return render_template("oauth10areport.html", user=current_user)


# This custom JSON encoder is used to serialize objects into JSON format, especially those that aren’t
# serializable by the default JSON encoder, like generator objects.
class CustomJSONEncoder(json.JSONEncoder):
    """
    CustomJSONEncoder extends the default JSONEncoder to handle serialization of more complex Python objects,
    like generators, which the default encoder cannot serialize. This class overrides the 'default' method of
    JSONEncoder.

    - For generator objects, it first converts them into a list, which is then easily serializable.
    - For other object types, it falls back to the superclasses default serialization method.

    This custom encoder ensures that when JSON encoding is required (for example, sending data via an API or saving
    to a file), the application can handle a wider range of data types without encountering serialization errors.
    """

    def default(self, obj):
        # If the object is a generator, convert it to a list before JSON encoding
        if isinstance(obj, GeneratorType):
            return list(obj)
        # For other types of objects, use the default JSON encoding method
        return super().default(obj)


# The oauth10areportimpersonators route handles the retrieval and display of users who might be impersonating
# a specific Twitter channel. It’s a POST route that receives the impersonated_channel parameter and returns
# the corresponding data.
@login_required
@oauth10a.route('/oauth10areportimpersonators', methods=['POST'])
@needs_token_refresh()
def oauth10areportimpersonators():
    """
    The 'oauth10areportimpersonators' route is designed to process POST requests where the user submits data
    identifying a specific Twitter channel that may be subject to impersonation.

    - It first retrieves the 'impersonated_channel' parameter from the form data.
    - It then calls the 'impersonatingusers' function, passing the channel name. This function is responsible for
      identifying Twitter users potentially impersonating the specified channel. The exact logic of how impersonation
      is determined should be defined within the 'impersonatingusers' function.
    - The response from 'impersonatingusers' is then encoded into JSON format using the custom JSON encoder,
      'CustomJSONEncoder', to handle any complex data types.
    - Finally, it renders the 'oauth10areport.html' template, passing the current user's information and the
      JSON-encoded response data for display.

    The route also uses the @needs_token_refresh() decorator to ensure that the OAuth token is refreshed if necessary,
    maintaining a secure and updated authentication state.
    """
    # Retrieve the 'impersonated_channel' parameter from the form data in the POST request
    impersonated_channel = request.form.get('impersonated_channel')
    # The 'impersonatingusers' function is assumed to return a list of Twitter users who are potentially
    # impersonating the provided channel. The function’s implementation details and how it determines impersonation
    # should be documented within or alongside that function.
    response = impersonatingusers(impersonated_channel)
    # Render the 'oauth10areport.html' template, passing the user and the JSON-encoded response data to be displayed
    return render_template('oauth10areport.html', user=current_user,
                           response=json.dumps(response, cls=CustomJSONEncoder))


# This error handler function is triggered when a TwitterAPIError exception is raised. It captures the error
# and displays an error page with a message describing the error. The HTTP status code from the error is also
# returned as the response’s status code.
@oauth10a.errorhandler(TwitterAPIError)
def handle_twitter_api_error(error):
    """
    This function is a custom error handler for TwitterAPIError exceptions. When such an exception is raised
    within the OAuth10a blueprint context, this handler is invoked.

    - The function captures the TwitterAPIError instance, extracts its message, and the associated HTTP status code.
    - It then renders an 'error.html' template, passing the error message and current user's information. This provides
      a user-friendly way to display error details.
    - The HTTP status code from the error is returned as part of the response, ensuring that the correct HTTP response
      status is communicated to the client.

    This approach centralizes error handling for TwitterAPIError, making the codebase cleaner and error responses
    more consistent.
    """
    return render_template('error.html', error_message=str(error), user=current_user), error.status_code
