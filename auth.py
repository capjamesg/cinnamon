from flask import Flask, request, session, redirect, flash, render_template
from indieauth import requires_indieauth
import requests
from actions import *
from config import *
import hashlib
import base64
import string

auth = Flask(__name__, static_folder="static", static_url_path="")

@auth.route("/callback")
def indieauth_callback():
    code = request.args.get("code")
    state = request.args.get("state")

    if state != session.get("state"):
        flash("Your authentication failed. Please try again.")
        return redirect("/login")

    data = {
        "code": code,
        "redirect_uri": CALLBACK_URL,
        "client_id": CLIENT_ID,
        "grant_type": "authorization_code",
        "code_verifier": session["code_verifier"]
    }

    headers = {
        "Accept": "application/json"
    }

    r = requests.post(session.get("token_endpoint"), data=data, headers=headers)
    
    if r.status_code != 200:
        flash("There was an error with your token endpoint server.")
        return redirect("/login")

    # remove code verifier from session because the authentication flow has finished
    session.pop("code_verifier")

    if r.json().get("me").strip("/") != ME.strip("/"):
        flash("Your domain is not allowed to access this website.")
        return redirect("/login")

    session["me"] = r.json().get("me")
    session["access_token"] = r.json().get("access_token")

    return redirect("/")

@auth.route("/logout")
def logout():
    session.pop("me")
    session.pop("access_token")

    return redirect("/login")

@auth.route("/login", methods=["GET", "POST"])
def login():
    return render_template("auth.html", title="Webmention Dashboard Login")

@auth.route("/discover", methods=["POST"])
def discover_auth_endpoint():
    domain = request.form.get("me")

    r = requests.get(domain)

    soup = BeautifulSoup(r.text, "html.parser")

    authorization_endpoint = soup.find("link", rel="authorization_endpoint")

    if authorization_endpoint is None:
        flash("An IndieAuth authorization endpoint could not be found on your website.")
        return redirect("/login")

    if not authorization_endpoint.get("href").startswith("https://") and not authorization_endpoint.get("href").startswith("http://"):
        flash("Your IndieAuth authorization endpoint published on your site must be a full HTTP URL.")
        return redirect("/login")

    token_endpoint = soup.find("link", rel="token_endpoint")

    if token_endpoint is None:
        flash("An IndieAuth token ndpoint could not be found on your website.")
        return redirect("/login")

    if not token_endpoint.get("href").startswith("https://") and not token_endpoint.get("href").startswith("http://"):
        flash("Your IndieAuth token endpoint published on your site must be a full HTTP URL.")
        return redirect("/login")

    auth_endpoint = authorization_endpoint["href"]

    random_code = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(30))

    session["code_verifier"] = random_code
    session["authorization_endpoint"] = auth_endpoint
    session["token_endpoint"] = token_endpoint["href"]

    sha256_code = hashlib.sha256(random_code.encode('utf-8')).hexdigest()

    code_challenge = base64.b64encode(sha256_code.encode('utf-8')).decode('utf-8')

    state = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))

    session["state"] = state

    return redirect(auth_endpoint + "?client_id=" + CLIENT_ID + "&redirect_uri=" + CALLBACK_URL + "&scope=read follow mute block channels&response_type=code&code_challenge=" + code_challenge + "&code_challenge_method=S256&state=" + state)