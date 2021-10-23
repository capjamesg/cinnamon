from flask import request, jsonify, escape
import sqlite3
import requests
from bs4 import BeautifulSoup
import feedparser
from . import poll_feeds
# import poll_feeds
import random
import string
import json

def change_to_json(database_result):
    columns = [column[0] for column in database_result.description]
    
    result = [dict(zip(columns, row)) for row in database_result]

    return result

def get_timeline():
    channel = request.args.get("channel")
    after = request.args.get("after")
    before = request.args.get("before")

    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        channel_arg = "channel = ? AND"
        channel_tuple = (channel,)

        if channel == "all":
            channel_arg = ""
            channel_tuple = ()

        if not after and not before:
            item_list = cursor.execute("SELECT * FROM timeline WHERE {} hidden = 0 ORDER BY date DESC LIMIT 20;".format(channel_arg), channel_tuple ).fetchall()
        elif before and not after:
            item_list = cursor.execute("SELECT * FROM timeline WHERE {} hidden = 0 AND date < ? ORDER BY date DESC LIMIT 20;".format(channel_arg), channel_tuple + (int(before), )).fetchall()
        else:
            item_list = cursor.execute("SELECT * FROM timeline WHERE {} hidden = 0 AND date < ? ORDER BY date DESC LIMIT 20;".format(channel_arg), channel_tuple + (int(after), )).fetchall()

    items = [[json.loads(item[1]), item[3], item[5]] for item in item_list]
    
    for i in items:
        if i[1] == "unread":
            i[0]["_is_read"] = False
        else:
            i[0]["_is_read"] = True

        i[0]["_id"] = i[2]

    items = [i[0] for i in items]

    items_for_date = [item for item in item_list]

    if len(item_list) > 0:
        before = items_for_date[0][2]
        after = items_for_date[-1][2]
    else:
        before = None
        after = None

    if not request.args.get("after") and not request.args.get("before"):
        before = None

    return jsonify({"items": items, "paging": {"before": before, "after": after}}), 200

def mark_as_read():
    connection = sqlite3.connect("microsub.db")

    read_status = request.form.get("method")

    if read_status == "mark_read":
        read = "read"
    else:
        read = "unread"

    if request.form.getlist("entry[]"):
        for entry in request.form.getlist("entry[]"):
            with connection:
                cursor = connection.cursor()
                cursor.execute("UPDATE timeline SET read_status = ? WHERE uid = ?", (read, entry, ))

                return {"type": "mark_as_read"}
    elif request.form.get("entry"):
        with connection:
            cursor = connection.cursor()
            cursor.execute("UPDATE timeline SET read_status = ? WHERE channel = ?", (read, request.form.get("channel"), ))

            return {"type": "mark_as_read"}
    else:
        with connection:
            cursor = connection.cursor()
            get_item = cursor.execute("SELECT date, channel FROM timeline WHERE uid = ?;", (request.form.get("last_read_entry"), )).fetchone()
            cursor.execute("UPDATE timeline SET read_status = ? WHERE date <= ? AND channel = ?", (read, get_item[0], get_item[1] ))

            return {"type": "mark_as_read"}

def discover_urls():
    url = request.args.get("url")

    r = requests.get(url)

    link_header = r.headers.get("Link")

    endpoints = {}

    look_for = ["authorization_endpoint", "token_endpoint", "microsub"]

    if link_header:
        for l in look_for:
            parsed_links = requests.utils.parse_header_links(link_header.rstrip('>').replace('>,<', ',<'))

            for link in parsed_links:
                if l in link["rel"]:
                    endpoints[l] = link["url"]
                    break

    soup = BeautifulSoup(r.text, "html.parser")

    # look for endpoints on url if none are available

    for item in soup():
        for l in look_for:
            if l not in endpoints.keys():
                if item.name == "a" and item.get("rel") and item["rel"][0] == l:
                    endpoints[l] = item.get("href")
                    break
                elif item.name == "link" and item.get("rel") and item["rel"][0] == l:
                    endpoints[l] = item.get("href")
                    break

def preview():
    url = request.form.get("url")

    r = requests.get(url)

    soup = BeautifulSoup(r.text, "html.parser")

    # get content type of url
    try:
        r = requests.head(url)
    except:
        return jsonify({"error": "invalid url"}), 400

    if r.headers.get('content-type'):
        content_type = r.headers['content-type']
    else:
        content_type = ""

    items_to_return = []

    if "xml" in content_type or ".xml" in url:
        feed = feedparser.parse(url)

        for entry in feed.entries:
            result, _ = poll_feeds.process_xml_feed(entry, feed, url)

            items_to_return.append(result)
    else:
        results = poll_feeds.process_hfeed(url, add_to_db=False)

        for result in results:
            items_to_return.append(result)

        content_type = "h-feed"

    feed = {
        "url": url,
        "feed_type": content_type
    }

    # get homepage favicon
    url_domain = url.split("/")[2]
    url_protocol = url.split("/")[0]

    url_to_check = url_protocol + "//" + url_domain

    soup = BeautifulSoup(requests.get(url_to_check).text, "html.parser")

    favicon = soup.find("link", rel="shortcut icon")

    if favicon:
        feed["icon"] = favicon.get("href")

    if soup.find("title"):
        feed["title"] = soup.find("title").text

    result = {
        "feed": feed,
        "items": items_to_return
    }

    return jsonify(result), 200

def get_channels():
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        cursor.execute("SELECT uid, channel FROM channels ORDER BY position ASC;")

        result = change_to_json(cursor)

        final_result = []

        total_unread = 0

        for r in result:
            get_unread = cursor.execute("SELECT COUNT(*) FROM timeline WHERE channel = ? AND read_status = 'unread';", (r["uid"],)).fetchone()
            r["unread"] = get_unread[0]
            r["name"] = r["channel"]
            total_unread += r["unread"]
            final_result.append(r)
            del r["channel"]

        # add "all" as a special value
        # used to show every post stored in the server
        final_result.append({"uid": "all", "name": "All", "unread": total_unread})

        return jsonify({"channels": final_result}), 200

def create_channel():
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()
        three_random_letters = "".join(random.choice(string.ascii_lowercase) for _ in range(3))
        # check if name taken
        cursor.execute("SELECT * FROM channels WHERE channel = ?", (request.args.get("name"),))

        if cursor.fetchone():
            return jsonify({"error": "This channel name has been taken."}), 400

        existing_channels = cursor.execute("SELECT position FROM channels ORDER BY position DESC LIMIT 1").fetchone()
        if existing_channels and len(existing_channels) > 0:
            last_position = int(existing_channels[0])
        else:
            last_position = 0

        cursor.execute("INSERT INTO channels VALUES(?, ?, ?)", (request.form.get("name"), request.form.get("name").lower() + three_random_letters, last_position + 1))

        all_channels = cursor.execute("SELECT * FROM channels ORDER BY position ASC").fetchall()

        return jsonify(all_channels), 200

def update_channel():
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()
        cursor.execute("UPDATE channels SET channel = ? WHERE uid = ?", (request.args.get("name"), request.args.get("channel")))

        get_updated_channel = cursor.execute("SELECT * FROM channels WHERE uid = ?", (request.args.get("channel"),)).fetchone()

        return get_updated_channel

def delete_channel():
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        cursor.execute("DELETE FROM channels WHERE uid = ?", (request.form.get("channel"),))

        return jsonify({"message": "channel deleted"}), 200

def get_follow(channel):
    connection = sqlite3.connect("microsub.db")

    print(channel)

    if not channel:
        return jsonify({}), 200

    with connection:
        cursor = connection.cursor()
        if channel == "all":
            results = cursor.execute("SELECT * FROM following;").fetchall()
        else:
            results = cursor.execute("SELECT * FROM following WHERE channel = ?", (channel,)).fetchall()

        print(results)

        results = [{"type": "feed", "url": r[1]} for r in results]

        final_result = {"items": results}

        return jsonify(final_result), 200

def create_follow():
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        url = escape(request.form.get("url").strip())

        # check if following
        cursor.execute("SELECT * FROM following WHERE channel = ? AND url = ?", (request.form.get("channel"), url))

        if cursor.fetchone():
            return jsonify({"error": "You are already following this feed in the {} channel.".format(request.form.get("channel"))}), 400

        # get information from feed web page

        r = requests.get(url)

        title = url
        favicon = ""

        soup = BeautifulSoup(r.text, "html.parser")

        if soup.find("title"):
            title = soup.find("title").text

        # get favicon

        favicon = soup.find("link", rel="shortcut icon")

        if favicon:
            favicon = favicon.get("href")        

        # "" empty string is etag which will be populated in poll_feeds.py if available
        cursor.execute("INSERT INTO following VALUES(?, ?, ?, ?, ?)", (request.form.get("channel"), url, "", favicon, title, ))

        # discover websub_hub

        # check link headers for websub hub

        link_header = r.headers.get("link")

        hub = None

        if link_header:
            # parse link header
            parsed_links = requests.utils.parse_header_links(link_header.rstrip('>').replace('>,<', ',<'))

            for link in parsed_links:
                if "rel" in link and "hub" in link["rel"]:
                    hub = link["url"]
                    break

        if hub == None:
            hub_link_tags = soup.find_all("link", rel="hub")

            if len(hub_link_tags) > 0:
                hub = hub_link_tags[0].get("href")

        if hub != None:
            random_string = "".join(random.choice(string.ascii_lowercase) for _ in range(10))

            r = requests.post(hub, data={"hub.mode": "subscribe", "hub.topic": url, "hub.callback": "https://microsub.jamesg.blog/websub_callback"})

            cursor.execute("INSERT INTO websub_subscriptions (?, ?);", (url, random_string))

        return {"type": "feed", "url": url}

def unfollow():
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM following WHERE url = ? AND channel = ?", (request.form.get("url"), request.form.get("channel"), ))

        return {"type": "unfollow"}

def get_muted():
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM muted_users WHERE muted = 1 AND channel = ?", (request.args.get("channel"),))

        return cursor.fetchall()

def mute():
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()
        cursor.execute("UPDATE muted_users SET muted = 1 WHERE channel = ?", (request.args.get("channel"),))

        return {"type": "mute"}

def unmute():
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()
        cursor.execute("UPDATE muted_users SET muted = 0 WHERE url = ?", (request.args.get("url"),))

        return {"type": "unmute"}
    
def remove_entry():
    connection = sqlite3.connect("microsub.db")

    if request.args.getlist("entry[]"):
        for entry in request.args.getlist("entry[]"):
            with connection:
                cursor = connection.cursor()
                cursor.execute("UPDATE timeline SET hidden = 1 WHERE channel = ? AND uid = ?", (request.form.get("channel"), entry ))

                return {"type": "remove_entry"}
    else:
        with connection:
            cursor = connection.cursor()

            cursor.execute("UPDATE timeline SET hidden = 1 WHERE channel = ? AND uid = ?", (request.form.get("channel"), request.form.get("entry") ))

            return {"type": "remove_entry"}

def reorder_channels():
    connection = sqlite3.connect("microsub.db")

    if len(request.form.getlist("channels")) == 2:
        with connection:
            cursor = connection.cursor()
            position_for_first = cursor.execute("SELECT position FROM channels WHERE uid = ?", (request.form.getlist("channels")[0],)).fetchone()
            position_for_second = cursor.execute("SELECT position FROM channels WHERE uid = ?", (request.form.getlist("channels")[1],)).fetchone()
            cursor.execute("UPDATE channels SET position = ? WHERE uid = ?", (position_for_second[0], request.form.getlist("channels")[0]))
            cursor.execute("UPDATE channels SET position = ? WHERE uid = ?", (position_for_first[0], request.form.getlist("channels")[1]))

            return {"type": "reorder"}

    with connection:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM channels")

        position = 1

        for channel in request.form.getlist("channels"):
            cursor.execute("INSERT INTO channels VALUES(?, ?, ?)", (channel["name"], channel["name"].lower(), position, ))

            position += 1

        return {"type": "reorder_channels"}