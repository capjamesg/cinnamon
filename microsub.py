from flask import Flask, request, jsonify, send_from_directory, session, redirect, flash, render_template, current_app
import sqlite3
from indieauth import requires_indieauth
import requests
from actions import *
from config import *
import hashlib
import base64
import string
import os

app = Flask(__name__)

# read config.py file
app.config.from_pyfile(os.path.join(".", "config.py"), silent=False)

# set secret key
app.secret_key = SECRET_KEY

@app.route("/", methods=["GET", "POST"])
# @requires_indieauth
def home():
    print(session)
    if request.form:
        action = request.form.get("action")
        method = request.form.get("method")
    else:
        action = request.args.get("action")
        method = request.args.get("method")

    if not action:
        return render_template("index.html")
    
    if action == "timeline" and request.method == "GET":
        return get_timeline()
    elif action == "timeline" and request.method == "POST" and method == "remove":
        return remove_entry()
    elif action == "timeline" and request.method == "POST":
        return mark_as_read()
    elif action == "follow" and request.method == "GET":
        return get_follow()
    elif action == "follow" and request.method == "POST":
        return create_follow()
    elif action == "unfollow" and request.method == "POST":
        return unfollow()
    elif action == "mute" and request.method == "GET":
        return get_muted()
    elif action == "mute" and request.method == "POST":
        return mute()
    elif action == "unmute" and request.method == "POST":
        return unmute()
    elif action == "channels" and request.method == "GET":
        return get_channels()
    elif action == "channels" and request.method == "POST":
        if request.args.get("channel") and not method:
            return update_channel()
        elif request.form.get("channels") and method == "order":
            return reorder_channels()
        elif method == "delete":
            return delete_channel()
        else:
            return create_channel()
    else:
        return jsonify({"error": "invalid_request", "error_description": "The action and method provided are not valid."}), 400

@app.route("/channels")
@requires_indieauth
def dashboard():
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        all_channels = cursor.execute("SELECT * FROM channels ORDER BY position ASC;").fetchall()

        return render_template("dashboard.html", title="Microsub Dashboard", channels=all_channels)

@app.route("/feeds", methods=["GET", "POST"])
@requires_indieauth
def feed_list():
    if request.method == "POST":
        req = {
            "action": "follow",
            "channel": request.form.get("channel"),
            "url": request.form.get("url")
        }

        r = requests.post(URL, data=req, headers={'Authorization': 'Bearer ' + session["access_token"]})

        if r.status_code == 200:
            connection = sqlite3.connect("microsub.db")

            with connection:
                cursor = connection.cursor()

                get_channel_by_id = cursor.execute("SELECT channel FROM channels WHERE uid = ?", (req["channel"], )).fetchone()

                flash("You are now following {} in the {} channel.".format(request.form.get("url"), get_channel_by_id[0]))
        else:
            flash("Something went wrong. Please try again.")

        return redirect("/feeds")

    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        all_channels = cursor.execute("SELECT * FROM channels ORDER BY position ASC;").fetchall()

        return render_template("feed_management.html", title="Feed Management | Microsub Dashboard", channels=all_channels)

@app.route("/reorder", methods=["POST"])
@requires_indieauth
def reorder_channels_view():
    if request.form.get("channel"):
        req = {
            "action": "channels",
            "method": "order",
            "channels": request.form.getlist("channel")
        }

        r = requests.post(URL, data=req, headers={'Authorization': 'Bearer ' + session["access_token"]})

        if r.status_code == 200:
            flash("Your channels have been reordered.")
        else:
            flash(r.json()["error"])

        return redirect("/channels")
    else:
        return redirect("/channels")

@app.route("/create-channel", methods=["POST"])
@requires_indieauth
def create_channel_view():
    if request.form.get("name"):
        req = {
            "action": "channels",
            "name": request.form.get("name")
        }

        r = requests.post(URL, data=req, headers={'Authorization': 'Bearer ' + session["access_token"]})

        if r.status_code == 200:
            flash("You have created a new channel called {}.".format(request.form.get("name")))
        else:
            flash(r.json()["error"])

        return redirect("/channels")
    else:
        return redirect("/channels")

@app.route("/delete-channel", methods=["POST"])
@requires_indieauth
def delete_channel_view():
    if request.form.get("channel"):
        req = {
            "action": "channels",
            "channel": request.form.get("channel"),
            "method": "delete"
        }

        r = requests.post(URL, data=req, headers={"Authorization": session["access_token"]})

        if r.status_code == 200:
            flash("You have deleted the {} channel.".format(r.json()["channel"]))
        else:
            flash(r.json()["error"])

        return redirect("/channels")
    else:
        return redirect("/channels")

@app.route("/unfollow", methods=["POST"])
@requires_indieauth
def unfollow_view():
    if request.form.get("channel") and request.form.get("url"):
        req = {
            "action": "unfollow",
            "channel": request.form.get("channel"),
            "url": request.form.get("url")
        }

        r = requests.post(URL, data=req, headers={"Authorization": session.get("access_token")})

        if r.status_code == 200:
            return jsonify(r.json()), 200
        else:
            return jsonify(r.json()), 400
    else:
        return redirect("/feeds")

@app.route("/callback")
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

@app.route("/logout")
@requires_indieauth
def logout():
    session.pop("me")
    session.pop("access_token")

    return redirect("/home")

@app.route("/discover", methods=["POST"])
def discover_auth_endpoint():
    domain = request.form.get("me")

    r = requests.get(domain)

    soup = BeautifulSoup(r.text, "html.parser")

    authorization_endpoint = soup.find("link", rel="authorization_endpoint")

    if authorization_endpoint is None:
        flash("An IndieAuth authorization ndpoint could not be found on your website.")
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

@app.route("/login", methods=["GET", "POST"])
def login():
    return render_template("auth.html", title="Webmention Dashboard Login")

@app.route("/discover-feed", methods=["POST"])
@requires_indieauth
def discover_feed():
    url = request.form.get("url")

    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    elif url.startswith("//"):
        url = "https:" + url

    soup = BeautifulSoup(requests.get(url).text, "html.parser")

    # check for presence of mf2 hfeed
    h_feed = soup.find_all(class_="h-feed")

    feeds = []

    if soup.find("link", rel="alternate", type="application/atom+xml"):
        feeds.append(soup.find("link", rel="alternate", type="application/atom+xml").get("href"))
        flash("Atom feed found at {}".format(url + soup.find("link", rel="alternate", type="application/atom+xml")["href"]))
    if soup.find("link", rel="alternate", type="application/rss+xml"):
        feeds.append(soup.find("link", rel="alternate", type="application/rss+xml").get("href"))
        flash("RSS feed found at {}".format(url + soup.find("link", rel="alternate", type="application/rss+xml")["href"]))
    if soup.find("link", rel="feed", type="text/html"):
        # used for mircoformats rel=feed discovery
        feeds.append(soup.find("link", rel="feed", type="text/html").get("href"))
        flash("h-feed found at {}".format(url + soup.find("link", rel="feed", type="text/html")["href"]))

    if h_feed and len(h_feed) > 0:
        feeds.append(url)
        flash("h-feed found at {}".format(url))

    if len(feeds) == 0:
        flash("No feed could be found attached to the web page you submitted.")
    
    return redirect("/feeds")

@app.route("/channel/<id>", methods=["GET", "POST"])
@requires_indieauth
def modify_channel(id):
    connection = sqlite3.connect("microsub.db")

    if request.method == "POST":
        req = {
            "action": "channels",
            "channel": request.form.getlist("channel"),
            "name": request.form.get("name"),
        }

        r = requests.post(URL, data=req, headers={"Authorization": session.get("access_token")})

        if r.status_code == 200:
            flash("The channel was successfully renamed to {}".format(request.form.get("name")))
        else:
            flash("Something went wrong. Please try again.")

    with connection:
        cursor = connection.cursor()
        channel = cursor.execute("SELECT * FROM channels WHERE uid = ?", (id,)).fetchone()
        feeds = cursor.execute("SELECT * FROM following WHERE channel = ?", (id,)).fetchall()

        return render_template("modify_channel.html", title="Modify {} Channel".format(channel[0]), channel=channel, feeds=feeds)

@app.route("/assets/<path:path>")
def assets(path):
    return send_from_directory("assets", path)

@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html", title="Page not found", error=404), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return render_template("404.html", title="Method not allowed", error=405), 405

@app.errorhandler(500)
def server_error(e):
    return render_template("404.html", title="Server error", error=500), 500

if __name__ == "__main__":
    app.run()