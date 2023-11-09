from flask import Blueprint, render_template, request, flash, redirect, url_for, json, jsonify, abort
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from .error import all_the_error_cries, TwitterAPIError
from .models import User
from .forms import PostForm
from PIL import Image
from . import db
import secrets
import os


auth = Blueprint('auth', __name__)


@auth.route('/authlogout')
@login_required
def authlogout():
    logout_user()
    return redirect(url_for('auth.authlogin'))


@auth.route('/authlogin', methods=['GET', 'POST'])
def authlogin():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user:

            if check_password_hash(user.password, password):

                flash('Logged in successfully!', category='success')

                login_user(user, remember=True)
                return redirect(url_for('unauth.unauthhome'))
            else:
                flash('Incorrect password, try again.', category='error')
        else:
            flash('Email does not exist.', category='error')

    return render_template(
        "unauthlogin.html", user=current_user, title="login", description="Login to Benemortasia.com, a tool to manage "
                                                                          "Twitter Impersonators for our beloved Crypto"
                                                                          " Channels with ease. Access your account to "
                                                                          "explore all the content and features of this"
                                                                          " web application.")


@auth.route('/authsignup', methods=['GET', 'POST'])
def authsignup():
    if request.method == 'POST':
        email = request.form.get('email')
        account_name = request.form.get('accountName')
        password1 = request.form.get('password1')
        password2 = request.form.get('password2')

        email_exists = User.query.filter_by(email=email).first()
        account_name_exists = User.query.filter_by(account_name=account_name).first()

        if email_exists:
            flash('Email already exists.', category='error')
        elif len(email) < 4:
            flash('Email must be greater than 3 characters.', category='error')
        elif account_name_exists:
            flash('Account name already exists.', category='error')
        elif len(account_name) < 2:
            flash('Account name must be greater than 1 character.', category='error')
        elif password1 != password2:
            flash('Passwords don\'t match.', category='error')
        elif len(password1) < 7:
            flash('Password must be at least 7 characters.', category='error')

        else:
            # SECURITY - Here we use Werkzeug to HASH the password using SHA512 instead of storing plain text.
            new_user = User(
                email=email, account_name=account_name, password=generate_password_hash(password1, method='sha512')
            )
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user, remember=True)
            flash('Account created!', category='success')
            return redirect(url_for('unauth.unauthhome'))
    return render_template(
        "unauthsignup.html", user=current_user, title="register", description="Register an account at Benemortasia.com,"
                                                                              " a tool to manage Twitter Impersonators "
                                                                              "for our beloved Crypto Channels with eas"
                                                                              "e. Join our community for access to uniq"
                                                                              "ue content and features. You do not have"
                                                                              " to use your e-mail you are using for yo"
                                                                              "ur Twitter account. In fact I take expli"
                                                                              "cit efforts to not use your Twitter acco"
                                                                              "unts email.")
