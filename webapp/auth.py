# Importing Flask modules and utilities for web application development.
from flask import Blueprint, render_template, request, flash, redirect, url_for, json, jsonify, abort
# - Blueprint: Organizes the app into distinct components, improving modularity.
# - render_template: Combines a given template with a data context and returns an HTML string.
# - request: Captures data sent from client to server, such as form submissions or query parameters.
# - flash: Sends temporary, user-facing messages, aiding in interactive feedback.
# - redirect: Programmatically navigates users to different URLs within the app.
# - url_for: Builds URLs dynamically, improving maintainability of URL structures.
# - json, jsonify: Converts data structures to and from JSON format, useful in API development.
# - abort: Provides a way to terminate a request early, typically when an error condition arises.

from flask_login import login_user, login_required, logout_user, current_user
# Flask-Login manages user sessions in a Flask application:
# - login_user: Sets up the user's session upon successful authentication.
# - login_required: Decorator that restricts view access to authenticated users.
# - logout_user: Clears the user's session, effectively logging them out.
# - current_user: Accesses the user object for the current session.

from werkzeug.security import generate_password_hash, check_password_hash
# Werkzeug Security provides password hashing utilities:
# - generate_password_hash: Securely hashes a plaintext password.
# - check_password_hash: Validates a provided password against the stored hash.

from .error import all_the_error_cries, TwitterAPIError
# Importing custom error handling functionalities to maintain consistent error responses.

from .models import User
# User model: Represents the structure of user data in the application's database.

from .forms import PostForm
# PostForm: A form handling class, useful for validating and processing form data.

from PIL import Image
# Python Imaging Library (PIL): A powerful library for opening, manipulating, and saving images.

from . import db
# Importing the database instance to enable database operations within this module.

import secrets
# secrets: Generates cryptographically strong random numbers, crucial for security-relevant applications.

import os
# os: Interacts with the operating system, particularly for file path and environment variable handling.

# Creating a Blueprint named 'auth' for handling authentication in the Flask application.
# This promotes a clean and modular codebase, segregating different functionalities.
auth = Blueprint('auth', __name__)


@auth.route('/authlogout')
@login_required
def authlogout():
    """
    Route to handle user logout. This function terminates the current user session.
    It ensures a secure logout by clearing session data and then redirects the user to the login page.
    The 'login_required' decorator ensures that only authenticated users can access this function.
    """
    logout_user()  # Ends the user's session.
    return redirect(url_for('auth.authlogin'))  # Redirects to the login page.


@auth.route('/authlogin', methods=['GET', 'POST'])
def authlogin():
    """
    Route to manage the login process for users, supporting both GET and POST methods.
    - GET: Renders the login page.
    - POST: Processes the submitted credentials. If valid, the user is logged in and redirected to the home page.
    Invalid credentials result in an error message being flashed to the user.
    The function utilizes 'flash' to provide feedback and 'login_user' to start a session for authenticated users.
    """
    if request.method == 'POST':
        # Retrieving submitted email and password from the login form.
        email = request.form.get('email')
        password = request.form.get('password')

        # Querying the database to find a user with the provided email.
        user = User.query.filter_by(email=email).first()
        # Validating the provided password against the stored hash.
        if user and check_password_hash(user.password, password):
            flash('Logged in successfully!', category='success')  # Successful login message.
            login_user(user, remember=True)  # Initiating a user session.
            return redirect(url_for('unauth.unauthhome'))  # Redirecting to the home page.
        else:
            # Flashing an error message for invalid credentials.
            flash('Invalid email or password.', category='error')

    # Rendering the login template on GET request or failed login attempt.
    return render_template("unauthlogin.html", user=current_user,
                           title="Login",
                           description=("Login to Benemortasia.com, a platform to "
                                        "manage Twitter Impersonators. Explore "
                                        "all the features by accessing your account."))


@auth.route('/authsignup', methods=['GET', 'POST'])
def authsignup():
    """
    Route to handle user registration, supporting both GET and POST methods.
    - GET: Renders the signup form.
    - POST: Processes and validates the submitted registration data.
    If validation passes, a new user account is created, and the user is logged in.
    The function performs checks for data integrity and uniqueness, flashes feedback messages,
    and employs password hashing for security.
    """
    if request.method == 'POST':
        # Extracting registration details from the form.
        email = request.form.get('email')
        account_name = request.form.get('accountName')
        password1 = request.form.get('password1')
        password2 = request.form.get('password2')

        # Checking for existing email or account name in the database.
        email_exists = User.query.filter_by(email=email).first()
        account_name_exists = User.query.filter_by(account_name=account_name).first()

        # Various validation checks for the user input.
        if email_exists:
            flash('Email is already in use.', category='error')
        elif len(email) < 4:
            flash('Email must be longer than 3 characters.', category='error')
        elif account_name_exists:
            flash('Account name is already taken.', category='error')
        elif len(account_name) < 2:
            flash('Account name must be longer than 1 character.', category='error')
        elif password1 != password2:
            flash('Passwords do not match.', category='error')
        elif len(password1) < 7:
            flash('Password must be at least 7 characters long.', category='error')
        else:
            # Hashing the password for secure storage.
            hashed_password = generate_password_hash(password1, method='sha512')
            new_user = User(email=email, account_name=account_name, password=hashed_password)
            db.session.add(new_user)  # Adding the new user to the database.
            db.session.commit()  # Committing the new user data to the database.
            login_user(new_user, remember=True)  # Logging in the new user.
            flash('Account successfully created!', category='success')
            return redirect(url_for('unauth.unauthhome'))

    # Rendering the signup page template with context data.
    return render_template("unauthsignup.html", user=current_user,
                           title="Register",
                           description=("Join Benemortasia.com to manage Twitter "
                                        "Impersonators. Our platform values privacy "
                                        "and security, allowing a separate email from "
                                        "your Twitter account for registration."))
