"""

    Get AccInfo by ID from Twitter showing if the account is suspended, not found, or what the latest information is.

"""

from instance import config
import requests
import json

bearer_token = config.BEARER_TOKEN


def create_url(user_id):
    """

    :param user_id:
    :return:
    """
    user_fields = "user.fields=description,created_at"
    # User fields are adjustable, options include:
    # created_at, description, entities, id, location, name,
    # pinned_tweet_id, profile_image_url, protected,
    # public_metrics, url, username, verified, and withheld
    url = f"https://api.twitter.com/2/users/{user_id}?{user_fields}"
    return url


def bearer_oauth(r):
    """
    Method required by bearer token authentication.
    """

    r.headers["Authorization"] = f"Bearer {bearer_token}"
    r.headers["User-Agent"] = "v2UserLookupPython"
    return r


def connect_to_endpoint(url):
    """

    :param url:
    :return:
    """
    response = requests.request("GET", url, auth=bearer_oauth, )
    print(response.status_code)
    if response.status_code != 200:
        raise Exception(
            "Request returned an error: {} {}".format(
                response.status_code, response.text
            )
        )
    return response.json()


def main():
    """

    :return:
    """
    user_id = input("Enter Twitter ID: ")
    url = create_url(user_id)
    json_response = connect_to_endpoint(url)
    print(json.dumps(json_response, indent=4, sort_keys=True))


if __name__ == "__main__":
    main()
