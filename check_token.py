from flask import session
import requests
from .config import TOKEN_ENDPOINT, ME

def check_token():
    if not session.get("access_token"):
        return False

    check_token = requests.get(TOKEN_ENDPOINT, headers={"Authorization": "Bearer " + session["access_token"]})

    if check_token.status_code != 200 or (check_token.json().get("me") and check_token.json()["me"] != ME):
        return False

    return True