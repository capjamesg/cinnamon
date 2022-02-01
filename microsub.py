import os
import sqlite3

import requests
from flask import (Flask, current_app, flash, jsonify, redirect,
                   render_template, request, send_from_directory, session)
from indieauth import requires_indieauth

from actions import *
from config import *

app = Flask(__name__, static_folder="static", static_url_path="")

# read config.py file
app.config.from_pyfile(os.path.join(".", "config.py"), silent=False)

# set secret key
app.secret_key = SECRET_KEY


def check_token():
    check_token = requests.get(
        TOKEN_ENDPOINT, headers={"Authorization": "Bearer " + session["access_token"]}
    )

    if check_token.status_code != 200 or (
        check_token.json().get("me") and check_token.json()["me"] != ME
    ):
        return False

    return True


@app.route("/")
def index():
    return render_template("index.html", title="Home | Microsub Endpoint")


@app.route("/endpoint", methods=["GET", "POST"])
@requires_indieauth
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
        return (
            jsonify(
                {
                    "error": "invalid_request",
                    "error_description": "The action and method provided are not valid.",
                }
            ),
            400,
        )


@app.route("/reorder", methods=["POST"])
def reorder_channels_view():
    auth_result = check_token(request.headers, session)

    if auth_result == False:
        return redirect("/login")

    if request.form.get("channel"):
        req = {
            "action": "channels",
            "method": "order",
            "channels": request.form.getlist("channel"),
        }

        r = requests.post(
            URL,
            data=req,
            headers={"Authorization": "Bearer " + session["access_token"]},
        )

        if r.status_code == 200:
            flash("Your channels have been reordered.")
        else:
            flash(r.json()["error"])

        return redirect("/lists")
    else:
        return redirect("/lists")


@app.route("/create-channel", methods=["POST"])
def create_channel_view():
    auth_result = check_token(request.headers, session)

    if auth_result == False:
        return redirect("/login")

    if request.form.get("name"):
        req = {"action": "channels", "name": request.form.get("name")}

        r = requests.post(
            URL,
            data=req,
            headers={"Authorization": "Bearer " + session["access_token"]},
        )

        if r.status_code == 200:
            flash(f"You have created a new channel called {request.form.get('name')}.")
        else:
            flash(r.json()["error"])

        return redirect("/lists")
    else:
        return redirect("/lists")


@app.route("/delete-channel", methods=["POST"])
def delete_channel_view():
    auth_result = check_token(request.headers, session)

    if auth_result == False:
        return redirect("/login")

    if request.form.get("channel"):
        req = {
            "action": "channels",
            "channel": request.form.get("channel"),
            "method": "delete",
        }

        r = requests.post(
            URL, data=req, headers={"Authorization": session["access_token"]}
        )

        if r.status_code == 200:
            flash(f"You have deleted the {r.json()['channel']} channel.")
        else:
            flash(r.json()["error"])

        return redirect("/lists")
    else:
        return redirect("/lists")


@app.route("/unfollow", methods=["POST"])
def unfollow_view():
    auth_result = check_token(request.headers, session)

    if auth_result == False:
        return redirect("/login")

    if request.form.get("channel") and request.form.get("url"):
        req = {
            "action": "unfollow",
            "channel": request.form.get("channel"),
            "url": request.form.get("url"),
        }

        r = requests.post(
            URL, data=req, headers={"Authorization": session.get("access_token")}
        )

        if r.status_code == 200:
            return jsonify(r.json()), 200
        else:
            return jsonify(r.json()), 400
    else:
        return redirect("/following")


@app.route("/channel/<id>", methods=["GET", "POST"])
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

        r = requests.post(
            URL, data=req, headers={"Authorization": session.get("access_token")}
        )

        if r.status_code == 200:
            flash(f"The channel was successfully renamed to {request.form.get('name')}")
        else:
            flash("Something went wrong. Please try again.")

    with connection:
        cursor = connection.cursor()
        channel = cursor.execute(
            "SELECT * FROM channels WHERE uid = ?", (id,)
        ).fetchone()
        feeds = cursor.execute(
            "SELECT * FROM following WHERE channel = ?", (id,)
        ).fetchall()

        return render_template(
            "modify_channel.html",
            title=f"Modify {channel[0]} Channel",
            channel=channel,
            feeds=feeds,
        )


@app.route("/assets/<path:path>")
def assets(path):
    return send_from_directory("assets", path)


@app.route("/robots.txt")
def robots():
    return send_from_directory(app.static_folder, "robots.txt")


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(app.static_folder, "favicon.ico")


if __name__ == "__main__":
    app.run()
