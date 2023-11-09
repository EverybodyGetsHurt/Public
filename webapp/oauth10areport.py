from flask import current_app, Blueprint, render_template, send_from_directory, jsonify, make_response, request
from requests_oauthlib import OAuth1Session
from instance import config
from .models import User
from flask_login import login_required, current_user
from flask_login import current_user
from flask.globals import request


oauth10areport = Blueprint('oauth10areport', __name__)


@login_required
@oauth10areport.route('/oauth10areportimpersonators')
def oauth10areportimpersonators(impersonated_channel):
    # get OAuth2PKCE tokens
    # OAuth2PKCE_access_token = None
    # OAuth2PKCE_refresh_token = None
    # if user.OAuth2PKCE:
    # OAuth2PKCE = user.OAuth2PKCE[0]  # assuming each user only has one OAuth2PKCE token
    # OAuth2PKCE_access_token = OAuth2PKCE.access_token
    # OAuth2PKCE_refresh_token = OAuth2PKCE.refresh_token
    user = User.query.filter_by(email=current_user.email).first()

    # get OAuth10a tokens
    oauth10a_token = None
    oauth10a_token_secret = None
    if user.oauth10a:
        oauth10a = user.oauth10a[0]  # assuming each user only has one OAuth10a token
        oauth10a_token = oauth10a.oauth_token
        oauth10a_token_secret = oauth10a.oauth_token_secret

    # Set up OAuth1Session
    oauth = OAuth1Session(
        config.APP_CONSUMER_KEY,
        client_secret=config.APP_CONSUMER_SECRET,
        resource_owner_key=oauth10a_token,
        resource_owner_secret=oauth10a_token_secret,
    )

    # Open the file containing the list of impersonators
    with open(current_app.instance_path + f"\\Active-{impersonated_channel}.txt", "r") as file:
        contents = file.read().split("=")
        # Extract the list of impersonators from the file
        impersonators_list = contents[1].split(",")

    response_list = []

    for impersonator in impersonators_list:
        # Mute the user
        mute_url = f"https://api.twitter.com/1.1/mutes/users/create.json?screen_name={impersonator}"
        try:
            response = oauth.post(mute_url)
            response.raise_for_status()
            yield f'Muted user with screen name: {impersonator}'
        except Exception as e:
            yield f'Error muting user {impersonator}: {e}'

        # Block the user
        block_url = f"https://api.twitter.com/1.1/blocks/create.json?screen_name={impersonator}"
        try:
            response = oauth.post(block_url)
            response.raise_for_status()
            yield f'Blocked user with screen name: {impersonator}'
        except Exception as e:
            yield f'Error blocking user {impersonator}: {e}'

        # Report the user as impersonator
        report_url = \
            f"https://api.twitter.com/1.1/users/report_spam.json?" \
            f"screen_name={impersonator}"

        response = oauth.post(report_url)
        if response.status_code != 200:
            yield f'Request returned an error: {response.status_code} {response.text}'
        else:
            yield f'Reported user with screen name: {impersonator}'

        # Saving the response as JSON
        json_response = response.json()
        response_list.append(json_response)

    return response_list



def impersonatingusers(impersonated_channel):
    # TODO: Implement the logic to find impersonating users for the given channel
    # This function is expected to return a JSON response
    # The logic will depend on how your application determines impersonation
    # For now, we'll return an empty list as a placeholder
    return []



def impersonatingusers(impersonated_channel, current_user, OAuth1Session, config, User):
    # get OAuth10a tokens
    oauth10a_token = None
    oauth10a_token_secret = None
    if current_user.oauth10a:
        oauth10a = current_user.oauth10a[0]  # assuming each user only has one OAuth10a token
        oauth10a_token = oauth10a.oauth_token
        oauth10a_token_secret = oauth10a.oauth_token_secret

    # Set up OAuth1Session
    oauth = OAuth1Session(
        config.APP_CONSUMER_KEY,
        client_secret=config.APP_CONSUMER_SECRET,
        resource_owner_key=oauth10a_token,
        resource_owner_secret=oauth10a_token_secret,
    )

    # Open the file containing the list of impersonators
    with open(current_app.instance_path + f"\Active-{impersonated_channel}.txt", "r") as file:
        contents = file.read().split("=")
        # Extract the list of impersonators from the file
        impersonators_list = contents[1].split(",")

    response_list = []

    for impersonator in impersonators_list:
        # Mute the user
        mute_url = f"https://api.twitter.com/1.1/mutes/users/create.json?screen_name={impersonator}"
        try:
            response = oauth.post(mute_url)
            response.raise_for_status()
            response_list.append(f'Muted user with screen name: {impersonator}')
        except Exception as e:
            response_list.append(f'Error muting user {impersonator}: {e}')

        # Block the user
        block_url = f"https://api.twitter.com/1.1/blocks/create.json?screen_name={impersonator}"
        try:
            response = oauth.post(block_url)
            response.raise_for_status()
            response_list.append(f'Blocked user with screen name: {impersonator}')
        except Exception as e:
            response_list.append(f'Error blocking user {impersonator}: {e}')

        # Report the user as impersonator
        report_url = f"https://api.twitter.com/1.1/users/report_spam.json?screen_name={impersonator}"
        response = oauth.post(report_url)
        if response.status_code != 200:
            response_list.append(f'Request returned an error: {response.status_code} {response.text}')
        else:
            response_list.append(f'Reported user with screen name: {impersonator}')

        # Saving the response as JSON
        json_response = response.json()
        response_list.append(json_response)

    return response_list
