# Standard library imports
import json
import logging
import urllib.parse
from datetime import datetime, timedelta
from functools import wraps
from types import GeneratorType

# Third-party imports
import oauth2 as oauth
from flask import (Flask, Blueprint, render_template, request, url_for, session)
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

# Local application imports
from .error import all_the_error_cries, TwitterAPIError
from .models import db, OAuth10a
from .oauth10areport import impersonatingusers
from instance.config import (APP_CONSUMER_KEY, APP_CONSUMER_SECRET, REQUEST_TOKEN_URL,
                             ACCESS_TOKEN_URL, AUTHORIZE_URL, SHOW_USER_URL)


# A log file is configured to record debug and error information, aiding in monitoring and troubleshooting.
logging.basicConfig(filename='/home/everybodygetshurt/everybodygetshurt/oauth1.0a-logfile.log', level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(message)s')

# oauth_store is a dictionary that temporarily holds OAuth tokens and secrets for ongoing sessions.
oauth_store = {}

# Flask application and Blueprint initialization
app = Flask(__name__, instance_relative_config=True)
app.config.from_pyfile('config.py', silent=True)
app.secret_key = app.config['API_KEY_SECRET']
oauth10a = Blueprint('oauth10a', __name__)


# The needs_token_refresh decorator is used to ensure that the OAuth token is refreshed
# automatically if it's older than 30 days. It's applied to routes that require OAuth token for API access.
# 30 days is a common practice for token expiration, ensuring that tokens are not overly exposed to  potential misuse.
# The 'oauth_instance' is expected to be a part of the kwargs when the decorated function is called.
def refresh_oauth_token(oauth_instance):
    # Placeholder for OAuth token refresh logic
    # Implement your token refresh logic here
    # For example, you might need to send a request to the OAuth server to refresh the token
    # and then update the oauth_instance with the new token details.
    return oauth_instance


# This decorator function is used to refresh OAuth tokens when they are expired.
# It should be applied to any route where an OAuth token is required for accessing an API.
def needs_token_refresh():
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            # Check if the OAuth token needs to be refreshed
            if kwargs.get('oauth_instance') and kwargs.get('oauth_instance').last_token_refresh_date:
                thirty_days_ago = datetime.utcnow() - timedelta(days=30)
                if kwargs.get('oauth_instance').last_token_refresh_date < thirty_days_ago:
                    # Refresh the OAuth token
                    kwargs['oauth_instance'] = refresh_oauth_token(kwargs.get('oauth_instance'))
            return view_func(*args, **kwargs)

        return wrapped

    return decorator


# The oauth10aindex route initiates the OAuth 1.0a authentication process. It creates a request token
# and redirects the user to Twitter's authorization URL.
@login_required
@oauth10a.route('/oauth10aindex')
def oauth10aindex():
    # This route is responsible for initiating the OAuth 1.0a authentication process. It generates a request token
    # and redirects the user to the Twitter authorization URL where they can grant access to the application.

    # The callback URL for the application is generated, ensuring it uses HTTPS for enhanced security.
    app_callback_url = url_for('oauth10a.oauth10acallback', _external=True, user=current_user, _scheme="https")
    # The OAuth consumer is created using the application's consumer key and secret.
    consumer = oauth.Consumer(APP_CONSUMER_KEY, APP_CONSUMER_SECRET)
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


# The oauth10acallback route handles the callback from Twitter after the user has either authorized or denied access.
# It processes the OAuth tokens and other details from the callback and either proceeds with accessing the user's data
# or handles the denial.
@login_required
@oauth10a.route('/oauth10acallback')
def oauth10acallback():
    # This route is the callback endpoint that users are redirected to after they have interacted with
    # Twitter’s authorization page. It’s responsible for handling the outcome of the authorization attempt,
    # capturing the OAuth tokens and other details if the authorization was successful, or dealing with the
    # denial if the user did not authorize the application.

    # If the current user is authenticated, retrieve their email; otherwise, set email to None.
    if current_user.is_authenticated:
        email = current_user.email
    else:
        email = None

    # Retrieve the OAuth token, verifier, and denied status from the request's query parameters.
    oauth_token = request.args.get('oauth_token')
    oauth_verifier = request.args.get('oauth_verifier')
    oauth_denied = request.args.get('denied')

    # If the user denied the request, clean up the session and render an error message to inform the user
    # that their OAuth request was denied.
    if oauth_denied:
        if oauth_denied in session:
            del session[oauth_denied]
        return render_template('error.html',
                               error_message="The OAuth request was denied by this user", user=current_user)
    # If either the OAuth token or verifier is not present in the callback URL, render an error message
    # indicating that these parameters are missing.
    if not oauth_token or not oauth_verifier:
        return render_template('error.html',
                               error_message="Callback param(s) missing", user=current_user)
    # Retrieve the OAuth token secret from the session. If not present, render an error message indicating
    # its absence.
    oauth_token_secret = session.get('oauth_token_secret')
    if not oauth_token_secret:
        return render_template('error.html',
                               error_message="oauth_token_secret not found in session", user=current_user)
    # Create a new OAuth token with the received OAuth token and secret, set its verifier, then make a POST
    # request to exchange the authorized request token for an access token.
    consumer = oauth.Consumer(
        APP_CONSUMER_KEY, APP_CONSUMER_SECRET)
    token = oauth.Token(oauth_token, oauth_token_secret)
    token.set_verifier(oauth_verifier)
    client = oauth.Client(consumer, token)

    resp, content = client.request(ACCESS_TOKEN_URL, "POST")
    access_token = dict(urllib.parse.parse_qsl(content))

    # Decode and extract user information like screen name and user ID from the received access token.
    screen_name = access_token[b'screen_name'].decode('utf-8')
    user_id = access_token[b'user_id'].decode('utf-8')

    # Use the access token to make authenticated requests to the Twitter API.
    real_oauth_token = access_token[b'oauth_token'].decode('utf-8')
    real_oauth_token_secret = access_token[b'oauth_token_secret'].decode('utf-8')

    # Create a new OAuth client with the real tokens to make an authenticated request to retrieve
    # the user’s Twitter profile information.
    real_token = oauth.Token(real_oauth_token, real_oauth_token_secret)
    real_client = oauth.Client(consumer, real_token)
    real_resp, real_content = real_client.request(SHOW_USER_URL + '?user_id=' + user_id, "GET")

    # If the response from the Twitter API is not successful, render an error message with the status code.
    if real_resp['status'] != '200':
        error_message = "Invalid response from Twitter API GET users/show: {status}".format(status=real_resp['status'])
        return render_template('error.html', error_message=error_message, user=current_user)
    # Parse the response content, extracting the user’s Twitter details like friends count, statuses count,
    # and followers count.
    response = json.loads(real_content.decode('utf-8'))

    friends_count = response['friends_count']
    statuses_count = response['statuses_count']
    followers_count = response['followers_count']
    name = response['name']
    # Create a new record with the user's Twitter and OAuth details to be added to the database.
    set_to_database = OAuth10a(
        twitter_id=user_id,
        account_name=screen_name,
        email=email,
        oauth_token=real_oauth_token,
        oauth_token_secret=real_oauth_token_secret,
        oauth_verifier=oauth_verifier,
        date_created=datetime.utcnow()
    )
    # Attempt to add the new record to the database, handling any potential integrity errors that might occur.
    try:
        db.session.add(set_to_database)
        db.session.commit()
    except IntegrityError as e:
        # This block catches any database integrity errors that occur when trying to add new OAuth records. It ensures
        # that unique constraints are maintained, and appropriate updates are made to existing records if needed.
        db.session.rollback()
        error_message = str(e)
        if "UNIQUE constraint failed: oauth10a.oauth_token_secret" in error_message and set_to_database. \
                oauth_token_secret and set_to_database.oauth_token:
            existing_entry = OAuth10a.query.filter_by(oauth_token_secret=set_to_database.oauth_token_secret,
                                                      oauth_token=set_to_database.oauth_token).first()
            if existing_entry:
                existing_entry.oauth_verifier = set_to_database.oauth_verifier
                db.session.commit()

        if 'UNIQUE constraint failed: oauth10a.user_id' in str(e):
            existing_record = OAuth10a.query.filter_by(user_id=set_to_database.user_id).first()
            if existing_record and existing_record.oauth_token_secret == set_to_database.oauth_token_secret \
                    and existing_record.oauth_token == set_to_database.oauth_token:
                existing_record.oauth_verifier = set_to_database.oauth_verifier
                db.session.commit()
    # If all goes well, render the callback page, displaying the user’s Twitter details and the received OAuth tokens.
    return render_template(
        'oauth10acallback.html', screen_name=screen_name, user_id=user_id,
        name=name, friends_count=friends_count, statuses_count=statuses_count,
        followers_count=followers_count, access_token_url=ACCESS_TOKEN_URL, user=current_user,
        email=email)


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
def update_existing_entry(set_to_database):
    existing_entry = OAuth10a.query.filter_by(
        oauth_token_secret=set_to_database.oauth_token_secret,
        oauth_token=set_to_database.oauth_token
    ).first()
    if existing_entry:
        existing_entry.oauth_verifier = set_to_database.oauth_verifier
        existing_entry.account_name = set_to_database.account_name
        existing_entry.oauth_token = set_to_database.oauth_token
        existing_entry.oauth_token_secret = set_to_database.oauth_token_secret
        existing_entry.date_created = set_to_database.date_created
        existing_entry.last_token_refresh_date = datetime.utcnow()  # Added this line
        db.session.commit()


# This function is for updating the user's record when a unique constraint violation on twitter_id is detected.
# It keeps the history of the user’s previous Twitter account information for reference.
def update_existing_record(set_to_database):
    existing_record = OAuth10a.query.filter_by(twitter_id=set_to_database.twitter_id).first()  # Updated this line
    if existing_record:
        # If the twitter_id has changed, store the existing information in the previous_twitter_account_info column
        if existing_record.twitter_id != set_to_database.twitter_id:  # Updated this line
            previous_info = {
                "twitter_id": existing_record.twitter_id,  # Updated this line
                "account_name": existing_record.account_name,
                "oauth_token": existing_record.oauth_token,
                "oauth_token_secret": existing_record.oauth_token_secret,
                "oauth_verifier": existing_record.oauth_verifier,
                "date_created": existing_record.date_created.strftime('%Y-%m-%d %H:%M:%S')
            }

            # If previous_twitter_account_info already contains data, append new data to the list
            if existing_record.previous_twitter_account_info:
                existing_data = json.loads(existing_record.previous_twitter_account_info)
                if isinstance(existing_data, list):
                    existing_data.append(previous_info)
                else:
                    existing_data = [existing_data, previous_info]
                existing_record.previous_twitter_account_info = json.dumps(existing_data)
            else:
                existing_record.previous_twitter_account_info = json.dumps([previous_info])

        # Update the record with the new information
        existing_record.twitter_id = set_to_database.twitter_id  # Updated this line
        existing_record.email = set_to_database.email  # Added this line to ensure email is updated
        existing_record.account_name = set_to_database.account_name
        existing_record.oauth_token = set_to_database.oauth_token
        existing_record.oauth_token_secret = set_to_database.oauth_token_secret
        existing_record.oauth_verifier = set_to_database.oauth_verifier
        existing_record.last_token_refresh_date = datetime.utcnow()  # Added this line
        db.session.commit()


# The oauth10areport route returns a webpage containing a report of the OAuth 1.0a authentication
# and user data retrieved from Twitter.
@login_required
@oauth10a.route('/oauth10areport')
def oauth10areport():
    # This route returns a web page containing a report. The exact content and format of the report are
    # determined by the 'oauth10areport.html' template and any data passed to it during rendering.
    return render_template("oauth10areport.html", user=current_user)


# This custom JSON encoder is used to serialize objects into JSON format, especially those that aren’t
# serializable by the default JSON encoder, like generator objects.
class CustomJSONEncoder(json.JSONEncoder):  # Updated JSONEncoder import here
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
    # Render an error template with the error message and user information, and return the error's status code as
    # the HTTP status code
    return render_template('error.html', error_message=str(error), user=current_user), error.status_code
