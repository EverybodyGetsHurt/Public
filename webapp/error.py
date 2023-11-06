from flask import Blueprint, Flask, render_template, session
from typing import Optional
from sqlalchemy.exc import IntegrityError, DataError
from json import JSONDecodeError

app = Flask(__name__, instance_relative_config=True)
app.config.from_pyfile('config.py', silent=True)

all_the_error_cries = Blueprint('all_the_error_cries', __name__)


class TwitterAPIError(Exception):
    def __init__(self, status_code: Optional[int], message: Optional[str] = None):
        self.status_code = status_code
        self.message = message if message else self.get_error_message()

    def __str__(self):
        return f"{self.status_code}: {self.message}"

    error_messages = {
        200: "The request was successful!",
        304: "304 - NOT MODIFIED: There was no new data to return.",
        400: "400 - BAD REQUEST: The request was invalid or cannot be otherwise served. An accompanying error message "
             "will explain further. Requests without authentication or with invalid query parameters are considered "
             "invalid and will yield this response. Double check the format of your JSON query. For example, "
             "if your rule contains double-quote characters associated with an exact-match or other operator, "
             "you may need to escape them using a backslash to distinguish them from the structure of the JSON "
             "format. Read more.",
        401: "401 - UNAUTHORIZED: There was a problem authenticating your request. This could be due to missing or "
             "incorrect authentication credentials. This may also be returned in other undefined circumstances. Check "
             "that you are using the correct authentication method and that your credentials are correct.",
        403: "403 - FORBIDDEN: The request is understood, but it has been refused or access is not allowed. An "
             "accompanying error message will explain why. Check that your developer account includes access to the "
             "endpoint you’re trying to use. You may also need to get your App allow-listed (e.g. Engagement API or "
             "Ads API) or sign up for access.",
        404: "404 - NOT FOUND: The URI requested is invalid or the resource requested does not exist. Check that you "
             "are using valid parameters and the correct URI for the endpoint you’re using.",
        406: "406 - NOT ACCEPTABLE: Returned when an invalid format is specified in the request. Generally, "
             "this occurs where your client fails to properly include the headers to accept gzip encoding, "
             "but can occur in other circumstances as well. Check that you are correctly passing expected query "
             "parameters, including expected headers, in your request.",
        409: "409 - CONNECTION EXCEPTION: Returned when attempting to connect to a filtered stream that has no rules. "
             "Check that you have created at least one rule on the stream you are connecting to. Filtered stream will "
             "only return Tweets that match an active rule. If there are no rules, the stream will not return any "
             "Tweets.",
        410: "410 - GONE: This resource is gone. Used to indicate that an API endpoint has been turned off.",
        422: "422 - UNPROCESSABLE ENTITY: Returned when the data is unable to be processed. Check that the data you "
             "are sending in your request is valid. For example, this data could be the JSON body of your request or "
             "an image.",
        429: "429 - TOO MANY REQUESTS: Returned when a request cannot be served due to the App's rate limit or Tweet "
             "cap having been exhausted. See Rate Limiting. Check the number of requests per timeframe allowed with "
             "the endpoint you’re using. Wait for the timeframe to reset. Space out your requests to ensure you don’t "
             "hit rate limits or upgrade to the next available data plan.",
        431: "431 - REQUEST HEADER FIELDS TOO LARGE: The server is unwilling to process the request because either an "
             "individual header field, or all the header fields collectively, are too large. Reduce the size of the "
             "request headers.",
        451: '451 - UNAVAILABLE FOR LEGAL REASONS - The user’s account is not available because it is disconnected '
             'from Twitter by a valid legal request.',
        460: '460 - CUSTOM ERROR - Custom error message for specific scenarios in your application.',
        461: '461 - ANOTHER CUSTOM ERROR - Another custom error message for different scenarios in your application.',
        500: "500 - INTERNAL SERVER ERROR: Something is broken. This is usually a temporary error, for example in a "
             "high load situation or if an endpoint is temporarily having issues. Check the Twitter API status page "
             "or the developer community forum in case others are having similar issues, or simply wait and try again "
             "later.",
    }

    def get_error_message(self):
        return self.error_messages.get(self.status_code, f"Unknown error code {self.status_code}.")


def handle_error(response):
    try:
        response_json = response.json()
    except ValueError:
        raise TwitterAPIError(
            response.status_code,
            f"Received {response.status_code} status code with invalid JSON response."
        )

    error_codes = {
        400: {3: 'Invalid coordinates.', 44: 'Attachment URL parameter is invalid.'},
        401: {32: 'Could not authenticate you.', 135: 'Timestamp out of bounds.'},
        403: {36: 'You cannot report yourself for spam.', 38: 'Parameter is missing.', 63: 'User has been suspended.',
              64: 'Account is suspended and not permitted to access this feature.',
              87: 'Client is not permitted to perform this action.', 92: 'SSL is required.',
              93: 'App is not allowed to access or delete your Direct Messages.',
              99: 'Unable to verify your credentials.', 110: 'User cannot be removed from this list.',
              120: 'Account update failed.', 139: 'Tweet cannot be favorite more than once.',
              150: 'Cannot send messages to users who are not following you.',
              151: 'There was an error sending your message.', 161: 'Cannot follow more people at this time.',
              179: 'Not authorized to see this status.', 185: 'User is over daily status update limit.'},
        404: {13: 'No location associated with the specified IP address.', 17: 'No user matches for specified terms.'},
        429: {None: 'Rate limit exceeded. Try again later.'},
        500: {None: 'Internal server error.'},
    }

    if response.status_code in error_codes:
        error_code_map = error_codes[response.status_code]
        if 'errors' in response_json and response_json['errors']:
            error_code = response_json['errors'][0]['code']
            if error_code in error_code_map:
                error_message = error_code_map[error_code]
            else:
                error_message = 'Unknown error occurred.'
        else:
            if None in error_code_map:
                error_message = error_code_map[None]
            else:
                error_message = 'Unknown error occurred.'

        raise TwitterAPIError(response.status_code, error_message)
    else:
        raise TwitterAPIError(response.status_code, 'Unknown error occurred.')


@app.errorhandler(TwitterAPIError)
def handle_twitter_api_error(error):
    error_code = error.status_code
    error_message = error.message
    return render_template('error.html', error_code=error_code, error_message=error_message), int(error_code)


@app.errorhandler(Exception)
def handle_exception_error(error):
    app.logger.error(error)
    return render_template('error.html', error_code=500, error_message="Internal Server Error"), 500


@app.errorhandler(400)
def bad_request(error):
    return render_template('error.html', error_code=400, error_message='Bad Request'), 400


@app.errorhandler(401)
def unauthorized(error):
    return render_template('error.html', error_code=401, error_message='Unauthorized'), 401


@app.errorhandler(403)
def forbidden(error):
    return render_template('error.html', error_code=403, error_message='Forbidden'), 403


@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', error_code=404, error_message='Not Found'), 404


@app.errorhandler(405)
def method_not_allowed(error):
    return render_template('error.html', error_code=405, error_message='Method Not Allowed'), 405


@app.errorhandler(429)
def too_many_requests(error):
    return render_template('error.html', error_code=429, error_message='Too Many Requests'), 429


@app.errorhandler(IntegrityError)
def handle_integrity_error(error):
    app.logger.error(error)
    return render_template('error.html', error_code=500, error_message="Database Integrity Error"), 500


@app.errorhandler(DataError)
def handle_data_error(error):
    app.logger.error(error)
    return render_template('error.html', error_code=500, error_message="Database Data Error"), 500


@app.errorhandler(JSONDecodeError)
def handle_json_decode_error(error):
    app.logger.error(error)
    return render_template('error.html', error_code=500, error_message="JSON Decode Error"), 500


@app.errorhandler(500)
def internal_server_error(error):
    return render_template('error.html', error_code=500, error_message='Internal Server Error'), 500


@app.errorhandler(502)
def bad_gateway(error):
    return render_template('error.html', error_code=502, error_message='Bad Gateway'), 502


@app.errorhandler(503)
def service_unavailable(error):
    return render_template('error.html', error_code=503, error_message='Service Unavailable'), 503


@app.errorhandler(504)
def gateway_timeout(error):
    return render_template('error.html', error_code=504, error_message='Gateway Timeout'), 504


@app.before_request
def session_management():
    # Here you can add logic to handle session-related errors, like checking if a session is still valid, etc.
    pass
