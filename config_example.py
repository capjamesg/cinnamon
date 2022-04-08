CLIENT_ID = "https://example.com"  # url at which you will host your server
CALLBACK_URL = CLIENT_ID + "/callback"
ME = "https://example.com"  # your domain name

SECRET_KEY = ""  # set this to a long, random string

PROJECT_DIRECTORY = "/home/username/"  # the root directory of the project

SERVER_API_WEBHOOK = False  # whether or not to use the server API webhook
WEBHOOK_CHANNEL = (
    "channel_name"  # the channel to which new posts should be sent via a webhook
)
WEBHOOK_TOKEN = "auth_token"  # the auth token to be sent in an Authorization header with the webhook

SENTRY_DSN = "sentry_url"  # your sentry logging URL (if you want to log with Sentry)
SENTRY_SERVER_NAME = (
    "Microsub Client and Server"  # the name of your server for use in Sentry
)

TWITTER_BEARER_TOKEN = ""  # used to generate reply contexts in the post editor
