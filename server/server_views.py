import sqlite3

import requests
from flask import Blueprint, jsonify, redirect, render_template, request, session

from authentication.check_token import verify as check_token
from .main import microsub_api_request

server_views = Blueprint("server_views", __name__, template_folder="templates")


@server_views.route("/lists")
def dashboard():
    auth_result = check_token(request.headers, session)

    if not auth_result:
        return redirect("/login")

    headers = {"Authorization": session["access_token"]}

    channel_req = requests.get(
        session.get("server_url") + "?action=channels", headers=headers
    )

    all_channels = channel_req.json()["channels"]

    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        feeds = cursor.execute(
            "SELECT * FROM channels ORDER by position ASC;"
        ).fetchall()

    return render_template(
        "server/dashboard.html", title="Your Lists", channels=all_channels, feeds=feeds
    )


@server_views.route("/reorder", methods=["POST"])
def reorder_channels_view():
    auth_result = check_token(request.headers, session)

    if not auth_result:
        return redirect("/login")

    if request.form.get("channel"):
        req = {
            "action": "channels",
            "method": "order",
            "channels": request.form.getlist("channel"),
        }

        microsub_api_request(req, "Your channels have been reordered.")

        return redirect("/lists")
    else:
        return redirect("/lists")


@server_views.route("/create-channel", methods=["POST"])
def create_channel_view():
    auth_result = check_token(request.headers, session)

    if not auth_result:
        return redirect("/login")

    if request.form.get("name"):
        req = {"action": "channels", "name": request.form.get("name")}

        microsub_api_request(
            req, f"You have created a new channel called {request.form.get('name')}."
        )

    return redirect("/lists")


@server_views.route("/delete-channel", methods=["POST"])
def delete_channel_view():
    auth_result = check_token(request.headers, session)

    if not auth_result:
        return redirect("/login")

    if request.form.get("channel"):
        req = {
            "action": "channels",
            "channel": request.form.get("channel"),
            "method": "delete",
        }

        microsub_api_request(req, "The specified channel has been deleted.")

        return redirect("/lists")

    return redirect("/lists")


@server_views.route("/unfollow", methods=["POST"])
def unfollow_view():
    auth_result = check_token(request.headers, session)

    if not auth_result:
        return redirect("/login")

    if request.form.get("channel") and request.form.get("url"):
        req = {
            "action": "unfollow",
            "channel": request.form.get("channel"),
            "url": request.form.get("url"),
        }

        microsub_api_request(req, "Your unfollow was successful.")

    return redirect("/following")


@server_views.route("/following/search", methods=["POST"])
def search_for_feed():
    auth_result = check_token(request.headers, session)

    if not auth_result:
        return redirect("/login")

    connection = sqlite3.connect("microsub.db")
    connection.row_factory = sqlite3.Row

    query = request.args.get("query")

    with connection:
        cursor = connection.cursor()

        feeds = cursor.execute(
            "SELECT * FROM following WHERE name LIKE ? ORDER BY id DESC",
            (f"%{query}%",),
        ).fetchall()

    unpacked = [{k: item[k] for k in item.keys()} for item in feeds]

    return jsonify({"items": unpacked}), 200


@server_views.route("/following", methods=["GET", "POST"])
def get_all_feeds():
    auth_result = check_token(request.headers, session)

    if not auth_result:
        return redirect("/login")

    connection = sqlite3.connect("microsub.db")

    channel = request.args.get("channel")

    if request.method == "POST":
        req = {
            "action": "follow",
            "channel": "all",
            "url": request.form.get("url"),
        }

        microsub_api_request(
            req, f"The channel was successfully renamed to {request.form.get('name')}"
        )

        return redirect("/reader/all")

    connection.row_factory = sqlite3.Row

    with connection:
        cursor = connection.cursor()

        if channel:
            feeds = cursor.execute(
                """
                SELECT f.channel, f.url, f.etag, f.photo, f.name, f.id, f.muted, f.blocked, c.channel AS channel_name
                FROM following AS f, channels AS c
                INNER JOIN channels ON c.uid = f.channel
                GROUP BY f.id
                WHERE channel = ? ORDER BY id DESC;
            """,
                (channel,),
            ).fetchall()
        else:
            feeds = cursor.execute(
                """
                SELECT f.channel, f.url, f.etag, f.photo, f.name, f.id, f.muted, f.blocked, c.channel AS channel_name
                FROM following AS f, channels AS c
                INNER JOIN channels ON c.uid = f.channel
                GROUP BY f.id
                ORDER BY id DESC;
            """
            ).fetchall()

    # source: https://nickgeorge.net/programming/python-sqlite3-extract-to-dictionary/#writing_a_function
    unpacked = [{k: item[k] for k in item.keys()} for item in feeds]

    count = len(feeds)

    headers = {"Authorization": session["access_token"]}

    channel_req = requests.get(
        session.get("server_url") + "?action=channels", headers=headers
    )

    return render_template(
        "server/following.html",
        title="People You Follow",
        feeds=unpacked,
        count=count,
        channels=channel_req.json()["channels"],
    )
