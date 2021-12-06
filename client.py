from flask import Blueprint, request, session, redirect, flash, render_template, send_from_directory
from .check_token import check_token
import requests
from .actions import *
from .config import *

client = Blueprint('client', __name__)

@client.route("/reader")
def reader_redirect():
    session["me"] = "jamesg.blog"
    session["access_token"] = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJtZSI6Imh0dHBzOi8vamFtZXNnLmJsb2ciLCJleHBpcmVzIjoxNjM5MDY3ODExLCJjbGllbnRfaWQiOiJodHRwczovL21pY3JvcHViLmphbWVzZy5ibG9nLyIsInJlZGlyZWN0X3VyaSI6Imh0dHBzOi8vbWljcm9wdWIuamFtZXNnLmJsb2cvY2FsbGJhY2siLCJzY29wZSI6ImNyZWF0ZSB1cGRhdGUgZGVsZXRlIG1lZGlhIHVuZGVsZXRlIHByb2ZpbGUgIiwicmVzb3VyY2UiOiJhbGwifQ.ueTLBxrlrTFvtl2ryUhL8s0gt4Owt-nFhVMOy_I0GIA"
    session["server_url"] = "https://microsub.jamesg.blog/endpoint"
    session["scope"] = "create update delete media"
    session["micropub_url"] = "https://micropub.jamesg.blog/endpoint"
    return redirect("/reader/all")

@client.route("/read/<id>")
def read_article(id):
    auth_result = check_token(session.get("access_token"))

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

    feeds = requests.get(session.get("server_url") + "?action=follow&channel={}".format(channel), headers=headers).json()

    channel_name = [c for c in channel_req.json()["channels"] if c["uid"] == channel]

    if len(channel_name) > 0:
        channel_name = channel_name[0]["name"]
    else:
        channel_name = "All"

    jf2 = json.loads(article_req.json()["post"][0]["jf2"])

    return render_template("client/read_article.html",
        title="{} | Microsub Reader".format(channel_name),
        channels=channel_req.json()["channels"],
        w=jf2,
        page_channel_uid=channel,
        feeds=feeds,
        channel_name=channel_name,
        show_all_content=True
    )

@client.route("/reader/<channel>")
def microsub_reader(channel):
    auth_result = check_token(session.get("access_token"))

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

    published_dates = [p.get("published") for p in microsub_req.json()["items"]]

    return render_template("client/reader.html",
        title="{} | Microsub Reader".format(channel_name),
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
    auth_result = check_token(session.get("access_token"))

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
    auth_result = check_token(session.get("access_token"))

    if auth_result == False:
        return redirect("/login")

    headers = {
        "Authorization": session["access_token"]
    }

    channel = request.form.get("channel")
    status = request.form.get("status")
    last_read_entry = request.form.get("last_read_entry")

    requests.post(session.get("server_url"), data={"action": "timeline", "channel": channel, "method": status, "last_read_entry": last_read_entry}, headers=headers)

    if last_read_entry == "mark_read":
        flash("Posts in this channel were successfully marked as read.")
    else:
        flash("Posts in this channel were successfully marked as unread.")

    return redirect("/reader/{}".format(channel))

@client.route("/reader/<channel>/delete/<entry_id>")
def delete_entry_in_channel(channel, entry_id):
    auth_result = check_token(session.get("access_token"))

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
    auth_result = check_token(session.get("access_token"))

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

    microsub_req = requests.post(session.get("server_url"), data=data, headers=headers)

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
        title="Preview Feed | Microsub Reader",
        feed=microsub_req.json(),
        channel=channel_id,
        channel_name=channel_name,
        channels=channel_req.json()["channels"]
    )

@client.route("/search")
def search_feed():
    auth_result = check_token(session.get("access_token"))

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
    auth_result = check_token(session.get("access_token"))

    if auth_result == False:
        return redirect("/login")

    return render_template("client/settings.html",
        title="Settings | Microsub Reader"
    )

@client.route("/reader.js")
def reader_js_file():
    return send_from_directory("static", "reader.js")