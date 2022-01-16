from flask import Blueprint, request, session, redirect, flash, render_template, send_from_directory
from check_token import verify as check_token
from feeds import read_later
import requests
from actions import *
from config import *
import re

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

@client.route("/read-later")
def read_later_view():
    auth_result = check_token(request.headers, session)

    if auth_result == False:
        return redirect("/login")

    url = request.args.get("url")

    if not url:
        return 400

    status = read_later.read_later(url)

    if status == None:
        flash("The requested article could not be retrieved.")

    return redirect("/reader/read-later")

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

    channel_req = requests.get(session.get("server_url") + "?action=channels", headers=headers)

    channel_name = [c for c in channel_req.json()["channels"] if c["uid"] == channel]

    if len(channel_name) > 0:
        channel_name = channel_name[0]["name"]
    else:
        channel_name = "All"

    published_dates = [p.get("published") for p in microsub_req.json()["items"]]

    if len(microsub_req.json()["items"]) > 0:
        last_num = microsub_req.json()["items"][0]["_id"]
    else:
        last_num = ""

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
        show_all_content=False,
        last_id=last_num
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
        content = request.form.get("content")
        parsed = BeautifulSoup(content, "lxml")

        if "p-rating" in content:
            request_to_make = {
                "h": "review",
                "properties": {
                    "content": [content]
                }
            }
        else:
            request_to_make = {
                "h": "entry",
                "in-reply-to": [request.form.get("in-reply-to")],
                "properties": {
                    "content": [content]
                }
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

        content += '<a href="https://brid.gy/publish/twitter?bridgy_omit_link=true"></a>'

        hashtags = re.findall(r"#(\w+)", content)
        hashtags.append("Note")
        
        request_to_make = {
            "type": ["h-entry"],
            "properties": {
                "content": [content],
                "category": hashtags
            }
        }
    else:
        request_to_make = {
            "h": "entry",
            request.form.get("reaction"): request.form.get("url")
        }

    r = requests.post(session.get("micropub_url"), json=request_to_make, headers=headers)

    if r.status_code != 201:
        return "error"

    headers = {
        "Authorization": session["access_token"]
    }

    if is_reply == "true":
        data_to_send = {
            "action": "react",
            "reaction": "reply",
            "uid": request.form.get("uid"),
            "content": request.form.get("content"),
            "url": r.headers.get("Location", "t")
        }
    else:
        data_to_send = {
            "action": "react",
            "reaction": request.form.get("reaction"),
            "uid": request.form.get("uid"),
            "url": r.headers.get("Location", "t")
        }

    requests.post(
        session.get("server_url"),
        data=data_to_send,
        headers=headers
    )

    return r.headers.get("Location", "")

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

@client.route("/reader/<channel>/delete")
def delete_entry_in_channel(channel):
    entry_id = request.args.get("entry_id")

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

    if r.status_code == 200:
        flash("The entry was successfully deleted.")
    else:
        flash("There was an error deleting the entry.")

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

@client.route("/media", methods=["POST"])
def make_micropub_media_request():
    auth_result = check_token(request.headers, session)

    if auth_result == False:
        return redirect("/login")

    headers = {
        "Authorization": "Bearer " + session["access_token"]
    }

    file = request.files["file"]

    photo_r = requests.post(MEDIA_ENDPOINT,
        files={"file": (file.filename, file.read(), "image/jpeg")},
        headers=headers)

    if photo_r.status_code != 201:
        return "error"

    return jsonify({"result": photo_r.headers.get("Location", "")}), 200

@client.route("/retrieve")
def retrieve_new_entries():
    auth_result = check_token(request.headers, session)

    if auth_result == False:
        return redirect("/login")

    headers = {
        "Authorization": session["access_token"]
    }

    last_id = request.args.get("last_id")

    if not last_id:
        return jsonify({"message": "last_id is required"}), 400

    channel = request.args.get("channel")

    if not channel:
        channel = "all"

    microsub_req = requests.get(
        f"{session.get('server_url')}?action=timeline&channel={channel}",
        headers=headers
    )

    json_data = microsub_req.json()

    if len(json_data["items"]) > 0:
        last_num = json_data["items"][0]["_id"]
    else:
        last_num = ""

    return jsonify({"last_id": last_num})

@client.route("/search")
def search_feed():
    auth_result = check_token(request.headers, session)

    if auth_result == False:
        return redirect("/login")

    headers = {
        "Authorization": session["access_token"]
    }

    query = request.args.get("query")
    channel = request.args.get("channel")
    format = request.args.get("format")

    if not query:
        channel_req = requests.get(session.get("server_url") + "?action=channels", headers=headers)

        return render_template("client/search.html", title="Search | Cinnamon", channels=channel_req.json()["channels"])

    if not channel:
        channel = "all"

    data = {
        "action": "search",
        "query": query,
        "channel": channel
    }

    microsub_req = requests.post(session.get("server_url"), data=data, headers=headers)

    if format == "json":
        return jsonify(microsub_req.json())
    else:
        channel_req = requests.get(session.get("server_url") + "?action=channels", headers=headers)

        return render_template("client/search.html", title="Search | Cinnamon", channels=channel_req.json()["channels"], results=microsub_req.json()["items"])


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