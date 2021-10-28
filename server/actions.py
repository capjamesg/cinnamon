from flask import request, jsonify, escape
import sqlite3
import requests
from bs4 import BeautifulSoup
import feedparser
from ..feeds import hfeed, json_feed, xml_feed
from ..feeds import canonicalize_url as canonicalize_url
from ..config import URL
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
        second_channel_arg = "channel = ? AND"
        channel_tuple = (channel,)

        if channel == "all":
            channel_arg = ""
            second_channel_arg = ""
            channel_tuple = ()

        if not after and not before:
            item_list = cursor.execute("SELECT * FROM timeline WHERE {} hidden = 0 AND feed_id IN (SELECT id FROM following WHERE muted = 0 AND blocked = 0) ORDER BY date DESC, id DESC LIMIT 21;".format(channel_arg, second_channel_arg), channel_tuple ).fetchall()
        elif before and not after:
            item_list = cursor.execute("SELECT * FROM timeline WHERE {} hidden = 0 AND id < ? AND feed_id IN (SELECT id FROM following WHERE muted = 0 AND blocked = 0) ORDER BY date DESC, id DESC LIMIT 21;".format(channel_arg, second_channel_arg), channel_tuple + (int(before), )).fetchall()
        else:
            item_list = cursor.execute("SELECT * FROM timeline WHERE {} hidden = 0 AND id > ? AND feed_id IN (SELECT id FROM following WHERE muted = 0 AND blocked = 0) ORDER BY date DESC, id DESC LIMIT 21;".format(channel_arg, second_channel_arg), channel_tuple + (int(after), )).fetchall()

    items = [[json.loads(item[1]), item[3], item[5]] for item in item_list]
    
    for i in items:
        if i[1] == "unread":
            i[0]["_is_read"] = False
        else:
            i[0]["_is_read"] = True

        i[0]["_id"] = i[2]

    items = [i[0] for i in items]

    items_for_date = [item for item in item_list]

    if len(item_list) > 20 and not request.args.get("after") and not request.args.get("before"):
        # 8 = id
        before = item_list[-1][8]
        after = item_list[0][8]
    elif len(item_list) <= 20 and len(item_list) != 0:
        before = items_for_date[-1][8]
        after = ""
    else:
        before = ""
        after = ""

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

def search_for_content():
    connection = sqlite3.connect("microsub.db")

    query = request.form.get("query")

    with connection:
        cursor = connection.cursor()

        result = cursor.execute("SELECT * FROM timeline WHERE jf2 LIKE ? ORDER BY date DESC;", ("%{}%".format(query), )).fetchall()

        items = [[json.loads(item[1]), item[3], item[5]] for item in result]

        items = [i[0] for i in items]

        return jsonify({"items": items}), 200

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
            result, _ = xml_feed.process_xml_feed(entry, feed, url)

            items_to_return.append(result)
    elif "json" in content_type or url.endswith(".json"):
        try:
            feed = requests.get(url, timeout=5).json()
        except:
            return jsonify({"error": "invalid url"}), 400

        for entry in feed.get("items", []):
            result, _ = json_feed.process_json_feed(entry, feed)

            items_to_return.append(result)
    else:
        results = hfeed.process_hfeed(url, add_to_db=False)

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
        feed["icon"] = canonicalize_url.canonicalize_url(favicon.get("href"), url_domain, favicon.get("href"))

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
        final_result.insert(0, {"uid": "all", "name": "All", "unread": total_unread})

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
        cursor.execute("UPDATE channels SET channel = ? WHERE uid = ?", (request.form.get("name"), request.form.get("channel")))

        get_updated_channel = cursor.execute("SELECT * FROM channels WHERE uid = ?", (request.form.get("channel"),)).fetchone()

        return get_updated_channel

def delete_channel():
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        get_channel = cursor.execute("SELECT * FROM channels WHERE uid = ?", (request.form.get("channel"),)).fetchone()

        if get_channel:
            cursor.execute("DELETE FROM channels WHERE uid = ?", (request.form.get("channel"),))

            # delete timeline posts in channel
            cursor.execute("DELETE FROM timeline WHERE channel = ?", (request.form.get("channel"),))

            # get_channel[0] is the deleted channel name
            return jsonify({"channel": get_channel[0]}), 200
        else:
            return jsonify({"error": "channel not found"}), 400

def get_follow(channel):
    connection = sqlite3.connect("microsub.db")

    if not channel:
        return jsonify({}), 200

    with connection:
        cursor = connection.cursor()
        if channel == "all":
            results = cursor.execute("SELECT * FROM following;").fetchall()
        else:
            results = cursor.execute("SELECT * FROM following WHERE channel = ?", (channel,)).fetchall()

        results = [{"type": "feed", "url": r[1], "photo": r[3], "name": r[4]} for r in results]

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
            favicon = canonicalize_url.canonicalize_url(favicon.get("href"), url.split("/")[2], favicon.get("href"))

        if not favicon:
            favicon = soup.find("link", rel="icon")

            if favicon:
                favicon = canonicalize_url.canonicalize_url(favicon.get("href"), url.split("/")[2], favicon.get("href"))

        # "" empty string is etag which will be populated in poll_feeds.py if available
        last_id = cursor.execute("SELECT MAX(id) FROM following").fetchone()

        if last_id and last_id [0] != None:
            print(last_id)
            last_id = last_id[0] + 1
        else:
            last_id = 1

        cursor.execute("INSERT INTO following VALUES(?, ?, ?, ?, ?, ?, ?, ?)", (request.form.get("channel"), url, "", favicon, title, last_id, 0, 0 ))

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

            r = requests.post(hub, data={"hub.mode": "subscribe", "hub.topic": url, "hub.callback": URL.strip("/") + "/websub_callback"})

            cursor.execute("INSERT INTO websub_subscriptions VALUES (?, ?, ?, ?);", (url, random_string, request.form.get("channel"), 1 ))

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
        cursor.execute("SELECT * FROM following WHERE muted = 1 AND channel = ?", (request.args.get("channel"),))

        return cursor.fetchall()

def mute():
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        cursor.execute("UPDATE following SET muted = 1 WHERE url = ?", (request.form.get("url"),))

        get_url = cursor.execute("SELECT url FROM following WHERE url = ?", (request.form.get("url"),)).fetchone()

        if get_url:
            return jsonify({"url": get_url[0], "type": "mute"}), 200
        else:
            return jsonify({"error": "You are not following this feed."}), 400

def block():
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        cursor.execute("UPDATE following SET blocked = 1 WHERE url = ?", (request.form.get("url"),))

        get_url = cursor.execute("SELECT url FROM following WHERE url = ?", (request.form.get("url"),)).fetchone()

        if get_url:
            return jsonify({"url": get_url[0], "type": "block"}), 200
        else:
            return jsonify({"error": "You are not following this feed."}), 400

def unblock():
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        cursor.execute("UPDATE following SET blocked = 0 WHERE url = ?", (request.form.get("url"),))

        get_url = cursor.execute("SELECT url FROM following WHERE url = ?", (request.form.get("url"),)).fetchone()

        if get_url:
            return jsonify({"url": get_url[0], "type": "unblock"}), 200
        else:
            return jsonify({"error": "You are not following this feed."}), 400

def unmute():
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        cursor.execute("UPDATE following SET muted = 0 WHERE url = ?", (request.form.get("url"),))

        get_url = cursor.execute("SELECT url FROM following WHERE url = ?", (request.form.get("url"),)).fetchone()

        if get_url:
            return jsonify({"url": get_url[0], "type": "unmute"}), 200
        else:
            return jsonify({"error": "You are not following this feed."}), 400
    
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