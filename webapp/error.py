# Importing modules and utilities for Flask web application development.
from flask import Blueprint, Flask, render_template, session
from typing import Optional
from sqlalchemy.exc import IntegrityError, DataError
from json import JSONDecodeError

# Initializing a Flask application with specific configuration settings.
# 'instance_relative_config=True' allows configurations to be loaded relative to the 'instance' folder,
# which typically contains sensitive information separate from the main application code.
app = Flask(__name__, instance_relative_config=True)
# Loading configuration from 'config.py' located in the 'instance' folder.
# 'silent=True' prevents Flask from throwing an error if the config file is absent, providing flexibility in deployment.
app.config.from_pyfile('config.py', silent=True)

# Creating a Blueprint for handling error-related routes and functionalities.
# Blueprints organize the app into distinct functional units or modules.
# This Blueprint, named 'all_the_error_cries', is dedicated to managing error-related aspects of the application.
all_the_error_cries = Blueprint('all_the_error_cries', __name__)


class TwitterAPIError(Exception):
    """
    A custom exception class for handling Twitter API-related errors more effectively.
    It allows for associating specific HTTP status codes with custom error messages,
    providing clearer, more informative feedback for both users and developers.
    """

    def __init__(self, status_code: Optional[int], message: Optional[str] = None):
        """
        Constructor for the TwitterAPIError class. 
        :param status_code: The HTTP status code associated with the
        error, used for HTTP response. 
        :param message: An optional message detailing the error. If not provided,
        a default message is set based on the status code.
        """
        self.status_code = status_code  # HTTP status code for the error.
        self.message = message if message else self.get_error_message()  # Custom or default error message.

    def __str__(self):
        """
        String representation of the TwitterAPIError, showing the status code and error message.
        This method is useful for logging and debugging purposes.
        """
        return f"{self.status_code}: {self.message}"

    # Dictionary mapping HTTP status codes to user-friendly error messages.
    # This helps in providing clearer, more contextual feedback for various error situations.
    error_messages = {
        # Examples of mapped status codes to specific error messages:
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

    # Method to retrieve an error message based on the status code.
    def get_error_message(self):
        """
        Retrieves a user-friendly error message based on the status code.
        If a specific message for the status code is not found, a default unknown error message is returned.
        :return: String representing the error message.
        """
        # Returns a tailored message for known status codes, or a generic message for unknown ones.
        return self.error_messages.get(self.status_code, f"Unknown error code {self.status_code}.")


# Function to handle and interpret Twitter API errors based on the response.
def handle_error(response):
    """
    Parses and handles errors based on the response from the Twitter API.
    This function aims to extract meaningful error information from the API response,
    transforming it into a structured exception for better error management.
    :param response: The response object from the Twitter API request.
    :raises TwitterAPIError: Customized exception encapsulating the error details.
    """
    try:
        # Attempting to decode the JSON content from the response.
        response_json = response.json()
    except ValueError:
        # If decoding fails, raise a TwitterAPIError with the status code and a generic message.
        raise TwitterAPIError(
            response.status_code,
            f"Received {response.status_code} status code with invalid JSON response."
        )

    # A mapping of Twitter-specific error codes to custom messages for various HTTP status codes.
    error_codes = {
        # Examples of mappings for common HTTP status codes and Twitter-specific error codes.
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

    # Check if the response's status code is covered in the error codes mapping.
    if response.status_code in error_codes:
        error_code_map = error_codes[response.status_code]
        # Determine the specific error message based on the error code in the response.
        if 'errors' in response_json and response_json['errors']:
            error_code = response_json['errors'][0]['code']
            error_message = error_code_map.get(error_code, 'Unknown error occurred.')
        else:
            error_message = error_code_map.get(None, 'Unknown error occurred.')

        # Raise a TwitterAPIError with the specific error message.
        raise TwitterAPIError(response.status_code, error_message)
    else:
        # If the status code is not in the mapping, raise a general TwitterAPIError.
        raise TwitterAPIError(response.status_code, 'Unknown error occurred.')


# Flask error handler for TwitterAPIError.
@app.errorhandler(TwitterAPIError)
def handle_twitter_api_error(error):
    """
    Custom error handler for TwitterAPIError.
    It renders an error page with the details of the Twitter API error.
    :param error: Instance of TwitterAPIError containing error details.
    :return: Rendered error page with appropriate HTTP status code.
    """
    error_code = error.status_code  # Extracting the HTTP status code from the error.
    error_message = error.message  # Extracting the error message.
    # Rendering an error template with the extracted information.
    return render_template('error.html', error_code=error_code, error_message=error_message), int(error_code)


# Flask error handler for generic exceptions.
@app.errorhandler(Exception)
def handle_exception_error(error):
    """
    Generic error handler for all uncaught exceptions.
    Logs the exception details and renders a generic internal server error page.
    This handler ensures that unhandled exceptions do not expose sensitive information.
    :param error: The caught exception instance.
    :return: Rendered internal server error template with HTTP status code 500.
    """
    app.logger.error(error)  # Logging the error details for debugging purposes.
    # Rendering a generic internal server error page.
    return render_template('error.html', error_code=500, error_message="Internal Server Error"), 500


# Error handlers for specific HTTP status codes.
# These functions provide tailored responses for common HTTP errors, improving user experience.
@app.errorhandler(400)
def bad_request(error):
    """
    Error handler for HTTP 400 Bad Request errors.
    Renders a custom error page specific to bad requests.
    :param error: The caught 400 error instance.
    :return: Rendered bad request error template with HTTP status code 400.
    """
    return render_template('error.html', error_code=400, error_message='Bad Request'), 400


@app.errorhandler(401)
def unauthorized(error):
    """
    Custom error handler for the 401 Unauthorized HTTP status code.
    This occurs when a request requires user authentication, and the request has not been fulfilled.
    Typically used for login pages or when a user tries to access a resource they don't have permission for.
    :param error: The error object provided by Flask.
    :return: Rendered error template with specific details for a 401 Unauthorized error.
    """
    # Render and return a custom error page specifically tailored for 401 Unauthorized errors.
    return render_template('error.html', error_code=401, error_message='Unauthorized'), 401


@app.errorhandler(403)
def forbidden(error):
    """
    Custom error handler for the 403 Forbidden HTTP status code.
    This occurs when the server understands the request but refuses to authorize it.
    A common use case is when the user lacks the necessary permissions for a resource.
    :param error: The error object provided by Flask.
    :return: Rendered error template with specific details for a 403 Forbidden error.
    """
    # Render and return a custom error page specifically tailored for 403 Forbidden errors.
    return render_template('error.html', error_code=403, error_message='Forbidden'), 403


@app.errorhandler(404)
def not_found(error):
    """
    Custom error handler for the 404 Not Found HTTP status code.
    This typically occurs when the user tries to access a resource that does not exist on the server.
    It is one of the most common errors on the web.
    :param error: The error object provided by Flask.
    :return: Rendered error template with specific details for a 404 Not Found error.
    """
    # Render and return a custom error page specifically tailored for 404 Not Found errors.
    return render_template('error.html', error_code=404, error_message='Not Found'), 404


@app.errorhandler(405)
def method_not_allowed(error):
    """
    Custom error handler for the 405 Method Not Allowed HTTP status code.
    This error occurs when the server knows the request method, but the target resource does not support this method.
    For example, a GET request to an endpoint that only supports POST requests would trigger this error.
    :param error: The error object provided by Flask.
    :return: Rendered error template with specific details for a 405 Method Not Allowed error.
    """
    # Render and return a custom error page specifically tailored for 405 Method Not Allowed errors.
    return render_template('error.html', error_code=405, error_message='Method Not Allowed'), 405


@app.errorhandler(429)
def too_many_requests(error):
    """
    Custom error handler for the 429 Too Many Requests HTTP status code.
    This error is triggered when a user has sent too many requests in a given amount of time ("rate limiting").
    It's a common way to protect web services from abuse and to manage traffic.
    :param error: The error object provided by Flask.
    :return: Rendered error template with specific details for a 429 Too Many Requests error.
    """
    # Render and return a custom error page specifically tailored for 429 Too Many Requests errors.
    return render_template('error.html', error_code=429, error_message='Too Many Requests'), 429


# SQLAlchemy's error handlers.
# These catch database-related errors and render an appropriate error message.
@app.errorhandler(IntegrityError)
def handle_integrity_error(error):
    """
    Handles SQLAlchemy IntegrityError, often related to database constraint violations.
    Logs the error for further investigation and renders a database-specific error page.
    :param error: The caught IntegrityError instance.
    :return: Rendered database error template with HTTP status code 500.
    """
    app.logger.error(error)  # Logging the error for administrative purposes.
    # Rendering a database-specific error page.
    return render_template('error.html', error_code=500, error_message="Database Integrity Error"), 500


@app.errorhandler(DataError)
def handle_data_error(error):
    """
    Handles SQLAlchemy DataError, typically indicating issues with the format or nature of database data.
    Logs the error for analysis and renders a database error page.
    :param error: The caught DataError instance.
    :return: Rendered database error template with HTTP status code 500.
    """
    app.logger.error(error)  # Logging the error for maintenance and debugging.
    # Rendering a database error page for data-related issues.
    return render_template('error.html', error_code=500, error_message="Database Data Error"), 500


@app.errorhandler(JSONDecodeError)
def handle_json_decode_error(error):
    """
    Handles errors related to JSON decoding, indicating issues in parsing JSON data.
    Logs the error for review and renders a JSON-specific error page.
    :param error: The caught JSONDecodeError instance.
    :return: Rendered JSON error template with HTTP status code 500.
    """
    app.logger.error(error)  # Logging the error for further investigation.
    # Rendering a JSON-specific error page.
    return render_template('error.html', error_code=500, error_message="JSON Decode Error"), 500


# Error handler for HTTP 500 Internal Server Error.
@app.errorhandler(500)
def internal_server_error(error):
    """
    Handles HTTP 500 Internal Server Error.
    Renders a generic internal server error page.
    :param error: The caught internal server error instance.
    :return: Rendered internal server error template with HTTP status code 500.
    """
    return render_template('error.html', error_code=500, error_message='Internal Server Error'), 500


# Additional error handlers for other HTTP status codes.
# These handlers ensure that the application provides informative feedback for various error conditions.
@app.errorhandler(502)
def bad_gateway(error):
    """
    Handles HTTP 502 Bad Gateway errors.
    Renders a custom error page indicating issues with the gateway or proxy.
    """
    return render_template('error.html', error_code=502, error_message='Bad Gateway'), 502


@app.errorhandler(503)
def service_unavailable(error):
    """
    Custom error handler for the 503 Service Unavailable HTTP status code.
    This error typically occurs when the server is down for maintenance or is overloaded.
    It indicates that the server is temporarily unable to handle the request.
    :param error: The error object provided by Flask.
    :return: Rendered error template with specific details for a 503 Service Unavailable error.
    """
    # Render and return a custom error page specifically tailored for 503 Service Unavailable errors.
    return render_template('error.html', error_code=503, error_message='Service Unavailable'), 503


@app.errorhandler(504)
def gateway_timeout(error):
    """
    Custom error handler for the 504 Gateway Timeout HTTP status code. This error occurs when a server acting as a
    gateway or proxy does not receive a timely response from an upstream server. It's an indication that a different
    server, which the initial request was sent to, is not responding. 
    :param error: The error object provided by Flask.
    :return: Rendered error template with specific details for a 504 Gateway Timeout error.
    """
    # Render and return a custom error page specifically tailored for 504 Gateway Timeout errors.
    return render_template('error.html', error_code=504, error_message='Gateway Timeout'), 504


@app.before_request
def session_management():
    """
    Function executed before each request. Ideal for session-related tasks.
    This could include actions like validating session tokens, refreshing session data, etc.
    """
    pass  # Placeholder for session management logic.
