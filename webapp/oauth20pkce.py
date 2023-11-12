# Standard library imports: These are Python built-in modules used for various standard operations.
import base64  # Used for encoding binary data into ASCII characters.
import hashlib  # Provides a set of algorithms for cryptographic hashing.
import logging  # Facilitates logging of messages for debugging and system monitoring.
import secrets  # Generates cryptographically strong random numbers for managing secrets.

# Third-party imports: These are modules installed separately, often used for web development and HTTP requests.
from flask import (Flask, Blueprint, render_template, session, request,
                   redirect, url_for, flash)  # Flask modules for web app development.
from flask_login import current_user, login_required  # Flask-Login module for handling user session and authentication.
from sqlalchemy.exc import IntegrityError  # SQLAlchemy module for handling database errors.
import requests  # Module for making HTTP requests.

# Local application imports: These are modules specific to your application, typically for database models.
from .models import db, OAuth20PKCE  # Importing database and model related classes.
from sqlalchemy.sql import func  # SQLAlchemy's func module is used for SQL functions.

# Initializing the Flask application instance with instance_relative_config set to True.
# This allows the app to load configuration files relative to the instance folder.
app = Flask(__name__, instance_relative_config=True)
app.config.from_pyfile('config.py', silent=True)  # Loading configurations from 'config.py'.
app.secret_key = app.config['API_KEY_SECRET']  # Setting the Flask app's secret key for session management.

# Creating a Blueprint named 'oauth20pkce'.
# Blueprints are used in Flask to organize a group of related views and other code.
# Here, 'oauth20pkce' is designated for handling OAuth 2.0 PKCE related routes.
oauth20pkce = Blueprint('oauth20pkce', __name__)


# A user must be logged in to access this route
@login_required
# Route to start the OAuth 2.0 PKCE flow:
# This part initializes the Flask app and sets up configurations and the secret key.
# It creates a Blueprint for the OAuth 2.0 PKCE flow and sets up the first route for starting the OAuth flow.
# When the user accesses this route, a code verifier and challenge are generated and stored,
# and the user is redirected to the OAuth provider's authorization URL.
@oauth20pkce.route('/oauth20pkceindex')  # Maps the URL '/oauth20pkceindex' to this function.
def oauth20pkce_index():
    """
    This route initializes the OAuth 2.0 PKCE authorization flow. It generates a code verifier and challenge,
    and redirects the user to the OAuth provider's (e.g., Twitter) authorization URL.

    The function generates a unique 'code_verifier' and a corresponding 'code_challenge' for each OAuth flow.
    It also generates a 'state' value for CSRF protection. These values are stored in the user's session
    and used in subsequent steps of the OAuth flow.
    """

    # Generating a code verifier and challenge for the OAuth 2.0 PKCE flow. The code verifier is a random
    # string, and the code challenge is derived from it using SHA-256 hashing and base64 encoding.
    # This is part of the OAuth 2.0 PKCE extension to enhance the security of the authorization flow.
    code_verifier = ''.join(
        secrets.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~') for _ in range(64))
    code_challenge = base64.urlsafe_b64encode(hashlib.sha3_512(code_verifier.encode()).digest()).decode().rstrip('=')

    # The state parameter is a unique token generated for each authorization request.
    # This is used to prevent CSRF attacks by ensuring that the response to the authorization request
    # comes from the intended user and session.
    state = secrets.token_hex(16)

    # Storing the generated code verifier and state in the user's session.
    # This is important for validating the response in the callback step of the OAuth flow.
    session['code_verifier'] = code_verifier
    session['state'] = state

    # Logging the generated code verifier and challenge for debugging and monitoring purposes.
    logging.info(f"Code Verifier: {code_verifier}")
    logging.info(f"Code Challenge: {code_challenge}")

    # Constructing the authorization URL to redirect the user to the OAuth provider's authorization endpoint.
    # This URL includes parameters like the client ID, redirect URI, required scopes, state, and code challenge.
    authorization_url = (
        f"https://twitter.com/i/oauth2/authorize"
        f"?response_type=code"
        f"&client_id={app.config['CLIENT_ID']}"
        f"&redirect_uri={app.config['REDIRECT_URI']}"
        f"&scope=tweet.read users.read mute.read mute.write block.read block.write offline.access"
        f"&state={state}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
    )

    # Logging the complete authorization URL for audit trails and troubleshooting.
    logging.info(f"Authorization URL: {authorization_url}")

    # Rendering a template that displays the OAuth authorization link to the user.
    # This template will also show the current user's information if they are logged in.
    return render_template('oauth20pkceindex.html', authorization_url=authorization_url, user=current_user)


# A user must be logged in to access this route
@login_required
# Route to handle the callback from the OAuth 2.0 authorization server
# This route handles the callback from the OAuth 2.0 authorization server. It checks if the user is authenticated
# and handles errors, validates the state parameter, and exchanges the authorization code for an access token.
# It then uses this token to retrieve the user's information and handles the response accordingly,
# either updating an existing user's data or creating a new user record.
@login_required  # Ensures that only authenticated users can access this route.
@oauth20pkce.route('/oauth20pkcecallback')  # Maps the URL '/oauth20pkcecallback' to this function.
def oauth20pkcecallback():
    """
    The 'oauth20pkcecallback' function serves as the callback endpoint for the OAuth 2.0 PKCE flow. It is executed
    after the user authorizes the application on the OAuth 2.0 authorization server. This function primarily
    handles the exchange of an authorization code for an access token and uses this token to retrieve the user's
    information from the OAuth server.

    The function follows these steps:
    1. Validates the current user's authentication status.
    2. Handles any errors returned by the OAuth server.
    3. Retrieves and validates the authorization code and state from the callback query parameters.
    4. Exchanges the authorization code for an access token.
    5. Retrieves the user's information using the access token.
    6. Updates or creates a user record in the database with the retrieved information.
    """

    # This block checks if the current user is authenticated using Flask-Login's current_user proxy.
    # If authenticated, the user's email is retrieved for later use. Otherwise, email is set to None.
    if current_user.is_authenticated:
        email = current_user.email
    else:
        email = None

    # Error handling for OAuth errors. If any error is returned in the query parameters from the
    # OAuth server, it is logged, and the user is redirected to an error page.
    error = request.args.get('error')
    if error:
        app.logger.error(f'Authorization failed: {error}')
        flash('Authorization failed', 'danger')
        return redirect(url_for('unauth.unauthhome'))

    # Retrieving the authorization code and state from the query parameters of the callback URL.
    # These are essential for the PKCE flow, where the code is exchanged for an access token, and
    # the state is used to mitigate CSRF attacks.
    code = request.args.get('code')
    state = request.args.get('state')
    app.logger.info(f"Received code: {code}")
    app.logger.info(f"Received state: {state}")

    # Validating the state parameter against the value stored in the user's session.
    # This is a crucial security measure to prevent CSRF attacks.
    if state != session.get('state'):
        app.logger.warning('Invalid state parameter')
        flash('Invalid state parameter', 'danger')
        return redirect(url_for('unauth.unauthabout'))

    # Retrieving the code verifier from the user's session. This verifier was previously generated
    # and stored in the session during the initial phase of the OAuth 2.0 PKCE flow.
    code_verifier = session.get('code_verifier')
    app.logger.info(f"Code Verifier from session: {code_verifier}")

    # Handling cases where the code verifier is not found or invalid.
    # This is a critical part of the PKCE flow, as the code verifier ensures the security of the code exchange process.
    if not code_verifier:
        app.logger.warning('Invalid code verifier')
        flash('Invalid code verifier', 'danger')
        return redirect(url_for('unauth.unauthhome'))

    # Setting up the request to the OAuth server's token endpoint to exchange the authorization code
    # for an access token. This process is secured by including the previously stored code verifier.
    # The request includes necessary headers and data, such as the client credentials, grant type, code,
    # redirect URI, and the code verifier.
    token_url = 'https://api.twitter.com/2/oauth2/token'
    credentials = base64.urlsafe_b64encode(
        f"{app.config['CONSUMER_KEY']}:{app.config['CONSUMER_SECRET']}".encode()
    ).decode()
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': f'Basic {credentials}'
    }
    data = {
        'client_id': app.config['CONSUMER_KEY'],
        'client_secret': app.config['CONSUMER_SECRET'],
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': app.config['REDIRECT_URI'],
        'code_verifier': code_verifier
    }
    app.logger.info(f"Token request headers: {headers}")
    app.logger.info(f"Token request data: {data}")

    # Sending the POST request to the token endpoint. The response is checked for a successful status code.
    # If the response indicates a failure, an error is logged, and the user is redirected.
    response = requests.post(token_url, headers=headers, data=data)
    if response.status_code != 200:
        app.logger.error(f'Failed to exchange authorization code for access token: {response.text}')
        flash(f"Authorization failed: {response.text}", 'danger')
        return redirect(url_for('unauth.unauthhome'))

    # Parsing the response to extract the access token. This token is then used to fetch the user's information
    # from the OAuth server. The headers for this request include the Bearer token authorization.
    token_data = response.json()
    headers = {
        'Authorization': f"Bearer {token_data['access_token']}"
    }
    user_info_url = 'https://api.twitter.com/2/users/me'
    user_response = requests.get(user_info_url, headers=headers)

    app.logger.info(f"Access Token: {token_data['access_token']}")
    app.logger.info(f"User info response status: {user_response.status_code}")
    app.logger.info(f"User info response headers: {user_response.headers}")
    app.logger.info(f"User info response text: {user_response.text}")

    # Handling unsuccessful requests for user information.
    if user_response.status_code != 200:
        app.logger.error(f'Failed to retrieve user information: {user_response.text}')
        flash('Failed to retrieve user information', 'danger')
        return redirect(url_for('unauth.unauthhome'))

    # Parsing the user information response. This data is used to either update an existing user's record
    # or create a new user in the application's database.
    user_data = user_response.json()

    # Searching for an existing user in the database by email.
    existing_user = OAuth20PKCE.query.filter_by(email=email).first()

    # If an existing user is found, their record is updated. Otherwise, a new user record is created.
    if existing_user:
        # Update logic for existing user record.
        existing_user.account_name = user_data['data']['name']
        existing_user.access_token = token_data['access_token']
        existing_user.refresh_token = token_data.get('refresh_token', existing_user.refresh_token)
        existing_user.state = state
        existing_user.code_verifier = code_verifier
        existing_user.twitter_id = user_data['data']['id']
        existing_user.last_token_refresh_date = func.now()
        db.session.commit()
        flash('Authorization successful', 'success')
        return render_template("oauth20pkcecallback.html", user_data=user_data, user=current_user, email=email)
    else:
        # Logic for creating a new user record.
        oauth_record = OAuth20PKCE(
            email=email,
            account_name=user_data['data']['name'],
            access_token=token_data['access_token'],
            refresh_token=token_data.get('refresh_token'),
            state=state,
            code_verifier=code_verifier,
            twitter_id=user_data['data']['id'],
            # Additional fields can be added as needed.
        )

        # Attempting to add the new user record to the database.
        try:
            db.session.add(oauth_record)
            db.session.commit()
            flash('Authorization successful', 'success')
            return render_template("oauth20pkcecallback.html", user_data=user_data, user=current_user, email=email)
        except IntegrityError as e:
            # Handling database errors, particularly related to unique constraint violations.
            db.session.rollback()
            if "UNIQUE constraint failed: OAuth20_PKCE.twitter_id" in str(e):
                flash('This Twitter ID is already registered with another account.', 'error')
            else:
                flash('An error occurred. Please try again.', 'error')
            return redirect(url_for('unauth.unauthhome'))
