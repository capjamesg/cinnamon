from flask import Blueprint, request, session, redirect, flash, render_template, send_from_directory
from .auth.check_token import check_token
import requests
from .auth.discovery import *
from .server.actions import *
from .config import *

client = Blueprint('client', __name__)

@client.route("/reader")
def reader_redirect():
    return redirect("/reader/all")

@client.route("/reader/<channel>")
def microsub_reader(channel):
    auth_result = check_token()

    if auth_result == False:
        return redirect("/login")

    headers = {
        "Authorization": session["access_token"]
    }

    before = None
    after = None

    if request.args.get("before"):
        before = request.args.get("before")

        microsub_req = requests.get(session.get("server_url") + "?action=timeline&channel={}&before={}".format(channel, before), headers=headers)
    elif request.args.get("after"):
        after = request.args.get("after")

        microsub_req = requests.get(session.get("server_url") + "?action=timeline&channel={}&after={}".format(channel, after), headers=headers)
    else:
        microsub_req = requests.get(session.get("server_url") + "?action=timeline&channel={}".format(channel), headers=headers)

    feeds = requests.get(session.get("server_url") + "?action=follow&channel={}".format(channel), headers=headers).json()

    before_to_show = microsub_req.json()["paging"]["before"]
    after_to_show = microsub_req.json()["paging"]["after"]

    channel_req = requests.get(session.get("server_url") + "?action=channels", headers=headers)

    channel_name = [c for c in channel_req.json()["channels"] if c["uid"] == channel]

    if len(channel_name) > 0:
        channel_name = channel_name[0]["name"]
    else:
        channel_name = "All"

    microsub_req_json = microsub_req.json()

    # mark all entries as read on load
    if len(microsub_req_json["items"]) > 0:
        requests.post(session.get("server_url"), data={"action": "timeline", "channel": channel, "method": "mark_read", "last_read_entry": microsub_req_json["items"][0]["_id"]}, headers=headers)

    published_dates = [p.get("published") for p in microsub_req_json["items"]]

    return render_template("client/reader.html",
        title="{} | Microsub Reader".format(channel_name),
        results=microsub_req_json["items"],
        channels=channel_req.json()["channels"],
        before=before_to_show,
        after=after_to_show,
        page_channel_uid=channel,
        published_dates=published_dates,
        feeds=feeds,
        channel_name=channel_name
    )

@client.route("/react", methods=["POST"])
def react_to_post():
    auth_result = check_token()

    if auth_result == False:
        return redirect("/login")

    headers = {
        "Authorization": session["access_token"],
        "Content-Type": "application/json",
    }

    request_to_make = {
        "type": ["h-entry"],
        request.form.get("reaction"): request.form.get("url")
    }

    if request.form.get("reaction") == "note":
        request_to_make["properties"] = {
            "content": [request.form.get("content")],
            "category": ["Note"],
            "is_hidden": ["no"]
        }

    r = requests.post(session.get("micropub_url"), json=request_to_make, headers=headers)

    if r.status_code != 200 and r.status_code != 201 and r.status_code != 202:
        return jsonify({"error": "There was an error."}), 400

    if request.form.get("reaction") == "note":
        flash("Your note has been posted to {}.".format(r.headers["Location"]))
        return redirect("/reader/{}".format(request.form.get("channel")))
    
    return jsonify({"location": r.headers["Location"]})

@client.route("/read", methods=["POST"])
def mark_channel_as_read():
    auth_result = check_token()

    if auth_result == False:
        return redirect("/login")

    headers = {
        "Authorization": session["access_token"]
    }

    channel = request.form.get("channel")
    status = request.form.get("status")
    last_read_entry = request.form.get("last_read_entry")

    requests.post(session.get("server_url"), data={"action": "timeline", "channel": channel, "method": status, "last_read_entry": last_read_entry}, headers=headers)

    if status == "mark_read":
        flash("Posts in this channel were successfully marked as read.")
    else:
        flash("Posts in this channel were successfully marked as unread.")

    return redirect("/reader/{}".format(channel))

@client.route("/reader/<channel>/delete/<entry_id>")
def delete_entry_in_channel(channel, entry_id):
    auth_result = check_token()

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
    return redirect("/reader/{}".format(channel))

@client.route("/preview")
def preview_feed():
    auth_result = check_token()

    if auth_result == False:
        return redirect("/login")

    headers = {
        "Authorization": session["access_token"]
    }

    url = request.args.get("url")
    channel_id = request.args.get("channel")

    channel_req = requests.get(session.get("server_url") + "?action=channels", headers=headers)

    if channel_id:
        channel_name = [c for c in channel_req.json()["channels"] if c["uid"] == channel_id][0]["name"]
    else:
        channel_name = "All"
        channel_id = "all"

    if not channel_name:
        flash("The channel to which you tried to add a feed does not exist.")
        return redirect("/reader/all")

    if request.args.get("url"):
        feeds, _ = feed_discovery(request.args.get("url"))

        if not request.args.get("url"):
            flash("Please specify a feed URL to preview a feed.")
            return redirect("/reader/all")

        if not channel_id:
            flash("The channel to which you tried to add a feed does not exist.")
            return redirect("/reader/all")

        return render_template("client/preview.html",
            title="Discover Feed | Microsub Reader",
            feeds=feeds,
            channel=channel_id,
            channel_name=channel_name,
            channels=channel_req.json()["channels"],
            discover=True,
            feed_title="a feed"
        )

    url = request.args.get("preview_url")

    if not url:
        flash("Please specify a feed URL to preview a feed.")
        return redirect("/reader/all")

    data = {
        "action": "preview",
        "url": url,
    }

    microsub_req = requests.post(session.get("server_url"), data=data, headers=headers)

    return render_template("client/preview.html",
        title="Preview Feed | Microsub Reader",
        feed=microsub_req.json(),
        channel=channel_id,
        channel_name=channel_name,
        channels=channel_req.json()["channels"],
        feed_title=microsub_req.json()["feed"]["title"]
    )

@client.route("/search")
def search_feed():
    auth_result = check_token()

    if auth_result == False:
        return redirect("/login")

    headers = {
        "Authorization": session["access_token"]
    }

    query = request.args.get("query")
    channel_id = request.args.get("channel")

    if not query or not channel_id:
        flash("Please specify a query and channel ID when searching for a feed.")
        return redirect("/reader/all")

    data = {
        "action": "search",
        "query": query,
    }

    microsub_req = requests.post(session.get("server_url"), data=data, headers=headers)

    feeds = requests.get(session.get("server_url") + "?action=follow&channel={}".format(channel_id), headers=headers).json()

    channel_req = requests.get(session.get("server_url") + "?action=channels", headers=headers)

    published_dates = [p.get("published") for p in microsub_req.json()["items"]]

    return render_template("client/reader.html",
        title="Showing results for {} | Microsub Reader".format(query),
        results=microsub_req.json()["items"],
        channel=channel_id,
        is_searching=True,
        query=query,
        feeds=feeds,
        channels=channel_req.json()["channels"],
        published_dates=published_dates
    )

@client.route("/settings")
def settings():
    auth_result = check_token()

    if auth_result == False:
        return redirect("/login")

    return render_template("client/settings.html",
        title="Settings | Microsub Reader"
    )

@client.route("/reader.js")
def reader_js_file():
    return send_from_directory("static", "reader.js")

@client.route("/emojis.json")
def emoji_dictionary():
    return send_from_directory("static", "emojis.json")