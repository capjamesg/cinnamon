from flask import Blueprint, request, jsonify, session, redirect, flash, render_template
from indieauth import requires_indieauth
from .check_token import check_token
import datetime
import sqlite3
import requests
from .discovery import *
from .actions import *
from .config import *

main = Blueprint('main', __name__, template_folder='templates')

@main.route("/")
def index():
    return render_template("index.html", title="Home | Microsub Endpoint")

@main.route("/setup")
def setup():
    return render_template("setup.html", title="Setup | Microsub Endpoint")

@main.route("/endpoint", methods=["GET", "POST"])
@requires_indieauth
def home():
    if request.form:
        action = request.form.get("action")
        method = request.form.get("method")
        channel = request.form.get("channel")
        query = request.form.get("query")
    else:
        action = request.args.get("action")
        method = request.args.get("method")
        channel = request.args.get("channel")
        query = request.args.get("query")

    if not action:
        return jsonify({"error": "No action specified."}), 400
    
    if action == "timeline" and request.method == "GET":
        return get_timeline()
    elif action == "timeline" and request.method == "POST" and method == "remove":
        return remove_entry()
    elif action == "timeline" and request.method == "POST":
        return mark_as_read()
    elif action == "preview" and request.method == "POST":
        return preview()
    elif action == "search" and query and request.method == "POST":
        return search_for_content()
    elif action == "follow" and request.method == "GET":
        return get_follow(channel)
    elif action == "follow" and request.method == "POST":
        return create_follow()
    elif action == "unfollow" and request.method == "POST":
        return unfollow()
    elif action == "block" and request.method == "POST":
        return block()
    elif action == "unblock" and request.method == "POST":
        return unblock()
    elif action == "mute" and request.method == "GET":
        return get_muted()
    elif action == "mute" and request.method == "POST":
        return mute()
    elif action == "unmute" and request.method == "POST":
        return unmute()
    elif action == "channels" and request.method == "GET":
        return get_channels()
    elif action == "channels" and request.method == "POST":
        if request.form.get("name") and request.form.get("channel"):
            return update_channel()
        elif request.form.get("channels") and method == "order":
            return reorder_channels()
        elif method == "delete":
            return delete_channel()
        else:
            return create_channel()
    else:
        return jsonify({"error": "invalid_request", "error_description": "The action and method provided are not valid."}), 400

@main.route("/channels")
def dashboard():
    auth_result = check_token()

    if auth_result == False:
        return redirect("/login")

    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        all_channels = cursor.execute("SELECT * FROM channels ORDER BY position ASC;").fetchall()

        return render_template("server/dashboard.html", title="Microsub Dashboard", channels=all_channels)

@main.route("/feeds", methods=["GET", "POST"])
def feed_list():
    auth_result = check_token()

    if auth_result == False:
        return redirect("/login")

    if request.method == "POST":
        req = {
            "action": "follow",
            "channel": request.form.get("channel"),
            "url": request.form.get("url")
        }

        r = requests.post(session.get("server_url"), data=req, headers={'Authorization': 'Bearer ' + session["access_token"]})

        if r.status_code == 200:
            flash("You are now following {}".format(request.form.get("url"), ))
        else:
            flash(r.json()["error"])

        return redirect("/reader/all")

    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        all_channels = cursor.execute("SELECT * FROM channels ORDER BY position ASC;").fetchall()

        return render_template("server/feed_management.html", title="Feed Management | Microsub Dashboard", channels=all_channels)

@main.route("/reorder", methods=["POST"])
def reorder_channels_view():
    auth_result = check_token()

    if auth_result == False:
        return redirect("/login")

    if request.form.get("channel"):
        req = {
            "action": "channels",
            "method": "order",
            "channels": request.form.getlist("channel")
        }

        r = requests.post(session.get("server_url"), data=req, headers={'Authorization': 'Bearer ' + session["access_token"]})

        if r.status_code == 200:
            flash("Your channels have been reordered.")
        else:
            flash(r.json()["error"])

        return redirect("/channels")
    else:
        return redirect("/channels")

@main.route("/create-channel", methods=["POST"])
def create_channel_view():
    auth_result = check_token()

    if auth_result == False:
        return redirect("/login")

    if request.form.get("name"):
        req = {
            "action": "channels",
            "name": request.form.get("name")
        }

        r = requests.post(session.get("server_url"), data=req, headers={'Authorization': 'Bearer ' + session["access_token"]})

        if r.status_code == 200:
            flash("You have created a new channel called {}.".format(request.form.get("name")))
        else:
            flash(r.json()["error"])

        return redirect("/channels")
    else:
        return redirect("/channels")

@main.route("/delete-channel", methods=["POST"])
def delete_channel_view():
    auth_result = check_token()

    if auth_result == False:
        return redirect("/login")

    if request.form.get("channel"):
        req = {
            "action": "channels",
            "channel": request.form.get("channel"),
            "method": "delete"
        }

        r = requests.post(session.get("server_url"), data=req, headers={"Authorization": session["access_token"]})

        if r.status_code == 200:
            flash("You have deleted the {} channel.".format(r.json()["channel"]))
        else:
            flash(r.json()["error"])

        return redirect("/channels")
    else:
        return redirect("/channels")

@main.route("/unfollow", methods=["POST"])
def unfollow_view():
    auth_result = check_token()

    if auth_result == False:
        return redirect("/login")

    if request.form.get("channel") and request.form.get("url"):
        req = {
            "action": "unfollow",
            "channel": request.form.get("channel"),
            "url": request.form.get("url")
        }

        r = requests.post(session.get("server_url"), data=req, headers={"Authorization": session.get("access_token")})

        if r.status_code == 200:
            return redirect("/reader/{}".format(request.form.get("channel")))
        else:
            return redirect("/reader/all")
    else:
        return redirect("/feeds")
        
@main.route("/discover-feed", methods=["POST"])
def discover_feed():
    auth_result = check_token()

    if auth_result == False:
        return redirect("/login")

    url = request.form.get("url")
    channel = request.form.get("channel")

    if not channel:
        channel = "all"
    
    feeds, h_feed = feed_discovery(url)

    if h_feed and len(h_feed) > 0:
        feeds.append(url)
        flash("h-feed found at {}".format(url))

    if len(feeds) == 0:
        flash("No feed could be found attached to the web page you submitted.")
    
    return redirect("/reader/{}".format(channel))

@main.route("/channel/<id>", methods=["GET", "POST"])
def modify_channel(id):
    auth_result = check_token()

    if auth_result == False:
        return redirect("/login")

    connection = sqlite3.connect("microsub.db")

    if request.method == "POST":
        req = {
            "action": "channels",
            "channel": request.form.get("channel"),
            "name": request.form.get("name"),
        }

        print(req)

        r = requests.post(session.get("server_url"), data=req, headers={"Authorization": session.get("access_token")})

        if r.status_code == 200:
            flash("The channel was successfully renamed to {}".format(request.form.get("name")))
        else:
            flash("Something went wrong. Please try again.")

        return redirect("/reader/{}".format(id))

    with connection:
        cursor = connection.cursor()

        channel = cursor.execute("SELECT * FROM channels WHERE uid = ?", (id,)).fetchone()

        feeds = cursor.execute("SELECT * FROM following WHERE channel = ?", (id,)).fetchall()

        if channel:
            return render_template("server/modify_channel.html", title="Modify {} Channel | Microsub Dashboard".format(channel), channel=channel, feeds=feeds)
        else:
            flash("The channel you were looking for could not be found.")
            return redirect("/reader/all")

@main.route("/mute", methods=["POST"])
def mute_view():
    auth_result = check_token()

    if auth_result == False:
        return redirect("/login")

    action = request.form.get("action")

    if "mute" not in session["scope"]:
        flash("You have not granted permission to block feeds. Please log in again and grant permission to block feeds.")
        return redirect("/reader/{}".format(request.form.get("channel")))

    if action != "mute" and action != "unmute":
        flash("Invalid action.")
        return redirect("/reader/{}".format(request.form.get("channel")))

    if request.form.get("channel"):
        req = {
            "action": action,
            "channel": request.form.get("channel"),
            "url": request.form.get("url")
        }

        r = requests.post(session.get("server_url"), data=req, headers={"Authorization": session.get("access_token")})

        if r.status_code == 200:
            if action == "mute":
                flash("You have muted {}.".format(r.json()["url"]))
            elif action == "unmute":
                flash("You have unmuted {}.".format(r.json()["url"]))
        else:
            flash(r.json()["error"])

        return redirect("/channel/{}".format(request.form.get("channel")))
    else:
        return redirect("/channel/{}".format(request.form.get("channel")))

@main.route("/block", methods=["POST"])
def block_view():
    auth_result = check_token()

    if auth_result == False:
        return redirect("/login")

    action = request.form.get("action")

    if "block" not in session["scope"]:
        flash("You have not granted permission to block feeds. Please log in again and grant permission to block feeds.")
        return redirect("/reader/{}".format(request.form.get("channel")))

    if action != "block" and action != "unblock":
        flash("Invalid action.")
        return redirect("/reader/{}".format(request.form.get("channel")))

    if request.form.get("channel"):
        req = {
            "action": action,
            "channel": request.form.get("channel"),
            "url": request.form.get("url")
        }

        r = requests.post(session.get("server_url"), data=req, headers={"Authorization": session.get("access_token")})

        print(r.json())

        if r.status_code == 200:
            if action == "block":
                flash("You have blocked {}.".format(r.json()["url"]))
            elif action == "unblock":
                flash("You have unblocked {}.".format(r.json()["url"]))
        else:
            flash(r.json()["error"])

        return redirect("/channel/{}".format(request.form.get("channel")))
    else:
        return redirect("/channel/{}".format(request.form.get("channel")))

@main.route("/websub/<uid>", methods=["POST"])
def save_new_post_from_websub(uid):
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()
        
        # check if subscription exists
        subscription = cursor.execute("SELECT url FROM websub_subscriptions WHERE uid = ? AND approved = 1", (uid,)).fetchone()

        if not subscription:
            return jsonify({"error": "Subscription does not exist."}), 400

        url = subscription[0]
        channel = subscription[2]

        # retrieve feed
        try:
            r = requests.head(url, timeout=5)
        except:
            return jsonify({"error": "invalid url"}), 400

        if r.headers.get('content-type'):
            content_type = r.headers['content-type']
        else:
            content_type = ""

        items_to_return = []

        if "xml" in content_type or ".xml" in url:
            feed = feedparser.parse(url)

            for entry in feed.entries:
                result, published = xml_feed.process_xml_feed(entry, feed, url)

                items_to_return.append(result, published)
        elif "json" in content_type or url.endswith(".json"):
            try:
                feed = requests.get(url, timeout=5).json()
            except:
                return jsonify({"error": "invalid url"}), 400

            for entry in feed.get("items", []):
                result, published = json_feed.process_json_feed(entry, feed)

                items_to_return.append(result, published)
        else:
            results = hfeed.process_hfeed(url, add_to_db=True)

            # this should use actual published dates
            # for now, we are just using the current time
            published = datetime.datetime.now().strftime("%Y%m%d")

            for result in results:
                items_to_return.append(result)

        ten_random_letters = ''.join(random.choice(string.ascii_lowercase) for _ in range(10))

        for result in items_to_return:
            published = result[1]
            result = result[0]

            cursor.execute("INSERT INTO timeline VALUES (?, ?, ?, ?, ?, ?, ?)", (channel, json.dumps(result), published, "unread", result["url"], ten_random_letters, 0, ))
            
        return jsonify({"success": "Entry added to feed."}), 200

@main.route("/websub_callback")
def verify_websub_subscription():
    auth_result = check_token()

    if auth_result == False:
        return redirect("/login")

    if not request.args.get("hub.mode"):
        return jsonify({"error": "hub.mode not found"}), 400

    if not request.args.get("hub.topic"):
        return jsonify({"error": "No topic provided."}), 400

    if request.args.get("hub.challenge"):
        connection = sqlite3.connect("microsub.db")

        with connection:
            cursor = connection.cursor()
            check_subscription = cursor.execute("SELECT * FROM websub_subscriptions WHERE url = ? AND random_string = ?", (request.args.get("hub.topic"), request.args.get("hub.challenge"), )).fetchone()

            if not check_subscription:
                return jsonify({"error": "Subscription does not exist."}), 400

            cursor.execute("UPDATE websub_subscriptions SET approved = ? WHERE url = ?", (1, request.args.get("hub.topic"), ))

        return request.args.get("hub.challenge"), 200
    else:
        return jsonify({"error": "No challenge found."}), 400

if __name__ == "__main__":
    main.run()