import random
import sqlite3
import string

import indieweb_utils
import requests
from bs4 import BeautifulSoup
from flask import escape, jsonify, request
from urllib.parse import urlparse as parse_url

from config import URL


def get_follow(channel: str, request: dict) -> dict:
    connection = sqlite3.connect("microsub.db")

    if not channel:
        return jsonify({}), 200

    with connection:
        cursor = connection.cursor()
        if channel == "all":
            results = cursor.execute(
                "SELECT * FROM following ORDER BY id DESC;"
            ).fetchall()
        else:
            results = cursor.execute(
                "SELECT * FROM following WHERE channel = ? ORDER by id DESC;",
                (channel,),
            ).fetchall()

        results = [
            {"type": "feed", "url": r[1], "photo": r[3], "name": r[4]} for r in results
        ]

        final_result = {"items": results}

        return jsonify(final_result), 200


def create_follow(request: request) -> dict:
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        url = escape(request.form.get("url").strip())

        # check if following
        cursor.execute(
            "SELECT * FROM following WHERE channel = ? AND url = ?",
            (request.form.get("channel"), url),
        )

        if cursor.fetchone():
            return (
                jsonify(
                    {
                        "error": f"You are already following this feed in the {request.form.get('channel')} channel."
                    }
                ),
                400,
            )
        title = url
        favicon = ""

        home_page_request = requests.get(
            indieweb_utils.canonicalize_url(url, url)
        ).text

        home_page = BeautifulSoup(home_page_request, "lxml")

        if home_page.find("title"):
            title = home_page.find("title").text

        # "" empty string is etag which will be populated in poll_feeds.py if available
        last_id = cursor.execute("SELECT MAX(id) FROM following").fetchone()

        if last_id and last_id[0] is not None:
            last_id = last_id[0] + 1
        else:
            last_id = 1

        favicon = get_feed_icon(home_page, url)

        # set cadence to hourly by default
        cursor.execute(
            "INSERT INTO following VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                request.form.get("channel"),
                url,
                "",
                favicon,
                title,
                last_id,
                0,
                0,
                "hourly",
            ),
        )

        subscribe_to_websub_hub(request, home_page, url, cursor)

        return {"type": "feed", "url": url}


def get_feed_icon(home_page: BeautifulSoup, url: str) -> str:
    favicon = home_page.find("link", rel="shortcut icon")

    url_domain = parse_url(url).netloc

    if favicon:
        favicon = indieweb_utils.canonicalize_url(
            favicon.get("href"), url_domain, url
        )
    else:
        favicon = ""

    if favicon == "":
        favicon = home_page.find("link", rel="icon")

        if favicon:
            favicon = indieweb_utils.canonicalize_url(
                favicon.get("href"), url_domain, url
            )

    if favicon:
        try:
            r = requests.get(favicon)

            if r.status_code != 200:
                favicon = ""
        except requests.exceptions.RequestException:
            favicon = ""

    if not favicon or favicon == "":
        favicon = "/static/gradient.png"

    return favicon


def subscribe_to_websub_hub(
    request: request, soup: BeautifulSoup, url: str, cursor: sqlite3.Cursor
) -> dict:
    # discover websub_hub

    # check link headers for websub hub

    link_header = request.headers.get("link")

    hub = None

    if link_header:
        # parse link header
        parsed_links = requests.utils.parse_header_links(
            link_header.rstrip(">").replace(">,<", ",<")
        )

        for link in parsed_links:
            if "rel" in link and "hub" in link["rel"]:
                hub = link["url"]
                break

    if hub is None:
        hub_link_tags = soup.find_all("link", rel="hub")

        if len(hub_link_tags) > 0:
            hub = hub_link_tags[0].get("href")

    if hub is None:
        return

    random_string = "".join(random.choice(string.ascii_lowercase) for _ in range(10))

    requests.post(
        hub,
        data={
            "hub.mode": "subscribe",
            "hub.topic": url,
            "hub.callback": URL.strip("/") + "/websub_callback",
        },
    )

    cursor.execute(
        "INSERT INTO websub_subscriptions VALUES (?, ?, ?, ?);",
        (url, random_string, request.form.get("channel"), 1),
    )


def unfollow(request: request) -> dict:
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM following WHERE url = ? AND channel = ?",
            (
                request.form.get("url"),
                request.form.get("channel"),
            ),
        )

        return {"type": "unfollow"}
