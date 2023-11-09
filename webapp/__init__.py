"""
This module serves as the initiation point for the web application.
Here, we import the necessary modules, initialize the database, and create the Flask application instance.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_talisman import Talisman
from flask import Flask
from os import path
from instance.config import DB_NAME

# Initialize SQLAlchemy instance to interact with the database
db = SQLAlchemy()


def create_app():
    """
    This function initializes the Flask application, configures it with necessary parameters,
    and registers various blueprints which govern the behavior of different routes in the application.
    It also initializes the login manager to handle user sessions.
    """

    # Create a Flask application instance with relative configuration option enabled
    app = Flask(__name__, instance_relative_config=True)

    # Load configuration from the 'config.py' file in the 'instance' folder
    app.config.from_pyfile(filename='config.py')

    # Mandatory configuration for Talisman
    app.config['SESSION_COOKIE_SECURE'] = True

    # Initialize the database with the current application instance
    db.init_app(app)

    # Importing models and blueprints
    from .models import User, OAuth10a, OAuth20PKCE, UserReportedImpersonator
    from .unauth import unauth
    from .auth import auth
    from .oauth10a import oauth10a
    from .oauth20pkce import oauth20pkce
    from webapp.oauth10areport import oauth10areport
    from .error import (all_the_error_cries, TwitterAPIError, handle_error, handle_exception_error, forbidden,
                        handle_twitter_api_error, not_found, unauthorized, method_not_allowed, bad_request)

    # Registering blueprints to the application instance
    app.register_blueprint(unauth, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')
    app.register_blueprint(oauth10a, url_prefix='/')
    app.register_blueprint(oauth10areport, url_prefix='/')
    app.register_blueprint(oauth20pkce, url_prefix='/')
    app.register_blueprint(all_the_error_cries, url_prefix='/')

    # Creating database tables within the application context
    with app.app_context():
        db.create_all()

    # Initializing and configuring the login manager
    login_manager = LoginManager()
    login_manager.login_view = 'auth.authlogin'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(email):
        """
        Configure the user loader callback for Flask-Login to use the email as the user identifier.
        This function will be used to load a user from the session.
        """
        return User.query.get(email)

    # Initializing and configuring the Flask-Talisman extension for HTTP security headers
    Talisman(app, force_https=True, session_cookie_secure=True, referrer_policy='no-referrer',
             strict_transport_security_max_age=63072000, strict_transport_security_preload=True,
             x_xss_protection=False)

    # Setting up logging to capture CSP violations
    import logging
    logging.basicConfig(filename='csp_violations.log', level=logging.INFO)
    logger = app.logger
    logger.addHandler(logging.FileHandler('csp_violations.log'))

    return app


def create_database():
    """
    This function checks for the existence of a database in the specified path.
    If not found, it creates a new database.
    """
    if not path.isfile('../instance/' + DB_NAME):
        db.create_all()
        print('Created Database!')
