from instance import config
import requests
import json

# MY API TOKEN - BEARER TOKEN
bearer_token = config.BEARER_TOKEN_V2


def create_url_by_username(username):
    """
    id: The unique identifier of this user.
    name: The name of the user, as they’ve defined it on their profile.
    username: The Twitter screen name, handle, or alias that this user identifies themselves with.
    created_at: The UTC datetime that the user account was created on Twitter.
    description: The text of this user's profile description (also known as bio), if the user provided one.
    entities: Contains details about text that has a special meaning in the user's description.
    location: The location specified in the user's profile, if the user provided one.
    pinned_tweet_id: Unique identifier of this user's pinned Tweet.
    profile_image_url: The URL to the profile image for this user, as shown on the user's profile.
    protected: Indicates if this user has chosen to protect their Tweets
               (in other words, if this user's Tweets are private).
    public_metrics: Contains details about activity for this user.
    url: The URL specified in the user's profile, if present.
    verified: Indicates if this user is a verified Twitter User.
    withheld: Contains withholding details for withheld content, if applicable.
    """
    user_fields = ("user.fields=id,name,username,created_at,description,"
                   "public_metrics,location,url,verified,profile_image_url,"
                   "protected,entities,pinned_tweet_id,withheld,blocked_by,blocking,"
                   "follow_request_sent,muting,profile_background_color,profile_background_image_url,"
                   "profile_banner_url,profile_text_color,translator_type,withheld")

    """
    attachments: Contains information about any attached media, URLs, or polls.
    author_id: The unique identifier of the author of this Tweet.
    context_annotations: Contains context annotations including domain and entity IDs.
    conversation_id: The unique identifier of the conversation this Tweet is part of.
    created_at: The UTC datetime when this Tweet was created.
    entities: Contains details about text that has a special meaning in the Tweet, such as hashtags, 
              URLs, user mentions, and cashtags.
    geo: Contains details about the location tagged in the Tweet, if the user has enabled location tagging.
    id: The unique identifier of this Tweet.
    in_reply_to_user_id: The unique identifier of the User this Tweet is in reply to, if applicable.
    lang: The language of the Tweet, if detected by Twitter. Returned as a BCP47 language tag.
    public_metrics: Contains details about public engagement with the Tweet.
    referenced_tweets: Contains details about Tweets this Tweet refers to.
    reply_settings: Indicates who can reply to this Tweet. Returned as either "everyone", 
                    "mentioned_users", or "followers".
    source: The name of the app the user Tweeted from.
    text: The text of the Tweet.
    withheld: Contains withholding details for withheld content, if applicable.
    non_public_metrics: Contains non-public engagement metrics of the Tweet (requires user context).
    organic_metrics: Contains organic engagement metrics of the Tweet (requires user context).
    promoted_metrics: Contains promoted engagement metrics of the Tweet (requires user context).
    possibly_sensitive: Indicates whether this Tweet contains URLs marked as sensitive, for example, by link shorteners.
    filter_level: Indicates the maximum value of the filter_level parameter which may be used and still stream this
                  Tweet. So a value of medium will be streamed on none, low, and medium streams.
    """
    tweet_fields = ("tweet.fields=attachments,author_id,context_annotations,"
                    "conversation_id,created_at,entities,geo,id,in_reply_to_user_id,"
                    "lang,public_metrics,referenced_tweets,reply_settings,source,"
                    "text,withheld,non_public_metrics,organic_metrics,promoted_metrics,"
                    "possibly_sensitive,filter_level")
    """
    attachments.poll_ids: Expands to an array of Polls included in the Tweet.
    attachments.media_keys: Expands to an array of Media included in the Tweet.
    author_id: Expands to the User who authored the Tweet.
    entities.mentions.username: Expands to an array of Users mentioned in the Tweet.
    geo.place_id: Expands to a Place associated with the location tagged in the Tweet.
    in_reply_to_user_id: Expands to the User mentioned in the parent Tweet of a conversation.
    referenced_tweets.id: Expands to an array of Tweets mentioned in the conversation.
    referenced_tweets.id.author_id: Expands to an array of Users who authored referenced Tweets in the conversation.
    """
    expansions = ("expansions=pinned_tweet_id,attachments.media_keys,referenced_tweets.id,"
                  "entities.mentions.username,entities.hashtags,geo.place_id,"
                  "author_id,in_reply_to_user_id,attachments.poll_ids,referenced_tweets.id.author_id")

    """
    media_key: Unique identifier of the media.
    type: Type of media (photo, video, animated GIF).
    duration_ms: Duration of the media in milliseconds (for videos and GIFs).
    height: Height of media in pixels.
    width: Width of media in pixels.
    preview_image_url: URL of the media preview image (for videos and GIFs).
    url: URL of the media.
    public_metrics: Public engagement metrics of the media.
    non_public_metrics: Non-public engagement metrics of the media (requires user context).
    organic_metrics: Organic engagement metrics of the media (requires user context).
    promoted_metrics: Promoted engagement metrics of the media (requires user context).
    alt_text: Alternative text description of the media.
    description: Description of the media.
    """
    media_fields = ("media.fields=duration_ms,height,media_key,preview_image_url,"
                    "type,url,width,public_metrics,non_public_metrics,organic_metrics,"
                    "promoted_metrics,alt_text,description")

    """
    contained_within: Returns the identifiers of known places that contain the referenced place.
    country: The full-length name of the country this place belongs to.
    country_code: The ISO Alpha-2 country code this place belongs to.
    full_name: A longer-form detailed place name.
    geo: Contains place details in GeoJSON format.
    id: The unique identifier of the expanded place, if this is a point of interest tagged in the Tweet.
    name: The short name of this place.
    place_type: Specifies the particular type of information represented by this place information,
                such as a city name, or a point of interest.
    """
    place_fields = "place.fields=contained_within,country,country_code,full_name,geo,id,name,place_type"

    """
    id: Unique identifier of the expanded poll.
    options: Contains objects describing each choice in the referenced poll.
    duration_minutes: Specifies the total duration of this poll.
    end_datetime: Specifies the end date and time for this poll.
    voting_status: Indicates if this poll is still active and can receive votes, or if the voting is now closed.
    """
    poll_fields = "poll.fields=duration_minutes,end_datetime,id,options,voting_status"

    url = (f"https://api.twitter.com/2/users/by/username/{username}?{user_fields}&{tweet_fields}"
           f"&{expansions}&{media_fields}&{place_fields}&{poll_fields}")

    return url


def get_users_tweets(username):
    tweet_fields = ("tweet.fields=attachments,author_id,context_annotations,"
                    "conversation_id,created_at,entities,geo,id,in_reply_to_user_id,"
                    "lang,public_metrics,referenced_tweets,reply_settings,source,"
                    "text,withheld")

    url = f"https://api.twitter.com/2/tweets/search/recent?query=from:{username}&{tweet_fields}"
    response = connect_to_endpoint(url)
    print(json.dumps(response, indent=4, sort_keys=True))


def get_user_timeline(username):
    tweet_fields = ("tweet.fields=attachments,author_id,context_annotations,"
                    "conversation_id,created_at,entities,geo,id,in_reply_to_user_id,"
                    "lang,public_metrics,referenced_tweets,reply_settings,source,"
                    "text,withheld")

    url = f"https://api.twitter.com/2/tweets/timeline?query=from:{username}&{tweet_fields}"
    response = connect_to_endpoint(url)
    print(json.dumps(response, indent=4, sort_keys=True))


def bearer_oauth(r):
    r.headers["Authorization"] = f"Bearer {bearer_token}"
    r.headers["User-Agent"] = "v2UserLookupPython"
    return r


def connect_to_endpoint(url):
    response = requests.request("GET", url, auth=bearer_oauth)
    if response.status_code != 200:
        raise Exception(
            f"Request returned an error: {response.status_code}, {response.text}"
        )
    return response.json()


# Twitter API v2
def get_user_info_v2(username):
    url = f"https://api.twitter.com/2/users/by/username/{username}?user.fields=public_metrics,pinned_tweet_id,withheld"
    headers = {"Authorization": f"Bearer {bearer_token}"}
    response = requests.get(url, headers=headers)
    return response.json()


# Twitter API v1.1
def get_user_info_v1(username):
    url = f"https://api.twitter.com/1.1/users/show.json?screen_name={username}&include_entities=true"
    headers = {"Authorization": f"Bearer {bearer_token}"}
    response = requests.get(url, headers=headers)
    return response.json()


# Combine data from both APIs
def get_combined_user_info(username):
    info_v2 = get_user_info_v2(username)
    info_v1 = get_user_info_v1(username)

    # Combine the data (update v2 data with v1 data)
    combined_info = info_v2.get('data', {})
    combined_info.update(info_v1)

    return combined_info


def main():
    username = input("Please enter a Twitter username: ")
    combined_info = get_combined_user_info(username)
    print(json.dumps(combined_info, indent=4, sort_keys=True))


if __name__ == "__main__":
    main()
