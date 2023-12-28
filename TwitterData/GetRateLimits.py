import requests
from instance import config
from requests_oauthlib import OAuth1
from datetime import datetime

# Application credentials
consumer_key_app1 = config.API_AKA_CONSUMER_KEY
consumer_secret_app1 = config.API_AKA_CONSUMER_KEY_SECRET
access_token_app1 = config.ACCESS_TOKEN
access_token_secret_app1 = config.ACCESS_TOKEN_SECRET

consumer_key_app2 = config.API_AKA_CONSUMER_KEY_V2
consumer_secret_app2 = config.API_AKA_CONSUMER_KEY_SECRET_V2
access_token_app2 = config.ACCESS_TOKEN_V2
access_token_secret_app2 = config.ACCESS_TOKEN_SECRET_V2


def get_rate_limits(consumer_key, consumer_secret, access_token, access_token_secret):
    url = "https://api.twitter.com/1.1/application/rate_limit_status.json"
    auth = OAuth1(consumer_key, consumer_secret, access_token, access_token_secret)
    response = requests.get(url, auth=auth)
    if response.status_code == 200:
        return response.json()
    else:
        return f"Error: {response.status_code}"


def format_rate_limits(rate_limits):
    resource_order = ["search", "application", "users", "account_activity", "compliance",
                      "geo", "friendships", "direct_messages", "media", "lists", "graphql",
                      "tweets", "trends"]
    formatted_output = ""
    for resource in resource_order:
        if resource in rate_limits["resources"]:
            formatted_output += f"Resource: {resource}\n"
            for endpoint, data in rate_limits["resources"][resource].items():
                reset_time = datetime.fromtimestamp(data['reset']).strftime('%Y-%m-%d %H:%M:%S')
                formatted_output += f"  Endpoint: {endpoint}\n"
                formatted_output += f"    Limit: {data['limit']}\n"
                formatted_output += f"    Remaining: {data['remaining']}\n"
                formatted_output += f"    Reset Time: {reset_time}\n"
            formatted_output += "\n"
    return formatted_output


# Fetching rate limits for each application
rate_limits_app1 = get_rate_limits(consumer_key_app1, consumer_secret_app1, access_token_app1, access_token_secret_app1)
rate_limits_app2 = get_rate_limits(consumer_key_app2, consumer_secret_app2, access_token_app2, access_token_secret_app2)

print("Rate Limits for Application 1:")
print(format_rate_limits(rate_limits_app1))
print("\nRate Limits for Application 2:")
print(format_rate_limits(rate_limits_app2))
