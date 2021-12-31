from flask import Blueprint, request, session, redirect, flash, render_template, send_from_directory
from check_token import verify as check_token
import requests
from actions import *
from config import *

client = Blueprint('client', __name__)

@client.route("/reader")
def reader_redirect():
    return redirect("/reader/all")

@client.route("/read/<id>")
def read_article(id):
    auth_result = check_token(request.headers, session)

    if auth_result == False:
        return redirect("/login")

    headers = {
        "Authorization": session["access_token"]
    }

    article_req = requests.get(session.get("server_url") + "?action=timeline&id=" + id, headers=headers)
    channel_req = requests.get(session.get("server_url") + "?action=channels", headers=headers)

    if article_req.status_code != 200:
        return redirect("/reader/all")

    channel = article_req.json()["post"][0]["channel"]

    feeds = requests.get(session.get("server_url") + f"?action=follow&channel={channel}", headers=headers).json()

    channel_name = [c for c in channel_req.json()["channels"] if c["uid"] == channel]

    if len(channel_name) > 0:
        channel_name = channel_name[0]["name"]
    else:
        channel_name = "All"

    jf2 = json.loads(article_req.json()["post"][0]["jf2"])

    return render_template("client/read_article.html",
        title=f"{channel_name} | Cinnamon",
        channels=channel_req.json()["channels"],
        w=jf2,
        page_channel_uid=channel,
        feeds=feeds,
        channel_name=channel_name,
        show_all_content=True
    )

@client.route("/reader/<channel>")
def microsub_reader(channel):
    auth_result = check_token(request.headers, session)

    if auth_result == False:
        return redirect("/login")

    headers = {
        "Authorization": session["access_token"]
    }

    before = None
    after = None

    if request.args.get("before"):
        before = request.args.get("before")

        microsub_req = requests.get(
            f"{session.get('server_url')}?action=timeline&channel={channel}&before={before}",
            headers=headers
        )
    elif request.args.get("after"):
        after = request.args.get("after")

        microsub_req = requests.get(
            f"{session.get('server_url')}?action=timeline&channel={channel}&after={after}",
            headers=headers
        )
    else:
        microsub_req = requests.get(
            f"{session.get('server_url')}?action=timeline&channel={channel}",
            headers=headers
        )

    feeds = requests.get(
        f"{session.get('server_url')}?action=follow&channel={channel}",
        headers=headers
    ).json()

    before_to_show = microsub_req.json()["paging"]["before"]
    after_to_show = microsub_req.json()["paging"]["after"]

    print(microsub_req.json()["paging"])

    channel_req = requests.get(session.get("server_url") + "?action=channels", headers=headers)

    channel_name = [c for c in channel_req.json()["channels"] if c["uid"] == channel]

    if len(channel_name) > 0:
        channel_name = channel_name[0]["name"]
    else:
        channel_name = "All"

    published_dates = [p.get("published") for p in microsub_req.json()["items"]]

    return render_template("client/reader.html",
        title=f"Your {channel_name} Feed | Cinnamon",
        results=microsub_req.json()["items"],
        channels=channel_req.json()["channels"],
        before=before_to_show,
        after=after_to_show,
        page_channel_uid=channel,
        published_dates=published_dates,
        feeds=feeds,
        channel_name=channel_name,
        show_all_content=False
    )

@client.route("/react", methods=["POST"])
def react_to_post():
    auth_result = check_token(request.headers, session)

    if auth_result == False:
        return redirect("/login")

    headers = {
        "Authorization": session["access_token"],
        "Content-Type": "application/json",
    }

    is_reply = request.args.get("is_reply")

    if is_reply == "true":
        request_to_make = {
            "h": "entry",
            "in-reply-to": [request.form.get("in-reply-to")],
            "properties": {
                "content": [
                    {
                        "html": request.form.get("content")
                    }
                ]
            }
        }
    else:
        request_to_make = {
            "h": "entry",
            request.form.get("reaction"): request.form.get("url")
        }

    requests.post(session.get("micropub_url"), json=request_to_make, headers=headers)

    return "OK"

@client.route("/read", methods=["POST"])
def mark_channel_as_read():
    auth_result = check_token(request.headers, session)

    if auth_result == False:
        return redirect("/login")

    headers = {
        "Authorization": session["access_token"]
    }

    channel = request.form.get("channel")
    status = request.form.get("status")
    last_read_entry = request.form.get("last_read_entry")

    requests.post(
        session.get("server_url"),
        data={
            "action": "timeline",
            "channel": channel,
            "method": status,
            "last_read_entry": last_read_entry
        },
        headers=headers
    )

    if last_read_entry == "mark_read":
        flash("Posts in this channel were successfully marked as read.")
    else:
        flash("Posts in this channel were successfully marked as unread.")

    return redirect(f"/reader/{channel}")

@client.route("/reader/<channel>/delete/<entry_id>")
def delete_entry_in_channel(channel, entry_id):
    auth_result = check_token(request.headers, session)

    if auth_result == False:
        return redirect("/login")

    headers = {
        "Authorization": session["access_token"]
    }

    data = {
        "action": "timeline",
        "method": "remove",
        "channel": channel,
        "entry": entry_id
    }

    r = requests.post(session.get("server_url"), data=data, headers=headers)

    flash("The entry was successfully deleted.")
    return redirect(f"/reader/{channel}")

@client.route("/preview")
def preview_feed():
    auth_result = check_token(request.headers, session)

    if auth_result == False:
        return redirect("/login")

    headers = {
        "Authorization": session["access_token"]
    }

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
        "items": []
    }

    try:
        microsub_req = requests.post(
            session.get("server_url"),
            data=data,
            headers=headers,
            timeout=5
        )

        feed_data = microsub_req.json()

        if microsub_req.status_code != 200:
            flash("The feed could not be previewed.")
            return redirect("/reader/all")

    except requests.exceptions.Timeout:
        flash("The feed preview request timed out.")

    channel_req = requests.get(session.get("server_url") + "?action=channels", headers=headers)

    if channel_id:
        channel_name = [c for c in channel_req.json()["channels"] if c["uid"] == channel_id][0]["name"]
    else:
        channel_name = "All"
        channel_id = "all"

    if not channel_name:
        flash("The channel to which you tried to add a feed does not exist.")
        return redirect("/reader/all")

    return render_template("client/preview.html",
        title="Preview Feed | Cinnamon",
        feed=feed_data,
        channel=channel_id,
        channel_name=channel_name,
        channels=channel_req.json()["channels"]
    )

@client.route("/search")
def search_feed():
    auth_result = check_token(request.headers, session)

    if auth_result == False:
        return redirect("/login")

    headers = {
        "Authorization": session["access_token"]
    }

    query = request.args.get("query")

    if not query:
        return render_template("client/search.html", title="Search | Cinnamon")

    data = {
        "action": "search",
        "query": query,
        "channel": "all"
    }

    microsub_req = requests.post(session.get("server_url"), data=data, headers=headers)

    return jsonify(microsub_req.json())

@client.route("/explore")
def explore_new_feeds():
    auth_result = check_token(request.headers, session)

    if auth_result == False:
        return redirect("/login")

    headers = {
        "Authorization": session["access_token"]
    }

    query = request.args.get("query")

    if not query:
        return render_template("client/discover.html", title="Explore | Cinnamon")

    data = {
        "action": "search",
        "query": query
    }

    print(data)

    microsub_req = requests.post(session.get("server_url"), data=data, headers=headers)

    return jsonify(microsub_req.json()["items"])

@client.route("/settings")
def settings():
    auth_result = check_token(request.headers, session)

    if auth_result == False:
        return redirect("/login")

    return render_template("client/settings.html",
        title="Settings | Cinnamon"
    )

@client.route("/reader.js")
def reader_js_file():
    return send_from_directory("static", "reader.js")