# Standard library imports
import base64
import hashlib
import logging
import secrets

# Third-party imports
from flask import (Flask, Blueprint, render_template, session, request,
                   redirect, url_for, flash)
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError
import requests

# Local application imports
from .models import db, OAuth20PKCE
from sqlalchemy.sql import func


# Initializing Flask app and loading configurations
app = Flask(__name__, instance_relative_config=True)
app.config.from_pyfile('config.py', silent=True)
app.secret_key = app.config['API_KEY_SECRET']

# Creating a Blueprint for the OAuth 2.0 PKCE routes
oauth20pkce = Blueprint('oauth20pkce', __name__)


# A user must be logged in to access this route
@login_required
# Route to start the OAuth 2.0 PKCE flow:
# This part initializes the Flask app and sets up configurations and the secret key.
# It creates a Blueprint for the OAuth 2.0 PKCE flow and sets up the first route for starting the OAuth flow.
# When the user accesses this route, a code verifier and challenge are generated and stored,
# and the user is redirected to the OAuth provider's authorization URL.
@oauth20pkce.route('/oauth20pkceindex')
def oauth20pkce_index():
    # A unique code_verifier is generated each time the OAuth flow is initiated to ensure security.
    # The code_challenge derived from the code_verifier is sent to the authorization server.
    code_verifier = ''.join(
        secrets.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~') for _ in range(128))

    # Generate the code challenge by hashing the code verifier using SHA-256, then base64url encoding the hash.
    """
    !!! SECURITY NOTICE ABOUT SHA256 HASHES: !!! 
    
    HMAC isn't specifically needed for the OAuth 2.0 PKCE flow. The original concern about SHA-256's vulnerability 
    to length-extension attacks is more applicable to situations where hash functions are used for creating secure 
    message authentication codes (MACs) or signatures. In such cases, HMAC (Hash-based Message Authentication Code) 
    is indeed recommended as it mitigates these vulnerabilities.

    In OAuth 2.0 PKCE, SHA-256 is used for a different purpose: to create a challenge from a verifier in a way that 
    is specified by the OAuth 2.0 standard (specifically RFC 7636). This usage does not involve creating a MAC or 
    signature and is not vulnerable to length-extension attacks. The code challenge is hashed and sent to the 
    authorization server, which later verifies that the same verifier is being used by hashing it again and comparing 
    it to the initially sent challenge.

    For the PKCE flow itself, the current use of SHA-256 is considered secure and standard-compliant.
    """
    # noinspection InsecureHash
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).decode().rstrip('=')

    # The state parameter is a CSRF token that is sent to the authorization server and must be returned unchanged
    # to prevent cross-site request forgery attacks.
    state = secrets.token_hex(128)

    # Storing the code verifier and state in the session ensures that they can be retrieved later
    # for validation and to complete the OAuth flow.
    session['code_verifier'] = code_verifier
    session['state'] = state

    # Log the code_verifier and code_challenge
    logging.info(f"Code Verifier: {code_verifier}")
    logging.info(f"Code Challenge: {code_challenge}")

    # Constructing the authorization URL with the client ID, redirect URI, scopes, state, code challenge, and method
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

    # The complete authorization URL is logged for debugging purposes
    logging.info(f"Authorization URL: {authorization_url}")

    # Rendering a template with the authorization URL and current user
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
