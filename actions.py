from flask import request, jsonify, escape
import sqlite3
import requests
from bs4 import BeautifulSoup
import feedparser
import mf2py
from feeds import hfeed, json_feed, xml_feed
import indieweb_utils
from config import URL
import random
import string
import json

def change_to_json(database_result):
    columns = [column[0] for column in database_result.description]
    
    result = [dict(zip(columns, row)) for row in database_result]

    return result

def search_for_content():
    channel = request.form.get("channel")
    query = request.form.get("query")

    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        if channel == "all":
            result = cursor.execute("SELECT jf2 FROM timeline WHERE jf2 LIKE ? ORDER BY date DESC;", (f"%{query}%", )).fetchall()
        else:
            result = cursor.execute("SELECT jf2 FROM timeline WHERE jf2 LIKE ? AND channel = ? ORDER BY date DESC;", (f"%{query}%", channel)).fetchall()

    items = [[json.loads(item[1]), item[3], item[5]] for item in result]

    return jsonify({"items": items})

def search_for_feeds():
    query = request.form.get("query").strip()

    search_url = "https://indieweb-search.jamesg.blog/results?query=discover {}&format=jf2".format(query)

    r = requests.get(search_url)

    if r.status_code == 200:
        return jsonify({"items": r.json()})
    else:
        return jsonify({"items": []})

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
    
    if len(item_list) > 20 and not request.args.get("after") and not request.args.get("before"):
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

def get_post():
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        cursor.execute("SELECT * FROM timeline WHERE uid = ?", (request.args.get("id"), ))

    return jsonify({"post": change_to_json(cursor)}), 200

def react():
    connection = sqlite3.connect("microsub.db")

    uid = request.form.get("uid")
    reaction_type = request.form.get("reaction")
    reaction_url = request.form.get("url")

    with connection:
        cursor = connection.cursor()

        timeline_item = cursor.execute("SELECT * FROM timeline WHERE uid = ?", (uid, )).fetchone()

        jf2 = json.loads(timeline_item[1])

        if not jf2.get("reactions"):
            jf2["reactions"] = {}

        if not jf2["reactions"].get("replies"):
            jf2["reactions"]["replies"] = []

        if request.form.get("content"):
            jf2["reactions"]["replies"] = [{"content": request.form.get("content"), "url": reaction_url}]
        else:
            jf2["reactions"][reaction_type] = ""

        cursor.execute("UPDATE timeline SET jf2 = ? WHERE uid = ?", (json.dumps(jf2), uid))

        return {"type": "success"}, 200

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

def search_for_content():
    connection = sqlite3.connect("microsub.db")

    query = request.form.get("query")

    with connection:
        cursor = connection.cursor()

        result = cursor.execute("SELECT * FROM timeline WHERE jf2 LIKE ? ORDER BY date DESC;", (f"%{query}%", )).fetchall()

        items = [[json.loads(item[1]), item[3], item[5]] for item in result]

        items = [i[0] for i in items]

        return jsonify({"items": items}), 200

def preview():
    url = request.form.get("url")

    # get content type of url
    try:
        r = requests.head(url)
    except:
        return jsonify({"error": "invalid url"}), 400

    soup = BeautifulSoup(r.text, "lxml")

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
        parsed = mf2py.parse(r.text)

        h_card = None

        for item in parsed["items"]:
            if "type" in item and item["type"] == "h-card":
                h_card = item

        for item in parsed["items"]:
            if "type" in item and item["type"][0] == "h-feed":
                for entry in item["children"]:
                    if entry["type"][0] == "h-entry":
                        result = hfeed.process_hfeed(entry, h_card, "", url, "")

                        items_to_return.append(result)
            elif "type" in item and item["type"][0] == "h-entry":
                result = hfeed.process_hfeed(item, h_card, "", url, "")

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

    soup = BeautifulSoup(requests.get(url_to_check).text, "lxml")

    favicon = soup.find("link", rel="shortcut icon")

    if favicon:
        feed["icon"] = indieweb_utils.canonicalize_url(favicon.get("href"), url_domain, favicon.get("href"))

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

        cursor.execute("SELECT uid, channel FROM channels ORDER BY position DESC;")

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
            results = cursor.execute("SELECT * FROM following ORDER BY id DESC;").fetchall()
        else:
            results = cursor.execute("SELECT * FROM following WHERE channel = ? ORDER by id DESC;", (channel,)).fetchall()

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
            return jsonify({"error": f"You are already following this feed in the {request.form.get('channel')} channel."}), 400

        # get information from feed web page

        r = requests.get(url)

        title = url
        favicon = ""

        soup = BeautifulSoup(r.text, "lxml")

        if soup.find("title"):
            title = soup.find("title").text

        # get favicon

        home_page_request = requests.get(url.split("/")[0] + "//" + url.split("/")[2]).text
        home_page = BeautifulSoup(home_page_request, "lxml")

        favicon = home_page.find("link", rel="shortcut icon")

        if favicon:
            favicon = indieweb_utils.canonicalize_url(favicon.get("href"), url.split("/")[2], url)
        else:
            favicon = ""

        if favicon == "":
            favicon = home_page.find("link", rel="icon")

            if favicon:
                favicon = indieweb_utils.canonicalize_url(favicon.get("href"), url.split("/")[2], url)

        if favicon:
            try:
                r = requests.get(favicon)

                if r.status_code != 200:
                    favicon = ""
            except:
                favicon = ""

        if not favicon or favicon == "":
            favicon = "/static/gradient.png"

        # "" empty string is etag which will be populated in poll_feeds.py if available
        last_id = cursor.execute("SELECT MAX(id) FROM following").fetchone()

        if last_id and last_id [0] != None:
            last_id = last_id[0] + 1
        else:
            last_id = 1

        # set cadence to hourly by default
        cursor.execute("INSERT INTO following VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                request.form.get("channel"),
                url,
                "",
                favicon,
                title,
                last_id,
                0,
                0,
                "hourly",
            )
        )

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

    if request.form.getlist("entry[]"):
        for entry in request.form.getlist("entry[]"):
            with connection:
                cursor = connection.cursor()
                cursor.execute("UPDATE timeline SET hidden = 1 WHERE uid = ?", (entry, ))

        return {"type": "remove_entry"}

    else:
        with connection:
            cursor = connection.cursor()

            cursor.execute("UPDATE timeline SET hidden = 1 WHERE uid = ?", (request.form.get("entry"), ))

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