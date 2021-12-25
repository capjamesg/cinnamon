from config import TOKEN_ENDPOINT, ME
import requests

def verify(headers, session):
    if headers.get("Authorization") != None:
        access_token = headers.get("Authorization").split(" ")[-1]
    elif session.get("access_token"):
        access_token = session.get("access_token")
    else:
        return False

    check_token = requests.get(TOKEN_ENDPOINT, headers={"Authorization": "Bearer " + access_token})

    if check_token.status_code != 200 or (check_token.json().get("me") and check_token.json()["me"] != ME):
        return False

    return True