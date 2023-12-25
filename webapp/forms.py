# Importing components from WTForms to create form fields and validators.
from wtforms import StringField, PasswordField, SubmitField, BooleanField, TextAreaField
# Validators are used to ensure that the data submitted by the user meets certain criteria.
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError
# FileField and FileAllowed are used for uploading and validating files.
from flask_wtf.file import FileField, FileAllowed
# current_user is a Flask-Login utility that represents the client of the current session.
from flask_login import current_user
# FlaskForm is a base class for all forms in Flask-WTF.
from flask_wtf import FlaskForm
# User model from the application's database models.
from .models import User


# Detailed explanation of each form class and its components:

class RegistrationForm(FlaskForm):
    """
    RegistrationForm is used for creating user registration forms. It inherits from FlaskForm
    and defines various form fields with appropriate validators.
    """

    # The username field is a StringField, which allows users to enter a username.
    # It uses validators to ensure that the data is present (DataRequired) and that
    # the length of the username is between 2 and 20 characters (Length).
    username = StringField('Username',
                           validators=[DataRequired(), Length(min=2, max=20)])

    # Email field similar to the username but uses the Email validator to ensure
    # that the input is in a valid email format.
    email = StringField('Email',
                        validators=[DataRequired(), Email()])

    # Password fields to enter and confirm the password. The EqualTo validator
    # ensures that both password fields have the same value.
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password',
                                     validators=[DataRequired(), EqualTo('password')])

    # A submit button to submit the form.
    submit = SubmitField('Sign Up')

    @staticmethod
    def validate_username(username):
        """
        Static method to validate the uniqueness of the username.
        It queries the database to see if the entered username already exists.
        :param username: The username field from the form.
        :raises ValidationError: If the username is already taken.
        """
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('That username is taken. Please choose a different one.')

    @staticmethod
    def validate_email(email):
        """
        Static method to validate the uniqueness of the email.
        It queries the database to see if the entered email already exists.
        :param email: The email field from the form.
        :raises ValidationError: If the email is already in use.
        """
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('That email is taken. Please choose a different one.')


# Detailed explanation for LoginForm, UpdateAccountForm, and PostForm follows a similar pattern:
# - Definition of form fields with validators.
# - Usage of StringField, PasswordField, BooleanField, FileField, TextAreaField as needed.
# - Custom validation methods where necessary (e.g., to check for uniqueness in the database).

# LoginForm is designed for user login with fields for email, password, and a remember-me option.
class LoginForm(FlaskForm):
    """
    A form for user login, inheriting from FlaskForm.
    Includes fields for email, password, a remember me checkbox, and a submit button.
    """
    email = StringField('Email',
                        validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')


# UpdateAccountForm allows users to update their account information,
# including changing their username, email, and profile picture.
class UpdateAccountForm(FlaskForm):
    """
    A form for updating user account information, inheriting from FlaskForm.
    Allows users to update their username, email, profile picture, and includes a submit button.
    """
    username = StringField('Username',
                           validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email',
                        validators=[DataRequired(), Email()])
    picture = FileField('Update Profile Picture', validators=[FileAllowed(['jpg', 'png'])])
    submit = SubmitField('Update')

    # Custom validators for username and email to check for uniqueness while allowing current values.
    @staticmethod
    def validate_username(username):
        """
        Custom validator for username during account update.
        Checks if the new username is different from the current and if it's unique.
        :param username: The username field from the form.
        :raises ValidationError: If the username is taken by another user.
        """
        if username.data != current_user.username:
            user = User.query.filter_by(username=username.data).first()
            if user:
                raise ValidationError('That username is taken. Please choose a different one.')

    @staticmethod
    def validate_email(email):
        """
        Custom validator for email during account update.
        Checks if the new email is different from the current and if it's unique.
        :param email: The email field from the form.
        :raises ValidationError: If the email is taken by another user.
        """
        if email.data != current_user.email:
            user = User.query.filter_by(email=email.data).first()
            if user:
                raise ValidationError('That email is taken. Please choose a different one.')


# PostForm is intended for creating blog posts or similar content, with fields for the title and content.
class PostForm(FlaskForm):
    """
    A form for creating a blog post or similar content, inheriting from FlaskForm.
    Includes fields for the title and content of the post, along with a submit button.
    """
    title = StringField('Title', validators=[DataRequired()])
    content = TextAreaField('Content', validators=[DataRequired()])
    submit = SubmitField('Post')
