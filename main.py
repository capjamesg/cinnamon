from flask import Flask, request, jsonify, send_from_directory, session, redirect, flash, render_template, current_app
from indieauth import requires_indieauth
from check_token import check_token
from dateutil import parser
import sqlite3
import requests
from actions import *
from config import *
import os

main = Flask(__name__, static_folder="static", static_url_path="")

# read config.py file
main.config.from_pyfile(os.path.join(".", "config.py"), silent=False)

# set secret key
main.secret_key = SECRET_KEY

# filter used to parse dates
# source: https://stackoverflow.com/questions/4830535/how-do-i-format-a-date-in-jinja2
@main.template_filter('strftime')
def _jinja2_filter_datetime(date, fmt=None):
    date = parser.parse(date)
    native = date.replace(tzinfo=None)
    format= '%b %d, %Y'
    return native.strftime(format) 

@main.route("/")
def index():
    return render_template("index.html", title="Home | Microsub Endpoint")

@main.route("/endpoint", methods=["GET", "POST"])
# @requires_indieauth
def home():
    if request.form:
        action = request.form.get("action")
        method = request.form.get("method")
    else:
        action = request.args.get("action")
        method = request.args.get("method")

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

        r = requests.post(URL, data=req, headers={'Authorization': 'Bearer ' + session["access_token"]})

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

        r = requests.post(URL, data=req, headers={'Authorization': 'Bearer ' + session["access_token"]})

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

        r = requests.post(URL, data=req, headers={"Authorization": session["access_token"]})

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

        r = requests.post(URL, data=req, headers={"Authorization": session.get("access_token")})

        if r.status_code == 200:
            return jsonify(r.json()), 200
        else:
            return jsonify(r.json()), 400
    else:
        return redirect("/feeds")
        
@main.route("/discover-feed", methods=["POST"])
def discover_feed():
    auth_result = check_token()

    if auth_result == False:
        return redirect("/login")

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

@main.route("/channel/<id>", methods=["GET", "POST"])
def modify_channel(id):
    auth_result = check_token()

    if auth_result == False:
        return redirect("/login")

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

        return render_template("server/modify_channel.html", title="Modify {} Channel".format(channel[0]), channel=channel, feeds=feeds)

@main.route("/preview")
def preview_feed():
    auth_result = check_token()

    if auth_result == False:
        return redirect("/login")

    session["access_token"] = ""

    headers = {
        "Authorization": session["access_token"]
    }

    url = request.args.get("url")
    channel_id = request.args.get("channel")

    if not url or not channel_id:
        flash("Please specify a feed URL and channel ID when previewing a feed.")
        return redirect("/")

    data = {
        "action": "preview",
        "url": url,
    }

    microsub_req = requests.post("https://microsub.jamesg.blog/endpoint", data=data, headers=headers)

    channel_req = requests.get("https://microsub.jamesg.blog/endpoint?action=channels", headers=headers)

    return render_template("client/preview.html",
        title="Preview Feed | Microsub Reader",
        feed=microsub_req.json(),
        channels=channel_req.json(),
        channel=channel_id
    )

@main.route("/websub/<uid>", methods=["POST"])
def save_new_post_from_websub(uid):
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()
        
        # check if subscription exists
        subscription = cursor.execute("SELECT url FROM websub_subscriptions WHERE uid = ?", (uid,)).fetchone()

        if not subscription:
            return jsonify({"error": "Subscription does not exist."}), 400

        url = subscription[0]

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
                result, _ = poll_feeds.process_xml_feed(entry, feed, url)
        else:
            results = poll_feeds.process_hfeed(url, add_to_db=True)

            for result in results:
                items_to_return.append(result)

        return jsonify({"success": "Entry added to feed."}), 200

if __name__ == "__main__":
    main.run()