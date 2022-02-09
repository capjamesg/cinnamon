import json
import sqlite3

from flask import request


def react(request: request) -> dict:
    connection = sqlite3.connect("microsub.db")

    uid = request.form.get("uid")
    reaction_type = request.form.get("reaction")
    reaction_url = request.form.get("url")

    with connection:
        cursor = connection.cursor()

        timeline_item = cursor.execute(
            "SELECT * FROM timeline WHERE uid = ?", (uid,)
        ).fetchone()

        jf2 = json.loads(timeline_item[1])

        if not jf2.get("reactions"):
            jf2["reactions"] = {}

        if not jf2["reactions"].get("replies"):
            jf2["reactions"]["replies"] = []

        if request.form.get("content"):
            jf2["reactions"]["replies"] = [
                {"content": request.form.get("content"), "url": reaction_url}
            ]
        else:
            jf2["reactions"][reaction_type] = ""

        cursor.execute(
            "UPDATE timeline SET jf2 = ? WHERE uid = ?", (json.dumps(jf2), uid)
        )

        return {"type": "success"}, 200


def mark_as_read(request: request) -> dict:
    connection = sqlite3.connect("microsub.db")

    read_status = request.form.get("method")

    if read_status == "mark_read":
        read = "read"
    else:
        read = "unread"

    with connection:
        cursor = connection.cursor()

        if request.form.get("channel") == "all":
            # set all items in the timeline to read other than notifications

            notification_channel = cursor.execute(
                "SELECT uid FROM channels WHERE position = 1;"
            ).fetchone()[0]

            cursor.execute(
                "UPDATE timeline SET read_status = ? WHERE channel != ?",
                (
                    read,
                    notification_channel,
                ),
            )

        if request.form.getlist("entry[]"):
            for entry in request.form.getlist("entry[]"):
                cursor.execute(
                    "UPDATE timeline SET read_status = ? WHERE uid = ?",
                    (
                        read,
                        entry,
                    ),
                )

        elif request.form.get("entry"):
            cursor.execute(
                "UPDATE timeline SET read_status = ? WHERE channel = ?",
                (
                    read,
                    request.form.get("channel"),
                ),
            )

        get_item = cursor.execute(
            "SELECT date, channel FROM timeline WHERE uid = ?;",
            (request.form.get("last_read_entry"),),
        ).fetchone()
        cursor.execute(
            "UPDATE timeline SET read_status = ? WHERE date <= ? AND channel = ?",
            (read, get_item[0], get_item[1]),
        )

    return {"type": "mark_as_read"}
