import random
import sqlite3
import string

from flask import jsonify, request

from .change_to_json import change_to_json


def get_channels() -> dict:
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        cursor.execute("SELECT uid, channel FROM channels ORDER BY position ASC;")

        result = change_to_json(cursor)

        final_result = []

        total_unread = 0

        for r in result:
            get_unread = cursor.execute(
                "SELECT COUNT(*) FROM timeline WHERE channel = ? AND read_status = 'unread';",
                (r["uid"],),
            ).fetchone()
            r["unread"] = get_unread[0]
            r["name"] = r["channel"]
            total_unread += r["unread"]
            final_result.append(r)
            del r["channel"]

        # add "all" as a special value
        # used to show every post stored in the server
        final_result.insert(0, {"uid": "all", "name": "All", "unread": total_unread})

        return jsonify({"channels": final_result}), 200


def create_channel(request: request) -> dict:
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()
        three_random_letters = "".join(
            random.choice(string.ascii_lowercase) for _ in range(3)
        )
        # check if name taken
        cursor.execute(
            "SELECT * FROM channels WHERE channel = ?", (request.args.get("name"),)
        )

        if cursor.fetchone():
            return jsonify({"error": "This channel name has been taken."}), 400

        existing_channels = cursor.execute(
            "SELECT position FROM channels ORDER BY position DESC LIMIT 1"
        ).fetchone()

        if existing_channels and len(existing_channels) > 0:
            last_position = int(existing_channels[0])
        else:
            last_position = 0

        cursor.execute(
            "INSERT INTO channels VALUES(?, ?, ?)",
            (
                request.form.get("name"),
                request.form.get("name").lower() + three_random_letters,
                last_position + 1,
            ),
        )

        all_channels = cursor.execute(
            "SELECT * FROM channels ORDER BY position ASC"
        ).fetchall()

        return jsonify(all_channels), 200


def update_channel(request: request) -> dict:
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE channels SET channel = ? WHERE uid = ?",
            (request.form.get("name"), request.form.get("channel")),
        )

        get_updated_channel = cursor.execute(
            "SELECT * FROM channels WHERE uid = ?", (request.form.get("channel"),)
        ).fetchone()

        return get_updated_channel


def delete_channel(request: request) -> dict:
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        get_channel = cursor.execute(
            "SELECT * FROM channels WHERE uid = ?", (request.form.get("channel"),)
        ).fetchone()

        if get_channel:
            cursor.execute(
                "DELETE FROM channels WHERE uid = ?", (request.form.get("channel"),)
            )

            # get_channel[0] is the deleted channel name
            return jsonify({"channel": get_channel[0]}), 200
        else:
            return jsonify({"error": "channel not found"}), 400


def reorder_channels(request: request) -> dict:
    connection = sqlite3.connect("microsub.db")

    if len(request.form.getlist("channels")) == 2:
        with connection:
            cursor = connection.cursor()
            position_for_first = cursor.execute(
                "SELECT position FROM channels WHERE uid = ?",
                (request.form.getlist("channels")[0],),
            ).fetchone()
            position_for_second = cursor.execute(
                "SELECT position FROM channels WHERE uid = ?",
                (request.form.getlist("channels")[1],),
            ).fetchone()
            cursor.execute(
                "UPDATE channels SET position = ? WHERE uid = ?",
                (position_for_second[0], request.form.getlist("channels")[0]),
            )
            cursor.execute(
                "UPDATE channels SET position = ? WHERE uid = ?",
                (position_for_first[0], request.form.getlist("channels")[1]),
            )

            return {"type": "reorder"}

    with connection:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM channels")

        position = 1

        for channel in request.form.getlist("channels"):
            cursor.execute(
                "INSERT INTO channels VALUES(?, ?, ?)",
                (
                    channel["name"],
                    channel["name"].lower(),
                    position,
                ),
            )

            position += 1

        return {"type": "reorder_channels"}
