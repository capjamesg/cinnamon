import sqlite3

import requests
from flask import Blueprint, request, jsonify, session, redirect, flash, render_template, abort
from check_token import verify as check_token
from actions import *

main = Blueprint('main', __name__, template_folder='templates')

def microsub_api_request(post_data, success_message):
    request = requests.post(
        session.get("server_url"),
        data=post_data,
        headers={
            'Authorization': 'Bearer ' + session["access_token"]
        }
    )

    if request.status_code == 200:
        flash(success_message)
    else:
        flash(request.json()["error"])

@main.route("/")
def index():
    is_authenticated = check_token(request.headers, session)

    if is_authenticated:
        return redirect("/reader/all")

    return render_template("index.html", title="Home | Cinnamon")

@main.route("/setup")
def setup():
    return render_template("setup.html", title="Setup | Cinnamon")

@main.route("/endpoint", methods=["GET", "POST"])
def home():
    if request.form:
        action = request.form.get("action")
        method = request.form.get("method")
        channel = request.form.get("channel")
        identifier = request.form.get("id")
    else:
        action = request.args.get("action")
        method = request.args.get("method")
        channel = request.args.get("channel")
        identifier = request.args.get("id")

    is_authenticated = check_token(request.headers, session)

    if not is_authenticated:
        return abort(403)

    if not action:
        return jsonify({"error": "No action specified."}), 400
    
    if action == "timeline" and request.method == "GET" and not identifier:
        return get_timeline()
    elif action == "timeline" and request.method == "GET" and identifier:
        return get_post()
    elif action == "timeline" and request.method == "POST" and method == "remove":
        return remove_entry()
    elif action == "timeline" and request.method == "POST":
        return mark_as_read()
    elif action == "preview" and request.method == "POST":
        return preview()
    elif action == "react" and request.method == "POST":
        return react()
    elif action == "search" and not channel:
        return search_for_feeds()
    elif action == "search" and channel:
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

        if request.form.get("channels") and method == "order":
            return reorder_channels()
        if method == "delete":
            return delete_channel()

        return create_channel()
    
    return jsonify({"error": "invalid_request", "error_description": "The action and method provided are not valid."}), 400

@main.route("/channels")
def dashboard():
    auth_result = check_token(request.headers, session)

    if not auth_result:
        return redirect("/login")

    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        all_channels = cursor.execute("SELECT * FROM channels ORDER BY position ASC;").fetchall()

        return render_template("server/dashboard.html", title="Cinnamon", channels=all_channels)

@main.route("/reorder", methods=["POST"])
def reorder_channels_view():
    auth_result = check_token(request.headers, session)

    if not auth_result:
        return redirect("/login")

    if request.form.get("channel"):
        req = {
            "action": "channels",
            "method": "order",
            "channels": request.form.getlist("channel")
        }

        microsub_api_request(
            req,
            "Your channels have been reordered."
        )

        return redirect("/channels")
    else:
        return redirect("/channels")

@main.route("/create-channel", methods=["POST"])
def create_channel_view():
    auth_result = check_token(request.headers, session)

    if not auth_result:
        return redirect("/login")

    if request.form.get("name"):
        req = {
            "action": "channels",
            "name": request.form.get("name")
        }

        microsub_api_request(
            req,
            f"You have created a new channel called {request.form.get('name')}."
        )
    
    return redirect("/channels")

@main.route("/delete-channel", methods=["POST"])
def delete_channel_view():
    auth_result = check_token(request.headers, session)

    if not auth_result:
        return redirect("/login")

    if request.form.get("channel"):
        req = {
            "action": "channels",
            "channel": request.form.get("channel"),
            "method": "delete"
        }

        microsub_api_request(
            req,
            f"The specified channel has been deleted."
        )

        return redirect("/channels")
    
    return redirect("/channels")

@main.route("/unfollow", methods=["POST"])
def unfollow_view():
    auth_result = check_token(request.headers, session)

    if not auth_result:
        return redirect("/login")

    if request.form.get("channel") and request.form.get("url"):
        req = {
            "action": "unfollow",
            "channel": request.form.get("channel"),
            "url": request.form.get("url")
        }

        microsub_api_request(
            req,
            f"Your unfollow was successful."
        )
    
    return redirect("/feeds")

def discover_web_page_feeds(url):
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    elif url.startswith("//"):
        url = "https:" + url

    try:
        web_page = requests.get(url, timeout=10, allow_redirects=True)

        web_page = web_page.text
    except:
        return None

    soup = BeautifulSoup(web_page, "lxml")

    # check for presence of mf2 hfeed
    h_feed = soup.find_all(class_="h-feed")

    feeds = []

    if soup.find("link", rel="alternate", type="application/atom+xml"):
        feeds.append(soup.find("link", rel="alternate", type="application/atom+xml").get("href"))
    if soup.find("link", rel="alternate", type="application/rss+xml"):
        feeds.append(soup.find("link", rel="alternate", type="application/rss+xml").get("href"))
    if soup.find("link", rel="feed", type="text/html"):
        # used for mircoformats rel=feed discovery
        feeds.append(soup.find("link", rel="feed", type="text/html").get("href"))
    if h_feed:
        feeds.append(url)

    for feed in range(len(feeds)):
        f = feeds[feed]

        if f.startswith("/"):
            feeds[feed] = url.strip("/") + f
        elif f.startswith("http://") or f.startswith("https://"):
            pass
        elif f.startswith("//"):
            feeds[feed] = "https:" + f

    return feeds
        
@main.route("/discover-feed")
def discover_feed():
    auth_result = check_token(request.headers, session)

    if not auth_result:
        return redirect("/login")

    url = request.args.get("subscribe-to")

    feeds = indieweb_utils.discover_web_page_feeds(url)

    if len(feeds) == 0:
        flash("No feed could be found attached to the web page you submitted.")
        return redirect("/feeds")
    
    return redirect("/preview?url={}".format(feeds[0]))

@main.route("/feeds", methods=["GET", "POST"])
def get_all_feeds():
    auth_result = check_token(request.headers, session)

    if not auth_result:
        return redirect("/login")

    connection = sqlite3.connect("microsub.db")

    channel = request.args.get("channel")

    if request.method == "POST":
        req = {
            "action": "channels",
            "channel": "all",
            "name": request.form.get("name"),
        }

        microsub_api_request(
            req,
            f"The channel was successfully renamed to {request.form.get('name')}"
        )

        return redirect(f"/reader/all")

    with connection:
        cursor = connection.cursor()

        if channel:
            feeds = cursor.execute("SELECT * FROM following WHERE channel = ?", (channel,)).fetchall()
        else:
            feeds = cursor.execute("SELECT * FROM following").fetchall()

    count = len(feeds)

    return render_template("server/modify_channel.html",
        title=f"People You Follow | Cinnamon",
        feeds=feeds,
        count=count
    )

@main.route("/mute", methods=["POST"])
def mute_view():
    auth_result = check_token(session.get("access_token"))

    if not auth_result:
        return redirect("/login")

    action = request.form.get("action")

    if "mute" not in session["scope"]:
        flash("You have not granted permission to block feeds. Please log in again and grant permission to block feeds.")
        return redirect(f"/reader/{request.form.get('channel')}")

    if action != "mute" and action != "unmute":
        flash("Invalid action.")
        return redirect(f"/reader/{request.form.get('channel')}")

    if request.form.get("channel"):
        req = {
            "action": action,
            "channel": request.form.get("channel"),
            "url": request.form.get("url")
        }

        r = requests.post(session.get("server_url"), data=req, headers={"Authorization": session.get("access_token")})

        if r.status_code == 200:
            if action == "mute":
                flash(f"You have muted {r.json()['url']}.")
            elif action == "unmute":
                flash(f"You have unmuted {r.json()['url']}.")
        else:
            flash(r.json()["error"])
    
    return redirect(f"/channel/{request.form.get('channel')}")

@main.route("/block", methods=["POST"])
def block_view():
    auth_result = check_token(session.get("access_token"))

    if not auth_result:
        return redirect("/login")

    action = request.form.get("action")

    if "block" not in session["scope"]:
        flash("You have not granted permission to block feeds. Please log in again and grant permission to block feeds.")
        return redirect(f"/reader/{request.form.get('channel')}")

    if action not in ("block", "unblock"):
        flash("Invalid action.")
        return redirect(f"/reader/{request.form.get('channel')}")

    if request.form.get("channel"):
        req = {
            "action": action,
            "channel": request.form.get("channel"),
            "url": request.form.get("url")
        }

        r = requests.post(session.get("server_url"), data=req, headers={"Authorization": session.get("access_token")})

        if r.status_code == 200:
            if action == "block":
                flash(f"You have blocked {r.json()['url']}.")
            elif action == "unblock":
                flash(f"You have unblocked {r.json()['url']}.")
        else:
            flash(r.json()["error"])
    
    return redirect(f"/channel/{request.form.get('channel')}")

@main.route("/websub/<uid>", methods=["POST"])
def save_new_post_from_websub(uid):
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()
        
        # check if subscription exists
        subscription = cursor.execute("SELECT url, channel FROM websub_subscriptions WHERE uid = ? AND approved = 1", (uid,)).fetchone()

        if not subscription:
            return jsonify({"error": "Subscription does not exist."}), 400

        url = subscription[0]
        channel = subscription[1]

        feed_id = cursor.execute("SELECT id FROM following WHERE url = ?", (url,)).fetchone()[0]

        # retrieve feed
        try:
            r = requests.get(url, timeout=5, allow_redirects=True)
        except:
            return jsonify({"error": "invalid url"}), 400

        if r.headers.get('content-type'):
            content_type = r.headers['content-type']
        else:
            content_type = ""

        items_to_return = []

        if "xml" in content_type or ".xml" in url:
            feed = feedparser.parse(url)

            for entry in feed.entries[:10]:
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
            mf2_raw = mf2py.parse(r.text)

            hcard = [item for item in mf2_raw['items'] if item['type'][0] == 'h-card']

            h_feed = [item for item in mf2_raw['items'] if item['type'] and item['type'][0] == 'h-feed']

            feed_title = None
            feed_icon = None

            if len(h_feed) > 0:
                feed = h_feed[0]["children"]
                feed_title = h_feed[0]["properties"].get("name")

                if feed_title:
                    feed_title = feed_title[0]

                feed_icon = h_feed[0]["properties"].get("icon")

                if feed_icon:
                    feed_icon = feed_icon[0]
            else:
                # get all non h-card items
                # this will let the program parse non h-entry feeds such as h-event feeds
                feed = [item for item in mf2_raw['items'] if item['type'] and item['type'][0] != 'h-card']

            # this should use actual published dates
            # for now, we are just using the current time

            for child in feed[:5]:
                result = hfeed.process_hfeed(child, hcard, channel, url, feed_id, feed_title)

                items_to_return.append(result)

        last_id = cursor.execute("SELECT MAX(id) FROM timeline;").fetchone()

        if last_id[0] != None:
            last_id = last_id[0] + 1
        else:
            last_id = 0

        for record in items_to_return:
            published = record.get("published")

            cursor.execute("""INSERT INTO timeline VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                (channel,
                    json.dumps(record),
                    record["published"],
                    0,
                    record["url"],
                    record["url"],
                    0,
                    feed_id,
                    last_id
                ))

            last_id += 1

    return jsonify({"success": "Entry added to feed."}), 200

@main.route("/websub_callback")
def verify_websub_subscription():
    auth_result = check_token(session.get("access_token"))

    if not auth_result:
        return redirect("/login")

    if not request.args.get("hub.mode"):
        return jsonify({"error": "hub.mode not found"}), 400

    if not request.args.get("hub.topic"):
        return jsonify({"error": "No topic provided."}), 400

    if request.args.get("hub.challenge"):
        connection = sqlite3.connect("microsub.db")

        with connection:
            cursor = connection.cursor()
            check_subscription = cursor.execute(
                "SELECT * FROM websub_subscriptions WHERE url = ? AND random_string = ?",
                    (
                        request.args.get("hub.topic"),
                        request.args.get("hub.challenge"),
                    )
            ).fetchone()

            if not check_subscription:
                return jsonify({"error": "Subscription does not exist."}), 400

            cursor.execute("UPDATE websub_subscriptions SET approved = ? WHERE url = ?", (1, request.args.get("hub.topic"), ))

        return request.args.get("hub.challenge"), 200
    
    return jsonify({"error": "No challenge found."}), 400

if __name__ == "__main__":
    main.run()