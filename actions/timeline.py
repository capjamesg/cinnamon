import json
import sqlite3

from flask import jsonify, request

from .change_to_json import change_to_json


def get_timeline(request: request) -> dict:
    channel = request.args.get("channel")
    after = request.args.get("after")
    before = request.args.get("before")

    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        channel_arg = "channel = ? AND"
        second_channel_arg = "channel = ? AND"
        channel_tuple = (
            channel,
            channel,
        )

        if channel == "all":
            channel_arg = ""
            second_channel_arg = ""
            channel_tuple = ()

        if not after and not before:
            item_list = cursor.execute(
                f"""SELECT * FROM timeline WHERE {channel_arg} {second_channel_arg} hidden = 0 AND
                    feed_id IN (SELECT id FROM following WHERE muted = 0 AND blocked = 0)
                    ORDER BY date DESC, id DESC LIMIT 21;""",
                channel_tuple,
            ).fetchall()
        elif before and not after:
            item_list = cursor.execute(
                f"""SELECT * FROM timeline WHERE {channel_arg} {second_channel_arg} hidden = 0 AND
                    id < ? AND feed_id IN (SELECT id FROM following WHERE muted = 0 AND blocked = 0)
                    ORDER BY date DESC, id DESC LIMIT 21;""",
                channel_tuple + (int(before),),
            ).fetchall()
        else:
            item_list = cursor.execute(
                f"""SELECT * FROM timeline WHERE {channel_arg} {second_channel_arg} hidden = 0 AND
                id > ? AND feed_id IN (SELECT id FROM following WHERE muted = 0 AND blocked = 0)
                ORDER BY date DESC, id DESC LIMIT 21;""",
                channel_tuple + (int(after),),
            ).fetchall()

    items = [[json.loads(item[1]), item[3], item[5]] for item in item_list]

    for i in items:
        if i[1] == "unread":
            i[0]["_is_read"] = False
        else:
            i[0]["_is_read"] = True

        i[0]["_id"] = i[2]

    items = [i[0] for i in items]

    if (
        len(item_list) > 20
        and not request.args.get("after")
        and not request.args.get("before")
    ):
        # 8 = id
        before = item_list[-1][8]
        after = ""
    elif len(item_list) <= 21 and len(item_list) != 0:
        before = item_list[0][8]
        after = item_list[-1][8]
    else:
        before = ""
        after = ""

    return jsonify({"items": items, "paging": {"before": before, "after": after}}), 200


def get_post(request: request) -> dict:
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        cursor.execute(
            "SELECT * FROM timeline WHERE uid = ?", (request.args.get("id"),)
        )

    return jsonify({"post": change_to_json(cursor)}), 200


def remove_entry(request: request) -> dict:
    connection = sqlite3.connect("microsub.db")

    if request.form.getlist("entry[]"):
        for entry in request.form.getlist("entry[]"):
            with connection:
                cursor = connection.cursor()
                cursor.execute("UPDATE timeline SET hidden = 1 WHERE uid = ?", (entry,))

        return {"type": "remove_entry"}

    else:
        with connection:
            cursor = connection.cursor()

            cursor.execute(
                "UPDATE timeline SET hidden = 1 WHERE uid = ?",
                (request.form.get("entry"),),
            )

        return {"type": "remove_entry"}
