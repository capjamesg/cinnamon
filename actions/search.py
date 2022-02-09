import json
import sqlite3

import requests
from flask import jsonify, request


def search_for_content(request: request) -> dict:
    channel = request.form.get("channel")
    query = request.form.get("query")

    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        if channel == "all":
            result = cursor.execute(
                "SELECT jf2 FROM timeline WHERE jf2 LIKE ? ORDER BY date DESC;",
                (f"%{query}%",),
            ).fetchall()
        else:
            result = cursor.execute(
                "SELECT jf2 FROM timeline WHERE jf2 LIKE ? AND channel = ? ORDER BY date DESC;",
                (f"%{query}%", channel),
            ).fetchall()

    items = [[json.loads(item[1]), item[3], item[5]] for item in result]

    return jsonify({"items": items})


def search_for_feeds(request: request) -> dict:
    query = request.form.get("query").strip()

    search_url = (
        f"https://indieweb-search.jamesg.blog/results?query=discover {query}&format=jf2"
    )

    r = requests.get(search_url)

    if r.status_code == 200:
        return jsonify({"items": r.json()})
    else:
        return jsonify({"items": []})
