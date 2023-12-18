"""
 Pretty-Much Perfect
"""
import os
import json
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker, scoped_session
from update_database import TwitterAccount  # Assuming this import works as intended

# Database setup
base_dir = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(base_dir, "TwitterData", "SQL-ImpersonatorAccounts", "ImpersonatorAccounts.sqlite")
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
engine = create_engine(DATABASE_URL)
Session = scoped_session(sessionmaker(bind=engine))

# Logging setup
logs_dir = os.path.join(base_dir, "logs")
os.makedirs(logs_dir, exist_ok=True)
log_filename = os.path.join(logs_dir, "Correct_Database.log")

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# File handler for detailed logs
file_handler = RotatingFileHandler(log_filename, maxBytes=int(49.9 * 1024 * 1024), backupCount=1, encoding='utf-8')
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Console handler for brief messages
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# Disable SQLAlchemy's own logger to console
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)


def log_issue(issue_description, account):
    """

    :param issue_description:
    :param account:
    :return:
    """
    detail = f"{issue_description} in account: {account.username} (ID: {account.twitter_id})"
    logger.warning(detail)
    print(detail)


def is_valid_json(json_string):
    """

    :param json_string:
    :return:
    """
    try:
        if isinstance(json_string, str):
            json.loads(json_string)
        return True
    except json.JSONDecodeError:
        return False


def check_for_duplicates(session):
    """

    :param session:
    :return:
    """
    # Adjusted query to check for duplicates in a case-insensitive manner
    duplicate_usernames = session.query(func.lower(TwitterAccount.username)).group_by(
        func.lower(TwitterAccount.username)).having(
        func.count(TwitterAccount.username) > 1).all()
    duplicate_twitter_ids = session.query(TwitterAccount.twitter_id).group_by(TwitterAccount.twitter_id).having(
        func.count(TwitterAccount.twitter_id) > 1).all()

    if duplicate_usernames or duplicate_twitter_ids:
        logger.warning("Duplicate entries found!")
        if duplicate_usernames:
            logger.warning(f"Duplicate Usernames: {[u[0] for u in duplicate_usernames]}")
        if duplicate_twitter_ids:
            logger.warning(f"Duplicate Twitter IDs: {[tid[0] for tid in duplicate_twitter_ids]}")
    else:
        logger.info("No duplicate entries found.")


def check_data_integrity(session):
    """

    :param session:
    :return:
    """
    accounts = session.query(TwitterAccount).all()
    for account in accounts:
        # Check for negative or None values in numeric fields only if Twitter ID is missing and account is active
        if not account.twitter_id and account.suspended == 0 and account.unresolvable == 0:
            numeric_fields = [account.followers_count, account.following_count, account.tweet_count,
                              account.listed_count]
            if any(x is None or (isinstance(x, int) and x < 0) for x in numeric_fields):
                log_issue("Invalid values in numeric fields in active account with no Twitter ID", account)

        # Check for valid datetime objects or None in date fields
        date_fields = [account.created_at, account.suspended_date, account.username_changed_date,
                       account.api_response_updated_at, account.previous_api_response_updated_at]
        if any(dt is not None and not isinstance(dt, datetime) for dt in date_fields):
            log_issue("Invalid date value", account)

        # Check API response formats
        if account.api_response and not is_valid_json(account.api_response):
            log_issue("Invalid API response format", account)
        if account.previous_api_response and not is_valid_json(account.previous_api_response):
            log_issue("Invalid previous API response format", account)

        # Check username change logic
        if account.username_changed:
            if not account.previous_username or account.username in account.previous_username:
                log_issue("Username change inconsistency", account)
            if not account.username_changed_date:
                log_issue("Missing username change date", account)

        # Check unresolvable accounts
        if account.unresolvable and not (account.api_response or account.previous_api_response):
            log_issue("Unresolvable account missing API response", account)

        # Check for missing Twitter ID only if the account is not suspended and not unresolvable
        if not account.twitter_id and account.suspended == 0 and account.unresolvable == 0:
            log_issue("Missing Twitter ID in active account", account)

        # Additional checks based on other fields can be added here


def prompt_for_correction():
    """

    :return:
    """
    response = input("Duplicate Usernames found. Do you want to correct/fix the database? (Y/N) ").strip().lower()
    return response == 'y'


def verify_duplicates(session, duplicates):
    """

    :param session:
    :param duplicates:
    :return:
    """
    for dup in duplicates:
        accounts = session.query(TwitterAccount).filter(func.lower(TwitterAccount.username) == dup[0]).all()

        if len(accounts) != 2:
            logger.warning(f"More than two accounts found for username {dup[0]}, manual review recommended.")
            continue

        suspended_accounts = [acc for acc in accounts if acc.suspended]
        active_accounts = [acc for acc in accounts if not acc.suspended]

        if len(suspended_accounts) != 1 or len(active_accounts) != 1:
            logger.warning(
                f"Expected one active and one suspended account for username {dup[0]}, "
                f"found {len(active_accounts)} active and {len(suspended_accounts)} suspended.")
            continue

        yield active_accounts[0], suspended_accounts[0]


def display_account_details(account):
    """

    :param account:
    :return:
    """
    details = f"ID: {account.id}, Twitter ID: {account.twitter_id}, Username: {account.username}, " \
              f"Suspended: {account.suspended}, Suspended Date: {account.suspended_date}, " \
              f"Unresolvable: {account.unresolvable}"
    return details


def handle_duplicate_accounts(session, active_account, duplicate_account):
    """

    :param session:
    :param active_account:
    :param duplicate_account:
    :return:
    """
    # Determine the status for the duplicate entry
    if duplicate_account.suspended:
        status = 'suspended'
    elif duplicate_account.unresolvable:
        status = 'unresolvable'
    else:
        status = 'active'

    # Print the details
    print(f"\nDuplicate username: {active_account.username}")
    print(f"Original entry: {display_account_details(active_account)}")
    print(f"Duplicate entry: {status}")

    response = input("Do you want to merge this duplicate? (Y/N) ").strip().lower()
    if response == 'y':
        if duplicate_account.suspended:
            active_account.suspended = True
            active_account.suspended_date = duplicate_account.suspended_date
        elif duplicate_account.unresolvable:
            active_account.unresolvable = True

        session.delete(duplicate_account)
        session.commit()
        print(f"Merged and removed duplicate for '{active_account.username}'.")
    else:
        print("Merge skipped.")


def fix_duplicates(session, duplicates):
    """

    :param session:
    :param duplicates:
    :return:
    """
    for dup in duplicates:
        accounts = session.query(TwitterAccount).filter(func.lower(TwitterAccount.username) == dup[0]).order_by(
            TwitterAccount.id).all()

        if len(accounts) != 2:
            logger.warning(
                f"Unexpected number of accounts found for username {dup[0]}. Expected 2, found {len(accounts)}.")
            continue

        # Assuming the first account in the ordered list is the original
        original_account, duplicate_account = accounts

        handle_duplicate_accounts(session, original_account, duplicate_account)


def main():
    """

    :return:
    """
    with Session() as session:
        logger.info("Checking for duplicate entries...")
        duplicates = session.query(func.lower(TwitterAccount.username)).group_by(
            func.lower(TwitterAccount.username)).having(
            func.count(TwitterAccount.username) > 1).all()

        if duplicates:
            logger.warning("Duplicate Usernames found.")
            if prompt_for_correction():
                logger.info("Correcting duplicates...")
                fix_duplicates(session, duplicates)
                logger.info("Duplicates corrected.")
            else:
                logger.info("Duplicate correction skipped.")
        else:
            logger.info("No duplicate entries found.")

        logger.info("Checking data integrity...")
        check_data_integrity(session)


if __name__ == "__main__":
    main()
