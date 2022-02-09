import sqlite3

from flask import jsonify, request


def get_muted(request: request) -> dict:
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT * FROM following WHERE muted = 1 AND channel = ?",
            (request.args.get("channel"),),
        )

        return cursor.fetchall()


def mute(request: request) -> dict:
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        cursor.execute(
            "UPDATE following SET muted = 1 WHERE url = ?", (request.form.get("url"),)
        )

        get_url = cursor.execute(
            "SELECT url FROM following WHERE url = ?", (request.form.get("url"),)
        ).fetchone()

        if get_url:
            return jsonify({"url": get_url[0], "type": "mute"}), 200
        else:
            return jsonify({"error": "You are not following this feed."}), 400


def block(request: request) -> dict:
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        cursor.execute(
            "UPDATE following SET blocked = 1 WHERE url = ?", (request.form.get("url"),)
        )

        get_url = cursor.execute(
            "SELECT url FROM following WHERE url = ?", (request.form.get("url"),)
        ).fetchone()

        if get_url:
            return jsonify({"url": get_url[0], "type": "block"}), 200
        else:
            return jsonify({"error": "You are not following this feed."}), 400


def unblock(request: request) -> dict:
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        cursor.execute(
            "UPDATE following SET blocked = 0 WHERE url = ?", (request.form.get("url"),)
        )

        get_url = cursor.execute(
            "SELECT url FROM following WHERE url = ?", (request.form.get("url"),)
        ).fetchone()

        if get_url:
            return jsonify({"url": get_url[0], "type": "unblock"}), 200
        else:
            return jsonify({"error": "You are not following this feed."}), 400


def unmute(request: request) -> dict:
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        cursor.execute(
            "UPDATE following SET muted = 0 WHERE url = ?", (request.form.get("url"),)
        )

        get_url = cursor.execute(
            "SELECT url FROM following WHERE url = ?", (request.form.get("url"),)
        ).fetchone()

        if get_url:
            return jsonify({"url": get_url[0], "type": "unmute"}), 200
        else:
            return jsonify({"error": "You are not following this feed."}), 400
