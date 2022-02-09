import json
import sqlite3

import requests
from flask import Blueprint, jsonify, redirect, request, session

from authentication.check_token import verify as check_token
from actions.preview import get_preview_items

websub = Blueprint("websub", __name__, template_folder="templates")


@websub.route("/websub/<uid>", methods=["POST"])
def save_new_post_from_websub(uid):
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        # check if subscription exists
        subscription = cursor.execute(
            "SELECT url, channel FROM websub_subscriptions WHERE uid = ? AND approved = 1",
            (uid,),
        ).fetchone()

        if not subscription:
            return jsonify({"error": "Subscription does not exist."}), 400

        url = subscription[0]
        channel = subscription[1]

        feed_id = cursor.execute(
            "SELECT id FROM following WHERE url = ?", (url,)
        ).fetchone()[0]

        # retrieve feed
        try:
            r = requests.get(url, timeout=5, allow_redirects=True)
        except requests.exceptions.RequestException:
            return jsonify({"error": "invalid url"}), 400

        if r.headers.get("content-type"):
            content_type = r.headers["content-type"]
        else:
            content_type = ""

        items_to_return, content_type = get_preview_items(content_type, url, r)

        last_id = cursor.execute("SELECT MAX(id) FROM timeline;").fetchone()

        if last_id[0] is not None:
            last_id = last_id[0] + 1
        else:
            last_id = 0

        for record in items_to_return:
            record["published"] = record.get("published")

            cursor.execute(
                """INSERT INTO timeline VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                (
                    channel,
                    json.dumps(record),
                    record["published"],
                    0,
                    record["url"],
                    record["url"],
                    0,
                    feed_id,
                    last_id,
                ),
            )

            last_id += 1

    return jsonify({"success": "Entry added to feed."}), 200


@websub.route("/websub_callback")
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
                ),
            ).fetchone()

            if not check_subscription:
                return jsonify({"error": "Subscription does not exist."}), 400

            cursor.execute(
                "UPDATE websub_subscriptions SET approved = ? WHERE url = ?",
                (
                    1,
                    request.args.get("hub.topic"),
                ),
            )

        return request.args.get("hub.challenge"), 200

    return jsonify({"error": "No challenge found."}), 400
