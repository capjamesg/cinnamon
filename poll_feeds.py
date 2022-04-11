import concurrent.futures
import datetime
import json
import logging
import os
import random
import sqlite3
import string

import feedparser
import mf2py
import requests
from dates import find_poll_cadence

from config import PROJECT_DIRECTORY, WEBHOOK_CHANNEL, WEBHOOK_TOKEN, WEBHOOK_URL
from feeds import hfeed, json_feed, xml_feed

logging.basicConfig(
    filename=f"logs/{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.log",
    datefmt="%Y-%m-%d %H:%M:%S",
)

print(
    f"Printing logs to logs/{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.log"
)

poll_cadences = []

# delete feed_items.json file so old records are not added to db again
if os.path.isfile(PROJECT_DIRECTORY.rstrip("/") + "/feed_items.json"):
    os.remove(PROJECT_DIRECTORY.rstrip("/") + "/feed_items.json")


def handle_xml_feed(channel_uid: str, url: str, feed_id: str, etag: str) -> None:
    try:
        feed = requests.get(url, timeout=20)
    except requests.exceptions.RequestException:
        return

    feed = feedparser.parse(feed.text)

    print("entries found: " + str(len(feed.entries)))

    validate_entry_count(feed.entries, url, feed_id)

    dates = []

    for entry in feed.entries[:10]:
        result, published = xml_feed.process_xml_feed(entry, feed, url)

        if result == None:
            continue

        ten_random_letters = "".join(
            random.choice(string.ascii_lowercase) for _ in range(10)
        )

        record = {
            "channel_uid": channel_uid,
            "result": json.dumps(result),
            "published": published,
            "unread": "unread",
            "url": result["url"],
            "uid": ten_random_letters,
            "hidden": 0,
            "feed_id": feed_id,
            "etag": etag,
            "feed_url": url,
        }

        dates.append(published)

        with open(PROJECT_DIRECTORY + "/feed_items.json", "a+") as file:
            file.write(json.dumps(record) + "\n")

    poll_cadence = find_poll_cadence(dates)

    poll_cadences.append((poll_cadence, url))


def handle_json_feed(
    channel_uid: str, url: str, feed_id: str, etag: str, s: list
) -> None:
    try:
        feed = requests.get(url, timeout=20)
    except requests.exceptions.RequestException:
        return

    if feed.status_code != 200:
        return

    # get etag header
    etag = feed.headers.get("etag", "")

    if etag != "" and etag == s[2]:
        print(f"{url} has not changed since last poll, skipping")
        return

    feed = feed.json()

    dates = []

    print("entries found: " + str(len(feed.get("items", []))))

    validate_entry_count(feed.get("items", []), url, feed_id)

    for entry in feed.get("items", []):
        result, published = json_feed.process_json_feed(entry, feed)

        if result is None:
            continue

        ten_random_letters = "".join(
            random.choice(string.ascii_lowercase) for _ in range(10)
        )

        record = {
            "channel_uid": channel_uid,
            "result": json.dumps(result),
            "published": published,
            "unread": "unread",
            "url": result["url"],
            "uid": ten_random_letters,
            "hidden": 0,
            "feed_id": feed_id,
            "etag": etag,
            "feed_url": url,
        }

        with open(PROJECT_DIRECTORY + "/feed_items.json", "a+") as file:
            file.write(json.dumps(record) + "\n")

        dates.append(published)

    poll_cadence = find_poll_cadence(dates)

    poll_cadences.append((poll_cadence, url))


def handle_hfeed(channel_uid, url, feed_id, etag):
    session = requests.Session()
    session.max_redirects = 2

    accept_headers = {
        "Accept": "text/html",
    }

    try:
        r = session.get(url, allow_redirects=True, timeout=10, headers=accept_headers)
    except requests.exceptions.RequestException:
        return None

    mf2_raw = mf2py.parse(r.text)

    hcard = [item for item in mf2_raw["items"] if item["type"][0] == "h-card"]

    h_feed = [
        item
        for item in mf2_raw["items"]
        if item["type"] and item["type"][0] == "h-feed"
    ]

    feed_title = None
    feed_icon = None

    dates = []

    if len(h_feed) > 0 and h_feed[0].get("children"):
        feed = h_feed[0]["children"]
        feed_title = h_feed[0]["properties"].get("name")

        if feed_title:
            feed_title = feed_title[0]

        feed_icon = h_feed[0]["properties"].get("icon")

        if feed_icon:
            feed_icon = feed_icon[0]
        feed = [item for item in feed if item["type"] == ["h-entry"]]
    else:
        # get all non h-card items
        # this will let the program parse non h-entry feeds such as h-event feeds
        feed = [
            item
            for item in mf2_raw["items"]
            if item["type"] and item["type"][0] != ["h-card"]
        ]

        if len(feed) == 0:
            return None

    print("entries found: " + str(len(feed)))

    validate_entry_count(feed, url, feed_id)

    for child in feed[:10]:
        result = hfeed.process_hfeed(
            child, hcard, channel_uid, url, feed_id, feed_title
        )

        if result == {}:
            continue

        ten_random_letters = "".join(
            random.choice(string.ascii_lowercase) for _ in range(10)
        )

        record = {
            "channel_uid": channel_uid,
            "result": json.dumps(result),
            "published": result["published"],
            "unread": "unread",
            "url": result["url"],
            "uid": ten_random_letters,
            "hidden": 0,
            "feed_id": feed_id,
            "etag": etag,
            "feed_url": url,
        }

        with open(PROJECT_DIRECTORY + "/feed_items.json", "a+") as file:
            file.write(json.dumps(record) + "\n")

        dates.append(result["published"])

    poll_cadence = find_poll_cadence(dates)

    poll_cadences.append((poll_cadence, url))


def validate_entry_count(entries, feed_url, feed_id):
    length = len(entries)

    if length < 3:
        published = datetime.datetime.now().strftime("%Y%m%d")

        message = f"""{feed_url} feed does not have any posts.
                    Please check that the feed URL is working correctly."""

        jf2 = {
            "type": "entry",
            "content": {
                "text": message,
                "html": message,
            },
            "published": published,
            "title": f"{feed_url} feed does not have any posts",
            "url": "https://webmention.jamesg.blog",
            "wm-property": "article",
        }

        ten_random_letters = "".join(
            random.choice(string.ascii_lowercase) for _ in range(10)
        )

        record = {
            "channel_uid": "notifications",
            "result": json.dumps(jf2),
            "published": published,
            "unread": "unread",
            "url": jf2["url"],
            "uid": ten_random_letters,
            "hidden": 0,
            "feed_id": feed_id,
            "etag": "",
            "feed_url": feed_url,
        }

        with open(PROJECT_DIRECTORY + "/feed_items.json", "a+") as file:
            file.write(json.dumps(record) + "\n")


def extract_feed_items(s, url, channel_uid, feed_id):
    session = requests.Session()
    session.max_redirects = 2

    headers = {
        "If-None-Match": s[2],
        "If-Modified-Since": s[4],
    }

    try:
        r = session.head(url, allow_redirects=True, timeout=10, headers=headers)
    except requests.exceptions.RequestException:
        return [None, None]

    if r.status_code == 304:
        # nothing has changed, escape
        return [None, None]

    # get content type of url
    if r.headers.get("content-type"):
        content_type = r.headers["content-type"]
    else:
        content_type = ""

    # # get etag of url
    if r.headers.get("etag"):
        etag = r.headers["etag"]
    else:
        etag = ""

    if etag != "" and etag == s[2]:
        print(f"{url} has not changed since last poll, skipping")
        return [None, None]

    # get last modified date of url
    if r.headers.get("last-modified"):
        last_modified = r.headers["last-modified"]
    else:
        last_modified = ""

    if last_modified != "" and datetime.datetime.strptime(
        last_modified, "%a, %d %b %Y %H:%M:%S %Z"
    ) < datetime.datetime.now() - datetime.timedelta(hours=12):
        print(f"{url} has not been modified in the last 12 hours, skipping")
        return [None, None]

    if "xml" in content_type or content_type == "binary/octet-stream":
        handle_xml_feed(channel_uid, url, feed_id, etag)
    elif "application/json" in content_type:
        handle_json_feed(channel_uid, url, feed_id, etag, s)
    else:
        handle_hfeed(channel_uid, url, feed_id, etag)

    return r.headers.get("Last-Modified", ""), feed_id


def poll_feeds():
    connection = sqlite3.connect(PROJECT_DIRECTORY.rstrip("/") + "/microsub.db")

    with connection:
        cursor = connection.cursor()

        # don't poll feeds that have been blocked
        # see https://indieweb.org/Microsub-spec#Blocking

        subscriptions = cursor.execute(
            "SELECT url, channel, etag, id, poll_cadence FROM following WHERE blocked = 0"
        ).fetchall()

        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
            channel_uids = []
            tasks = []

            for s in subscriptions:
                if s[0] is None:
                    continue

                url = s[0]
                feed_id = s[3]

                # get channel uid
                try:
                    channel_uid = cursor.execute(
                        "SELECT uid FROM channels WHERE uid = ?;", (s[1],)
                    ).fetchone()
                    if channel_uid:
                        channel_uids.append(channel_uid[0])
                except Exception as e:
                    print(e)
                    print("channel uid not found")
                    # continue

                tasks.append(
                    executor.submit(extract_feed_items, s, url, channel_uid, feed_id)
                )

            for task in concurrent.futures.as_completed(tasks):
                try:
                    modified_since, feed_item = task.result()

                    if modified_since is not None:
                        cursor.execute(
                            "UPDATE following SET poll_cadence = ? WHERE id = ?;",
                            (modified_since, feed_item),
                        )
                except Exception as e:
                    print(e)
                    continue

    print("polled all subscriptions")


def write_record_to_database(line, cursor, last_id):
    record = json.loads(line)

    print("Adding: " + record["url"])

    # check if url in db
    in_db = cursor.execute(
        "SELECT * FROM timeline WHERE url = ?", (record["url"],)
    ).fetchall()

    if len(in_db) > 0:
        return

    if type(record["channel_uid"]) == list:
        record["channel_uid"] = record["channel_uid"][0]

    if record["channel_uid"] == WEBHOOK_CHANNEL and WEBHOOK_TOKEN != "":
        record_jf2 = json.loads(record["result"])
        # send notification to calibot that a new post has been found
        data = {
            "message": "{} ({}) has been published in the {} channel.".format(
                record_jf2["title"],
                record_jf2["url"],
                record["channel_uid"],
            )
        }

        headers = {"Authorization": "Bearer " + WEBHOOK_TOKEN}

        try:
            requests.post(WEBHOOK_URL, data=data, headers=headers)
        except requests.exceptions.RequestException:
            print("error sending webhook")

    cursor.execute(
        """INSERT INTO timeline VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);""",
        (
            record["channel_uid"],
            record["result"],
            record["published"],
            record["unread"],
            record["url"],
            record["uid"],
            record["hidden"],
            record["feed_id"],
            last_id,
        ),
    )

    last_id += 1

    # update following to add new etag so we can track modifications to a feed
    cursor.execute(
        "UPDATE following SET etag = ? WHERE url = ?;",
        (record["etag"], record["feed_url"]),
    )


def add_feed_items_to_database():
    print("adding feed items to database")

    with open(PROJECT_DIRECTORY.rstrip("/") + "/feed_items.json", "r") as f:
        connection = sqlite3.connect(PROJECT_DIRECTORY.rstrip("/") + "/microsub.db")

        with connection:
            cursor = connection.cursor()

            for p in poll_cadences:
                cursor.execute(
                    "UPDATE following SET poll_cadence = ? WHERE url = ?;", (p[0], p[1])
                )

            last_id = cursor.execute("SELECT MAX(id) FROM timeline;").fetchone()

            if last_id[0] is not None:
                last_id = last_id[0] + 1
            else:
                last_id = 0

            for line in f:
                write_record_to_database(line, cursor, last_id)
                last_id += 1


if __name__ == "__main__":
    poll_feeds()
    add_feed_items_to_database()

    # remove feed items file after all items have been added to the database
    os.remove(PROJECT_DIRECTORY + "/feed_items.json")
