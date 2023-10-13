from instance.config import APP_CONSUMER_KEY, APP_CONSUMER_SECRET, REQUEST_TOKEN_URL, \
    ACCESS_TOKEN_URL, AUTHORIZE_URL, SHOW_USER_URL
from flask import Flask, Blueprint, render_template, request, url_for, session, jsonify
from .error import all_the_error_cries, TwitterAPIError
from flask_login import current_user, login_required
from werkzeug.security import generate_password_hash
from .oauth10areport import impersonatingusers
from sqlalchemy.exc import IntegrityError
from .models import db, OAuth10a
from types import GeneratorType  # Importing GeneratorType
from datetime import datetime, timedelta
from json import JSONEncoder
from functools import wraps  # Import wraps for the decorator
import oauth2 as oauth
import urllib.parse
import logging
import json

logging.basicConfig(filename='/home/everybodygetshurt/everybodygetshurt/oauth1.0a-logfile.log', level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(message)s')

oauth_store = {}

app = Flask(__name__, instance_relative_config=True)
app.config.from_pyfile('config.py', silent=True)
app.secret_key = app.config['API_KEY_SECRET']
oauth10a = Blueprint('oauth10a', __name__)


# Simplified token refresh logic
def refresh_oauth_token(oauth_instance):
    # Implement your token refresh logic here
    # For example, send a request to refresh the token and update oauth_instance
    # oauth_instance = make_refresh_request(oauth_instance)
    return oauth_instance


# Define a decorator for handling OAuth token refresh
def needs_token_refresh():
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if kwargs.get('oauth_instance') and kwargs.get('oauth_instance').last_token_refresh_date:
                thirty_days_ago = datetime.utcnow() - timedelta(days=30)
                if kwargs.get('oauth_instance').last_token_refresh_date < thirty_days_ago:
                    # Refresh the OAuth token
                    kwargs['oauth_instance'] = refresh_oauth_token(kwargs.get('oauth_instance'))
            return view_func(*args, **kwargs)

        return wrapped

    return decorator


@login_required
@oauth10a.route('/oauth10aindex')
def oauth10aindex():
    # SECURITY - The _scheme="https" makes sure the callback url is using HTTPS
    app_callback_url = url_for('oauth10a.oauth10acallback', _external=True, user=current_user, _scheme="https")
    consumer = oauth.Consumer(
        APP_CONSUMER_KEY, APP_CONSUMER_SECRET)
    client = oauth.Client(consumer)
    resp, content = client.request(REQUEST_TOKEN_URL, "POST", body=urllib.parse.urlencode({
        "oauth10a.oauth10acallback": app_callback_url}))

    if resp['status'] != '200':
        raise TwitterAPIError(int(resp['status']))

    request_token = dict(urllib.parse.parse_qsl(content))
    try:
        oauth_token = request_token[b'oauth_token'].decode('utf-8', 'ignore')
        oauth_token_secret = request_token[b'oauth_token_secret'].decode('utf-8', 'ignore')
    except UnicodeDecodeError as e:
        logging.error(f"Unicode decode error: {str(e)}")
        return render_template('error.html', error_message="Unicode decode error", user=current_user)

    oauth_secret_hash = generate_password_hash(oauth_token_secret)
    oauth_store[oauth_token] = oauth_secret_hash

    session['oauth_token_secret'] = oauth_token_secret

    logging.debug(f"Request Token: {request_token}")
    logging.debug(f"App Callback URL: {app_callback_url}")

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
        return render_template('error.html',
                               error_message="The OAuth request was denied by this user", user=current_user)

    if not oauth_token or not oauth_verifier:
        return render_template('error.html',
                               error_message="Callback param(s) missing", user=current_user)

    oauth_token_secret = session.get('oauth_token_secret')
    if not oauth_token_secret:
        return render_template('error.html',
                               error_message="oauth_token_secret not found in session", user=current_user)

    consumer = oauth.Consumer(
        APP_CONSUMER_KEY, APP_CONSUMER_SECRET)
    token = oauth.Token(oauth_token, oauth_token_secret)
    token.set_verifier(oauth_verifier)
    client = oauth.Client(consumer, token)

    resp, content = client.request(ACCESS_TOKEN_URL, "POST")
    access_token = dict(urllib.parse.parse_qsl(content))

    screen_name = access_token[b'screen_name'].decode('utf-8')
    user_id = access_token[b'user_id'].decode('utf-8')

    real_oauth_token = access_token[b'oauth_token'].decode('utf-8')
    real_oauth_token_secret = access_token[b'oauth_token_secret'].decode('utf-8')

    real_token = oauth.Token(real_oauth_token, real_oauth_token_secret)
    real_client = oauth.Client(consumer, real_token)
    real_resp, real_content = real_client.request(SHOW_USER_URL + '?user_id=' + user_id, "GET")

    if real_resp['status'] != '200':
        error_message = "Invalid response from Twitter API GET users/show: {status}".format(status=real_resp['status'])
        return render_template('error.html', error_message=error_message, user=current_user)

    response = json.loads(real_content.decode('utf-8'))

    friends_count = response['friends_count']
    statuses_count = response['statuses_count']
    followers_count = response['followers_count']
    name = response['name']

    set_to_database = OAuth10a(
        twitter_id=user_id,
        account_name=screen_name,
        email=email,
        oauth_token=real_oauth_token,
        oauth_token_secret=real_oauth_token_secret,
        oauth_verifier=oauth_verifier,
        date_created=datetime.utcnow()
    )

    try:
        db.session.add(set_to_database)
        db.session.commit()
    except IntegrityError as e:
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

    return render_template(
        'oauth10acallback.html', screen_name=screen_name, user_id=user_id,
        name=name, friends_count=friends_count, statuses_count=statuses_count,
        followers_count=followers_count, access_token_url=ACCESS_TOKEN_URL, user=current_user,
        email=email)


def handle_integrity_error(e, set_to_database):
    db.session.rollback()
    error_message = str(e)
    if "UNIQUE constraint failed: oauth10a.oauth_token_secret" in error_message:
        update_existing_entry(set_to_database)
    elif 'UNIQUE constraint failed: oauth10a.twitter_id' in error_message:  # Updated this line
        update_existing_record(set_to_database)
    else:
        return render_template('error.html', error_message=error_message, user=current_user)


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


@login_required
@oauth10a.route('/oauth10ajson')
def oauth10ajson():
    return render_template("json.html", user=current_user)


@login_required
@oauth10a.route('/oauth10areport')
def oauth10areport():
    return render_template("oauth10areport.html", user=current_user)


class CustomJSONEncoder(json.JSONEncoder):  # Updated JSONEncoder import here
    def default(self, obj):
        if isinstance(obj, GeneratorType):
            return list(obj)
        return super().default(obj)


@login_required
@oauth10a.route('/oauth10areportimpersonators', methods=['POST'])
@needs_token_refresh()  # Apply the decorator to this route
def oauth10areportimpersonators():
    impersonated_channel = request.form.get('impersonated_channel')
    response = impersonatingusers(impersonated_channel)
    return render_template('oauth10areport.html', user=current_user,
                           response=json.dumps(response, cls=CustomJSONEncoder))


@oauth10a.errorhandler(TwitterAPIError)
def handle_twitter_api_error(error):
    return render_template('error.html', error_message=str(error), user=current_user), error.status_code
