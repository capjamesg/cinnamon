import json
import os
import random
import re
import string

import indieweb_utils
import requests
from bs4 import BeautifulSoup
from flask import Blueprint, flash, jsonify, redirect, render_template, request, session

from authentication.check_token import verify as check_token
from config import TWITTER_BEARER_TOKEN
from feeds import read_later

client = Blueprint("client", __name__)


@client.route("/reader")
def reader_redirect():
    return redirect("/reader/all")


@client.route("/read/<id>")
def read_article(id):
    auth_result = check_token(request.headers, session)

    if auth_result is False:
        return redirect("/login")

    headers = {"Authorization": session["access_token"]}

    article_req = requests.get(
        session.get("server_url") + "?action=timeline&id=" + id, headers=headers
    )
    channel_req = requests.get(
        session.get("server_url") + "?action=channels", headers=headers
    )

    if article_req.status_code != 200:
        return redirect("/reader/all")

    channel = article_req.json()["post"][0]["channel"]

    feeds = requests.get(
        session.get("server_url") + f"?action=follow&channel={channel}", headers=headers
    ).json()

    channel_name = [c for c in channel_req.json()["channels"] if c["uid"] == channel]

    if len(channel_name) > 0:
        channel_name = channel_name[0]["name"]
    else:
        channel_name = "All"

    jf2 = json.loads(article_req.json()["post"][0]["jf2"])

    return render_template(
        "client/read_article.html",
        title=f"{channel_name}",
        channels=channel_req.json()["channels"],
        w=jf2,
        page_channel_uid=channel,
        feeds=feeds,
        channel_name=channel_name,
        show_all_content=True,
    )


@client.route("/read-later")
def read_later_view():
    auth_result = check_token(request.headers, session)

    if auth_result is False:
        return redirect("/login")

    url = request.args.get("url")

    if not url:
        return 400

    status = read_later.read_later(url)

    if status is None:
        flash("The requested article could not be retrieved.")

    return redirect("/reader/read-later")


@client.route("/reader/<channel>")
def microsub_reader(channel):
    auth_result = check_token(request.headers, session)

    if auth_result is False:
        return redirect("/login")

    headers = {"Authorization": session["access_token"]}

    before = None
    after = None

    if request.args.get("before"):
        before = request.args.get("before")

        microsub_req = requests.get(
            f"{session.get('server_url')}?action=timeline&channel={channel}&before={before}",
            headers=headers,
        )
    elif request.args.get("after"):
        after = request.args.get("after")

        microsub_req = requests.get(
            f"{session.get('server_url')}?action=timeline&channel={channel}&after={after}",
            headers=headers,
        )
    else:
        microsub_req = requests.get(
            f"{session.get('server_url')}?action=timeline&channel={channel}",
            headers=headers,
        )

    feeds = requests.get(
        f"{session.get('server_url')}?action=follow&channel={channel}", headers=headers
    ).json()

    before_to_show = microsub_req.json()["paging"]["before"]
    after_to_show = microsub_req.json()["paging"]["after"]

    channel_req = requests.get(
        session.get("server_url") + "?action=channels", headers=headers
    )

    all_channels = channel_req.json()["channels"]

    channel_name = [c for c in all_channels if c["uid"] == channel]

    if len(channel_name) > 0:
        channel_name = channel_name[0]["name"]
    else:
        channel_name = "All"

    published_dates = [p.get("published") for p in microsub_req.json()["items"]]

    if len(microsub_req.json()["items"]) > 0:
        last_num = microsub_req.json()["items"][0]["_id"]
    else:
        last_num = ""

    if session.get("micropub_url"):
        contacts = requests.get(
            session.get("micropub_url") + "?q=contacts", headers=headers
        ).json()
        hashtags = requests.get(
            session.get("micropub_url") + "?q=category", headers=headers
        ).json()
        contacts = contacts["contacts"]
        hashtags = hashtags["categories"]
    else:
        # if hashtags / contacts are not supported, leave values blank
        contacts = []
        hashtags = []

    # make all keys lowercase
    contacts = {k.lower(): v for k, v in contacts.items()}

    requests.post(
        session.get("server_url"),
        data={
            "action": "timeline",
            "channel": channel,
            "method": "mark_read",
            "last_read_entry": last_num,
        },
        headers=headers,
    )

    return render_template(
        "client/reader.html",
        title=f"{channel_name} Posts",
        results=microsub_req.json()["items"],
        channels=channel_req.json()["channels"],
        before=before_to_show,
        after=after_to_show,
        page_channel_uid=channel,
        published_dates=published_dates,
        feeds=feeds,
        channel_name=channel_name,
        show_all_content=False,
        last_id=last_num,
        channel_id=channel,
        contacts=contacts,
        hashtags=hashtags,
    )


@client.route("/react", methods=["POST"])
def react_to_post():
    auth_result = check_token(request.headers, session)

    if auth_result is False:
        return redirect("/login")

    headers = {
        "Authorization": session["access_token"],
        "Content-Type": "application/json",
    }

    is_reply = request.args.get("is_reply")

    if is_reply == "true":
        content = request.form.get("content")
        parsed = BeautifulSoup(content, "lxml")

        if "p-rating" in content:
            request_to_make = {"h": "review", "properties": {"content": [content]}}
        else:
            request_to_make = {
                "h": "entry",
                "in-reply-to": [request.form.get("in-reply-to")],
                "properties": {"content": [content]},
            }

        name = parsed.find("span", {"class": "p-name"})

        if name:
            request_to_make["properties"]["name"] = name.text

        rating = parsed.find("span", {"class": "p-rating"})

        if rating:
            request_to_make["properties"]["rating"] = rating.text

    elif is_reply == "note":
        # get all hashtags from content

        content = request.form.get("content")

        content += '<a href="https://brid.gy/publish/twitter"></a>'

        hashtags = re.findall(r"#(\w+)", content)
        hashtags.append("Note")

        request_to_make = {
            "type": ["h-entry"],
            "properties": {"content": [content], "category": hashtags},
        }

    else:
        request_to_make = {
            "h": "entry",
            "properties": {
                request.form.get("reaction"): [
                    {request.form.get("reaction"): request.form.get("url")}
                ],
                "category": [request.form.get("reaction")],
            },
        }

    if request.form.get("private") and request.form.get("private") == "true":
        request_to_make["private"] = ["true"]

    r = requests.post(
        session.get("micropub_url"), json=request_to_make, headers=headers
    )

    if r.status_code != 201:
        return "error"

    headers = {"Authorization": session["access_token"]}

    if is_reply == "true":
        data_to_send = {
            "action": "react",
            "reaction": "reply",
            "uid": request.form.get("uid"),
            "content": request.form.get("content"),
            "url": r.headers.get("Location", "t"),
        }
    else:
        data_to_send = {
            "action": "react",
            "reaction": request.form.get("reaction"),
            "uid": request.form.get("uid"),
            "url": r.headers.get("Location", "t"),
        }

    requests.post(session.get("server_url"), data=data_to_send, headers=headers)

    return r.headers.get("Location", "")


@client.route("/read", methods=["POST"])
def mark_channel_as_read():
    auth_result = check_token(request.headers, session)

    if auth_result is False:
        return redirect("/login")

    headers = {"Authorization": session["access_token"]}

    channel = request.form.get("channel")
    status = request.form.get("status")
    last_read_entry = request.form.get("last_read_entry")

    requests.post(
        session.get("server_url"),
        data={
            "action": "timeline",
            "channel": channel,
            "method": status,
            "last_read_entry": last_read_entry,
        },
        headers=headers,
    )

    if last_read_entry == "mark_read":
        flash("Posts in this channel were successfully marked as read.")
    else:
        flash("Posts in this channel were successfully marked as unread.")

    return redirect(f"/reader/{channel}")


@client.route("/reader/<channel>/delete")
def delete_entry_in_channel(channel):
    entry_id = request.args.get("entry_id")

    auth_result = check_token(request.headers, session)

    if auth_result is False:
        return redirect("/login")

    headers = {"Authorization": session["access_token"]}

    data = {
        "action": "timeline",
        "method": "remove",
        "channel": channel,
        "entry": entry_id,
    }

    r = requests.post(session.get("server_url"), data=data, headers=headers)

    if r.status_code == 200:
        flash("The entry was successfully deleted.")
    else:
        flash("There was an error deleting the entry.")

    return redirect(f"/reader/{channel}")


@client.route("/preview")
def preview_feed():
    auth_result = check_token(request.headers, session)

    if auth_result is False:
        return redirect("/login")

    headers = {"Authorization": session["access_token"]}

    url = request.args.get("url")
    channel_id = request.args.get("channel")

    if not url:
        flash("Please specify a feed URL to preview a feed.")
        return redirect("/reader/all")

    data = {
        "action": "preview",
        "url": url,
    }

    feed_data = {
        "feed": {
            "title": url,
            "url": url,
        },
        "items": [],
    }

    try:
        microsub_req = requests.post(
            session.get("server_url"), headers=headers, data=data, timeout=15
        )

        feed_data = microsub_req.json()

        if microsub_req.status_code != 200:
            flash("The feed could not be previewed.")
            return redirect("/reader/all")

    except requests.exceptions.Timeout:
        flash("The feed preview request timed out.")
    except Exception as e:
        print(e)
        flash("There was an error previewing the feed.")
        return redirect("/reader/all")

    print(session.get("server_url"))

    channel_req = requests.get(
        session.get("server_url") + "?action=channels", headers=headers
    )

    if channel_id:
        channel_name = [
            c for c in channel_req.json()["channels"] if c["uid"] == channel_id
        ][0]["name"]
    else:
        channel_name = "All"
        channel_id = "all"

    if not channel_name:
        flash("The channel to which you tried to add a feed does not exist.")
        return redirect("/reader/all")

    return render_template(
        "client/preview.html",
        title="Preview Feed",
        feed=feed_data,
        channel=channel_id,
        channel_name=channel_name,
        channels=channel_req.json()["channels"],
    )


@client.route("/media", methods=["POST"])
def make_micropub_media_request():
    auth_result = check_token(request.headers, session)

    if auth_result is False:
        return redirect("/login")

    headers = {"Authorization": "Bearer " + session["access_token"]}

    file = request.files["file"]

    photo_r = requests.post(
        session.get("media_endpoint"),
        files={"file": (file.filename, file.read(), "image/jpeg")},
        headers=headers,
    )

    if photo_r.status_code != 201 and photo_r.status_code != 200:
        return "error"

    file = request.files["file"]

    if file is None:
        return jsonify({"message": "Please send a file."}), 400

    # get file extension
    if "." in file.filename:
        ext = file.filename.split(".")[-1]
    else:
        return jsonify({"message": "Please send a file with an extension."}), 400

    ALLOWED_EXTENSIONS = ["jpg", "jpeg", "png", "gif"]
    UPLOAD_FOLDER = "static/"

    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"message": "Please send a valid image file."}), 400

    filename = "".join(random.sample(string.ascii_letters, 5)) + "." + ext

    # save image as file then open with PIL for resizing

    file.save(os.path.join(UPLOAD_FOLDER, filename))

    # if ext in (".jpg", ".jpeg"):
    #     image_file_local = Image.open(os.path.join(UPLOAD_FOLDER, filename))
    #     image_file_local = ImageOps.exif_transpose(image_file_local)
    #     image_file_local.thumbnail((1200, 750))
    #     image_file_local.save(os.path.join(UPLOAD_FOLDER, filename))

    return jsonify({"result": f"/static/{filename}"}), 200


@client.route("/retrieve")
def retrieve_new_entries():
    auth_result = check_token(request.headers, session)

    if auth_result is False:
        return redirect("/login")

    headers = {"Authorization": session["access_token"]}

    last_id = request.args.get("last_id")

    if not last_id:
        return jsonify({"message": "last_id is required"}), 400

    channel = request.args.get("channel")

    if not channel:
        channel = "all"

    microsub_req = requests.get(
        f"{session.get('server_url')}?action=timeline&channel={channel}",
        headers=headers,
    )

    json_data = microsub_req.json()

    if len(json_data["items"]) > 0:
        last_num = json_data["items"][0]["_id"]
    else:
        last_num = ""

    return jsonify({"last_id": last_num})


@client.route("/context", methods=["POST"])
def make__context_request():
    url = request.json.get("url")

    if not url:
        return jsonify({"message": "url is required"}), 400

    _, h_entry, _ = indieweb_utils.get_reply_context(
        url, twitter_bearer_token=TWITTER_BEARER_TOKEN
    )

    return jsonify(h_entry), 200


@client.route("/search")
def search_feed():
    auth_result = check_token(request.headers, session)

    if auth_result is False:
        return redirect("/login")

    headers = {"Authorization": session["access_token"]}

    query = request.args.get("query")
    channel = request.args.get("channel")
    format = request.args.get("format")

    if not query:
        channel_req = requests.get(
            session.get("server_url") + "?action=channels", headers=headers
        )

        return render_template(
            "client/search.html",
            title="Search",
            channels=channel_req.json()["channels"],
        )

    if not channel:
        channel = "all"

    data = {"action": "search", "query": query, "channel": channel}

    microsub_req = requests.post(session.get("server_url"), data=data, headers=headers)

    if format == "json":
        return jsonify(microsub_req.json())
    else:
        channel_req = requests.get(
            session.get("server_url") + "?action=channels", headers=headers
        )

        return render_template(
            "client/search.html",
            title="Search Your Feed",
            channels=channel_req.json()["channels"],
            results=microsub_req.json()["items"],
        )


@client.route("/explore")
def explore_new_feeds():
    auth_result = check_token(request.headers, session)

    if auth_result is False:
        return redirect("/login")

    headers = {"Authorization": session["access_token"]}

    query = request.args.get("query")

    if not query:
        channel_req = requests.get(
            session.get("server_url") + "?action=channels", headers=headers
        )

        return render_template(
            "client/discover.html",
            title="Discover People",
            channels=channel_req.json()["channels"],
        )

    data = {"action": "search", "query": query}

    microsub_req = requests.post(session.get("server_url"), data=data, headers=headers)

    return jsonify(microsub_req.json()["items"])


@client.route("/settings")
def settings():
    auth_result = check_token(request.headers, session)

    if auth_result is False:
        return redirect("/login")

    headers = {"Authorization": session["access_token"]}

    channel_req = requests.get(
        session.get("server_url") + "?action=channels", headers=headers
    )

    return render_template(
        "client/settings.html",
        title="Settings",
        channels=channel_req.json()["channels"],
    )


@client.route("/discover-feed")
def discover_feed():
    auth_result = check_token(request.headers, session)

    if not auth_result:
        return redirect("/login")

    url = request.args.get("subscribe-to")

    feeds = indieweb_utils.discover_web_page_feeds(url)

    if len(feeds) == 0:
        flash("No feed could be found attached to the web page you submitted.")
        return redirect("/following")

    return redirect(f"/preview?url={feeds[0].url}")


@client.route("/mute", methods=["POST"])
def mute_view():
    auth_result = check_token(session.get("access_token"))

    if not auth_result:
        return redirect("/login")

    action = request.form.get("action")

    if "mute" not in session["scopes"]:
        flash(
            "You have not granted permission to block feeds. Please log in again and grant permission to block feeds."
        )
        return redirect(f"/reader/{request.form.get('channel')}")

    if action != "mute" and action != "unmute":
        flash("Invalid action.")
        return redirect(f"/reader/{request.form.get('channel')}")

    if request.form.get("channel"):
        req = {
            "action": action,
            "channel": request.form.get("channel"),
            "url": request.form.get("url"),
        }

        r = requests.post(
            session.get("server_url"),
            data=req,
            headers={"Authorization": session.get("access_token")},
        )

        if r.status_code == 200:
            if action == "mute":
                flash(f"You have muted {r.json()['url']}.")
            elif action == "unmute":
                flash(f"You have unmuted {r.json()['url']}.")
        else:
            flash(r.json()["error"])

    return redirect(f"/channel/{request.form.get('channel')}")


@client.route("/block", methods=["POST"])
def block_view():
    auth_result = check_token(session.get("access_token"))

    if not auth_result:
        return redirect("/login")

    action = request.form.get("action")

    if "block" not in session["scopes"]:
        flash(
            "You have not granted permission to block feeds. Please log in again and grant permission to block feeds."
        )
        return redirect(f"/reader/{request.form.get('channel')}")

    if action not in ("block", "unblock"):
        flash("Invalid action.")
        return redirect(f"/reader/{request.form.get('channel')}")

    if request.form.get("channel"):
        req = {
            "action": action,
            "channel": request.form.get("channel"),
            "url": request.form.get("url"),
        }

        r = requests.post(
            session.get("server_url"),
            data=req,
            headers={"Authorization": session.get("access_token")},
        )

        if r.status_code == 200:
            if action == "block":
                flash(f"You have blocked {r.json()['url']}.")
            elif action == "unblock":
                flash(f"You have unblocked {r.json()['url']}.")
        else:
            flash(r.json()["error"])

    return redirect(f"/channel/{request.form.get('channel')}")
