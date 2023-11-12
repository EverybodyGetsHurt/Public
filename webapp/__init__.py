"""
The '__init__.py' file in a Python package serves multiple purposes. Primarily, it allows the directory to be
treated as a package, enabling imports from other files in the same directory. This specific '__init__.py' is
geared towards setting up a Flask-based web application. It initializes the application's environment by
importing necessary libraries, setting up database connections, configuring application instances, and
registering Flask blueprints and extensions. This setup is crucial for the application's scalability and
maintenance, as well as for ensuring security and functionality through structured organization.
"""

# Importing essential libraries for Flask web application.

# SQLAlchemy provides ORM (Object-Relational Mapping) support for Flask applications.
from flask_sqlalchemy import SQLAlchemy
# Flask-Login offers session management for user logins, handling the common tasks in login workflows.
from flask_login import LoginManager
# Flask-Talisman applies security headers to Flask
# applications to protect against common web vulnerabilities.
from flask_talisman import Talisman
# Flask is a micro web framework for Python, providing tools,
# libraries, and technologies for building web applications.
from flask import Flask
# Used for operating system dependent functionality, especially for file path manipulations.
from os import path
# Imports the database name from a configuration file, usually used to separate configuration from code.
from instance.config import DB_NAME

# Initializing SQLAlchemy.
# This line creates an instance of the SQLAlchemy class.
# This instance acts as the bridge between Flask and the database,
# providing an interface to interact with the database using ORM techniques.
db = SQLAlchemy()


def create_app():
    """
    The create_app function is a factory that creates and configures an instance of a Flask application.
    The function is structured as a factory to allow for different instances of the application to be created,
    which is essential for scenarios such as testing or deployment in different environments.
    Each time this function is called, it sets up a new Flask application with its own configurations and contexts.
    """

    # Creating a Flask application instance. The Flask class instantiation creates an application object. The
    # 'instance_relative_config=True' argument allows the application to load configuration files from the instance
    # folder, providing a layer for private data separation.
    app = Flask(__name__, instance_relative_config=True)

    # Loading configuration from a file. This method loads the configuration settings from 'config.py' located in the
    # 'instance' folder. The settings may include database URLs, secret keys, and other environment-specific settings.
    app.config.from_pyfile(filename='config.py')

    # Enforcing security configurations for Flask-Talisman. This setting ensures that cookies related to user
    # sessions are sent over secure HTTPS connections only, enhancing the security of user data.
    app.config['SESSION_COOKIE_SECURE'] = True

    # Linking SQLAlchemy with the Flask app. The init_app method connects the SQLAlchemy instance with the created
    # Flask app, allowing ORM-based interactions with the database.
    db.init_app(app)

    # Importing models and blueprints. Models are Python classes that define the structure of database tables.
    # Blueprints are Flask's way to organize a group of related views and other code. They help to keep the
    # application modular and scalable.
    from .models import User, OAuth10a, OAuth20PKCE, UserReportedImpersonator
    from .unauth import unauth
    from .auth import auth
    from .oauth10a import oauth10a
    from .oauth20pkce import oauth20pkce
    from webapp.oauth10areport import oauth10areport
    from .error import (all_the_error_cries, TwitterAPIError, handle_error, handle_exception_error, forbidden,
                        handle_twitter_api_error, not_found, unauthorized, method_not_allowed, bad_request)

    # Registering blueprints with the application. This step involves linking the blueprints to the Flask app.
    # Blueprints define routes and views, enabling the app to handle various HTTP requests. Each blueprint can have
    # its own static files, templates, and URL prefixes.
    app.register_blueprint(unauth, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')
    app.register_blueprint(oauth10a, url_prefix='/')
    app.register_blueprint(oauth10areport, url_prefix='/')
    app.register_blueprint(oauth20pkce, url_prefix='/')
    app.register_blueprint(all_the_error_cries, url_prefix='/')

    # Creating database tables. Within the application context, this ensures that the necessary database tables are
    # created based on the models defined. It's a crucial step to prepare the database schema before handling any data.
    with app.app_context():
        db.create_all()

    # Setting up the login manager for user authentication. The LoginManager instance is responsible for managing
    # user sessions, providing a way to load users, and redirecting users to the login page when necessary.
    login_manager = LoginManager()
    login_manager.login_view = 'auth.authlogin'  # Setting the default view for logging in users.
    login_manager.init_app(app)  # Integrating the login manager with the Flask app.

    # User loader function for Flask-Login. This callback is used by Flask-Login to load a user object from a user ID
    # stored in the session. It's essential for tracking the current user and their authentication status.
    @login_manager.user_loader
    def load_user(email):
        """
        User loader for Flask-Login.

        This function retrieves a user object from the database using the user's email as an identifier. Flask-Login
        uses this function to manage user sessions, making it a cornerstone for user authentication in Flask.
        """
        return User.query.get(email)

    # Initializing Flask-Talisman for HTTP security headers. Talisman adds various HTTP security headers to protect
    # the app from common vulnerabilities like XSS, clickjacking, and others. Each setting like 'force_https' and
    # 'strict_transport_security' adds a layer of security.
    Talisman(app, force_https=True, session_cookie_secure=True, referrer_policy='no-referrer',
             strict_transport_security_max_age=63072000, strict_transport_security_preload=True,
             x_xss_protection=False)

    # Setting up logging to monitor Content Security Policy (CSP) violations. This is critical for identifying and
    # mitigating potential security threats, as CSP violations could indicate attempted or successful attacks.
    import logging
    logging.basicConfig(filename='csp_violations.log', level=logging.INFO)
    logger = app.logger
    logger.addHandler(logging.FileHandler('csp_violations.log'))

    # Returning the configured Flask application instance.
    # This instance is now ready to be used or run, with all configurations, routes, and handlers set up.
    return app


def create_database():
    """
    Function to create a database if it doesn't exist.

    This function checks the filesystem for the existence of the database file, as specified in the configuration. If
    the database file does not exist, it calls SQLAlchemy's create_all method to create a new database file with the
    defined schema. This is particularly useful in development and production environments for initializing the
    database.
    """
    if not path.isfile('../instance/' + DB_NAME):
        db.create_all()
        print('Created Database!')
