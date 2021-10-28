from flask import Blueprint, request, session, redirect, flash, render_template
import requests
from ..server.actions import *
from ..config import *
import hashlib
import base64
import string

auth = Blueprint('auth', __name__)

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

    granted_scopes = r.json().get("scope").split(" ")

    if r.json().get("scope") == "" or "read" not in granted_scopes or "channels" not in granted_scopes:
        flash("You need to grant 'read' and 'channels' access to use this tool.")
        return redirect("/login")

    session["me"] = r.json().get("me")
    session["access_token"] = r.json().get("access_token")
    session["scope"] = r.json().get("scope")

    return redirect("/")

@auth.route("/logout")
def logout():
    session.pop("me")
    session.pop("access_token")

    return redirect("/login")

@auth.route("/login", methods=["GET"])
def login():
    return render_template("auth.html", title="Microsub Dashboard Login")

@auth.route("/discover", methods=["POST"])
def discover_auth_endpoint():
    domain = request.form.get("me")

    r = requests.get(domain)

    soup = BeautifulSoup(r.text, "html.parser")

    http_link_headers = r.headers.get("link")

    authorization_endpoint_found = False
    token_endpoint_found = False

    if http_link_headers != None:
        parsed_link_headers = requests.utils.parse_header_links(r.links.rstrip('>').replace('>,<', ',<'))
    else:
        parsed_link_headers = []

    authorization_endpoint_in_header = [h for h in parsed_link_headers if h['rel'] == 'authorization_endpoint']

    if len(authorization_endpoint_in_header) > 0:
        authorization_endpoint = authorization_endpoint_in_header[0]['url']
        authorization_endpoint_found = True
    else:
        authorization_endpoint_search = soup.find("link", rel="authorization_endpoint")

        if authorization_endpoint_search:
            authorization_endpoint = authorization_endpoint_search["href"]
            authorization_endpoint_found = True

    if authorization_endpoint_found == False:
        flash("An IndieAuth authorization endpoint could not be found on your website.")
        return redirect("/login")

    if not authorization_endpoint.startswith("https://") and not authorization_endpoint.startswith("http://"):
        flash("Your IndieAuth authorization endpoint published on your site must be a full HTTP URL.")
        return redirect("/login")
        
    token_endpoint_in_header = [h for h in parsed_link_headers if h['rel'] == 'token_endpoint']

    if len(token_endpoint_in_header) > 0:
        token_endpoint = token_endpoint_in_header[0]['url']
        token_endpoint_found = True
    else:
        token_endpoint_search = soup.find("link", rel="token_endpoint")

        if token_endpoint_search:
            token_endpoint = token_endpoint_search["href"]
            token_endpoint_found = True
    
    if token_endpoint_found == False:
        flash("An IndieAuth token endpoint could not be found on your website.")
        return redirect("/login")

    if not token_endpoint.startswith("https://") and not token_endpoint.startswith("http://"):
        flash("Your IndieAuth token endpoint published on your site must be a full HTTP URL.")
        return redirect("/login")

    micropub_endpoint_in_header = [h for h in parsed_link_headers if h['rel'] == 'micropub']

    if len(micropub_endpoint_in_header) > 0:
        session["micropub_url"] = micropub_endpoint_in_header[0]['url']
    else:
        micropub_endpoint = soup.find("link", rel="micropub")

        if micropub_endpoint:
            session["micropub_url"] =  micropub_endpoint["href"]

    microsub_endpoint_in_header = [h for h in parsed_link_headers if h['rel'] == 'microsub']

    if len(microsub_endpoint_in_header) > 0:
        session["server_url"] = microsub_endpoint_in_header[0]['url']
    else:
        microsub_endpoint = soup.find("link", rel="microsub")

        if microsub_endpoint:
            session["server_url"] = microsub_endpoint["href"]
        else:
            flash("Your website does not have a microsub server. Please add a microsub server to your site header to use this service.")
            return redirect("/login")

    random_code = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(30))

    session["code_verifier"] = random_code
    session["authorization_endpoint"] = authorization_endpoint
    session["token_endpoint"] = token_endpoint

    sha256_code = hashlib.sha256(random_code.encode('utf-8')).hexdigest()

    code_challenge = base64.b64encode(sha256_code.encode('utf-8')).decode('utf-8')

    state = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))

    session["state"] = state

    print(authorization_endpoint)

    return redirect(authorization_endpoint + "?client_id=" + CLIENT_ID + "&redirect_uri=" + CALLBACK_URL + "&scope=read follow mute block channels create&response_type=code&code_challenge=" + code_challenge + "&code_challenge_method=S256&state=" + state)