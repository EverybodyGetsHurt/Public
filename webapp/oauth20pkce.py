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
@oauth20pkce.route('/oauth20pkcecallback')
def oauth20pkcecallback():
    # The user's email is retrieved from the current_user object provided by Flask-Login.
    if current_user.is_authenticated:
        email = current_user.email
    else:
        email = None  # or handle this case as per your application's requirement

    # Error handling is in place to catch and log any errors that occur during the OAuth process,
    # ensuring a graceful failure that can be diagnosed and corrected.
    error = request.args.get('error')
    if error:
        # Extracting the code and state from the query string
        app.logger.error(f'Authorization failed: {error}')
        flash('Authorization failed', 'danger')
        return redirect(url_for('unauth.unauthhome'))

    code = request.args.get('code')
    # The state parameter returned from the authorization server is validated against the one stored
    # in the user's session to mitigate CSRF attacks.
    state = request.args.get('state')
    app.logger.info(f"Received code: {code}")
    app.logger.info(f"Received state: {state}")

    # If the state parameter from the server matches the one stored in the session, the process continues
    # Otherwise, an error is logged and the user is redirected
    if state != session.get('state'):
        app.logger.warning('Invalid state parameter')
        flash('Invalid state parameter', 'danger')
        return redirect(url_for('unauth.unauthabout'))

    # Retrieving the stored code verifier from the session
    code_verifier = session.get('code_verifier')
    app.logger.info(f"Code Verifier from session: {code_verifier}")
    if not code_verifier:
        app.logger.warning('Invalid code verifier')
        flash('Invalid code verifier', 'danger')
        return redirect(url_for('unauth.unauthhome'))

    # Creating a request to exchange the authorization code for an access token
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

    # The headers and data for the token request are logged for debugging purposes
    app.logger.info(f"Token request headers: {headers}")
    app.logger.info(f"Token request data: {data}")

    # The application exchanges the authorization code for an access token using a POST request,
    # including the code_verifier to satisfy the PKCE requirement.
    response = requests.post(token_url, headers=headers, data=data)

    # If the request is unsuccessful, an error is logged and the user is redirected
    if response.status_code != 200:
        app.logger.error(f'Failed to exchange authorization code for access token: {response.text}')
        flash(f"Authorization failed: {response.text}", 'danger')
        return redirect(url_for('unauth.unauthhome'))

    # The access token and user information are logged for debugging purposes
    token_data = response.json()

    # Using the access token to fetch the user's information
    headers = {
        'Authorization': f"Bearer {token_data['access_token']}"
    }
    user_info_url = 'https://api.twitter.com/2/users/me'
    # The user's information is retrieved from the authorization server using the newly acquired access token.
    user_response = requests.get(user_info_url, headers=headers)

    app.logger.info(f"Access Token: {token_data['access_token']}")
    app.logger.info(f"User info response status: {user_response.status_code}")
    app.logger.info(f"User info response headers: {user_response.headers}")
    app.logger.info(f"User info response text: {user_response.text}")

    # If the request for user information is unsuccessful, an error is logged and the user is redirected
    if user_response.status_code != 200:
        app.logger.error(f'Failed to retrieve user information: {user_response.text}')
        flash('Failed to retrieve user information', 'danger')
        return redirect(url_for('unauth.unauthhome'))

    # Parsing the JSON response to get the user's data
    user_data = user_response.json()

    # Existing users are updated with new tokens and other info, while new users are created as needed,
    # ensuring a smooth and seamless user experience.
    existing_user = OAuth20PKCE.query.filter_by(email=email).first()

    # If a user with the given email already exists, their information is updated
    # Otherwise, a new user record is created
    if existing_user:
        # Update the existing user record with new tokens and other info
        existing_user.account_name = user_data['data']['name']
        existing_user.access_token = token_data['access_token']
        existing_user.refresh_token = token_data.get('refresh_token', existing_user.refresh_token)  # Update if present
        existing_user.state = state
        existing_user.code_verifier = code_verifier
        existing_user.twitter_id = user_data['data']['id']
        existing_user.last_token_refresh_date = func.now()  # Update the last token refresh date
        db.session.commit()
        flash('Authorization successful', 'success')
        return render_template("oauth20pkcecallback.html", user_data=user_data, user=current_user, email=email)
    else:
        # Create and store the OAuth record after processing the callback
        oauth_record = OAuth20PKCE(
            email=email,
            account_name=user_data['data']['name'],
            access_token=token_data['access_token'],
            refresh_token=token_data.get('refresh_token'),  # Store refresh token if present
            state=state,
            code_verifier=code_verifier,
            twitter_id=user_data['data']['id'],
            # Add any other necessary fields
        )

        try:
            # The new OAuth record is added to the database, and the transaction is committed
            db.session.add(oauth_record)
            db.session.commit()

            # A success message is flashed to the user, and they are presented with a webpage displaying their user data
            flash('Authorization successful', 'success')
            return render_template("oauth20pkcecallback.html", user_data=user_data, user=current_user, email=email)
        except IntegrityError as e:
            # If a database error occurs, the transaction is rolled back
            # The user is flashed with an error message and redirected
            db.session.rollback()
            if "UNIQUE constraint failed: OAuth20_PKCE.twitter_id" in str(e):
                flash('This Twitter ID is already registered with another account.', 'error')
            else:
                flash('An error occurred. Please try again.', 'error')
            return redirect(url_for('unauth.unauthhome'))
