from .config import TOKEN_ENDPOINT, ME
import requests

def check_token(token):
    if not token:
        return False

    check_token = requests.get(TOKEN_ENDPOINT, headers={"Authorization": "Bearer " + token})

    if check_token.status_code != 200 or (check_token.json().get("me") and check_token.json()["me"] != ME):
        return False

    return True