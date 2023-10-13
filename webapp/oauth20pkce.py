from flask import Flask, Blueprint, render_template, session, request, redirect, url_for, flash
from flask_login import current_user, login_required
from .models import db, OAuth20PKCE
from sqlalchemy.sql import func
import requests
import logging
import secrets
import hashlib
import base64


app = Flask(__name__, instance_relative_config=True)
app.config.from_pyfile('config.py', silent=True)
app.secret_key = app.config['API_KEY_SECRET']
oauth20pkce = Blueprint('oauth20pkce', __name__)


@login_required
@oauth20pkce.route('/oauth20pkceindex')
def oauth20pkce_index():
    # Generate a random code verifier
    code_verifier = ''.join(
        secrets.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~') for _ in range(64))

    # Generate the code challenge by hashing the code verifier using SHA-256, then base64url encoding the hash
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).decode().rstrip('=')

    state = secrets.token_hex(16)

    session['code_verifier'] = code_verifier
    session['state'] = state

    # Log the code_verifier and code_challenge
    logging.info(f"Code Verifier: {code_verifier}")
    logging.info(f"Code Challenge: {code_challenge}")

    # Construct the authorization URL dynamically
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

    # Log the authorization URL
    logging.info(f"Authorization URL: {authorization_url}")

    return render_template('oauth20pkceindex.html', authorization_url=authorization_url, user=current_user)


@login_required
@oauth20pkce.route('/oauth20pkcecallback')
def oauth20pkcecallback():
    if current_user.is_authenticated:
        email = current_user.email
    else:
        email = None  # or handle this case as per your application's requirement

    error = request.args.get('error')
    if error:
        app.logger.error(f'Authorization failed: {error}')
        flash('Authorization failed', 'danger')
        return redirect(url_for('unauth.unauthhome'))

    code = request.args.get('code')
    state = request.args.get('state')

    app.logger.info(f"Received code: {code}")
    app.logger.info(f"Received state: {state}")

    if state != session.get('state'):
        app.logger.warning('Invalid state parameter')
        flash('Invalid state parameter', 'danger')
        return redirect(url_for('unauth.unauthhome'))

    code_verifier = session.get('code_verifier')
    app.logger.info(f"Code Verifier from session: {code_verifier}")

    if not code_verifier:
        app.logger.warning('Invalid code verifier')
        flash('Invalid code verifier', 'danger')
        return redirect(url_for('unauth.unauthhome'))

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

    response = requests.post(token_url, headers=headers, data=data)

    if response.status_code != 200:
        app.logger.error(f'Failed to exchange authorization code for access token: {response.text}')
        flash(f"Authorization failed: {response.text}", 'danger')
        return redirect(url_for('unauth.unauthhome'))

    token_data = response.json()

    # Fetch user information using the access token
    headers = {
        'Authorization': f"Bearer {token_data['access_token']}"
    }
    user_info_url = 'https://api.twitter.com/2/users/me'
    user_response = requests.get(user_info_url, headers=headers)

    app.logger.info(f"Access Token: {token_data['access_token']}")
    app.logger.info(f"User info response status: {user_response.status_code}")
    app.logger.info(f"User info response headers: {user_response.headers}")
    app.logger.info(f"User info response text: {user_response.text}")

    if user_response.status_code != 200:
        app.logger.error(f'Failed to retrieve user information: {user_response.text}')
        flash('Failed to retrieve user information', 'danger')
        return redirect(url_for('unauth.unauthhome'))

    user_data = user_response.json()

    # Check if a user with the given email already exists
    existing_user = OAuth20PKCE.query.filter_by(email=email).first()

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
        db.session.add(oauth_record)
        db.session.commit()

    flash('Authorization successful', 'success')
    return render_template("oauth20pkcecallback.html", user_data=user_data, user=current_user, email=email)
