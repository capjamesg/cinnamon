from flask import Blueprint, request, session, redirect, flash, render_template
from check_token import check_token
from indieauth import requires_indieauth
import requests
from actions import *
from config import *

client = Blueprint('client', __name__)

@client.route("/reader")
def reader_redirect():
    return redirect("/reader/all")

@client.route("/reader/<channel>")
def microsub_reader(channel):
    auth_result = check_token()

    if auth_result == False:
        return redirect("/login")

    session["access_token"] = ""

    headers = {
        "Authorization": session["access_token"]
    }

    if request.args.get("before"):
        before = True
    else:
        before = False

    microsub_req = requests.get("https://microsub.jamesg.blogendpoint?action=timeline&channel={}".format(channel), headers=headers)

    channel_req = requests.get("https://microsub.jamesg.blogendpoint?action=channels", headers=headers)

    channel_name = [c for c in channel_req.json()["channels"] if c["uid"] == channel][0]["name"]
    published_dates = [p["published"] for p in microsub_req.json()["items"]]

    return render_template("client/reader.html",
        title="{} | Microsub Reader".format(channel_name),
        results=microsub_req.json()["items"],
        channels=channel_req.json()["channels"],
        before=before,
        page_channel_uid=channel,
        published_dates=published_dates
    )

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

    requests.post("https://microsub.jamesg.blog/endpoint", data={"action": "timeline", "channel": channel, "method": status, "last_read_entry": last_read_entry}, headers=headers)

    if last_read_entry == "mark_as_read":
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

    r = requests.post("https://microsub.jamesg.blog/endpoint", data=data, headers=headers)

    flash("The entry was successfully deleted.")
    return redirect("/reader/{}".format(channel))