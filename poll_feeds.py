import sqlite3
import requests
from bs4 import BeautifulSoup
import random
import string
import mf2py
import datetime
import json
import feedparser
from dateutil.parser import parse
import microformats2
from time import mktime

def process_hfeed(url, cursor, channel_uid):
    r = requests.get(url)

    mf2_raw = mf2py.parse(r.text)

    hcard = [item for item in mf2_raw['items'] if item['type'][0] == 'h-card']

    for item in mf2_raw["items"]:
        if item.get("type") and item.get("type")[0] == "h-feed":
            for child in item["children"]:
                jf2 = microformats2.to_jf2(child)

                if hcard:
                    jf2["author"] = {
                        "type": "card",
                        "name": hcard[0]["properties"]["name"][0],
                        "url": hcard[0]["properties"]["url"][0]
                    }

                in_db = cursor.execute("SELECT * FROM timeline WHERE url = ?", (jf2["url"],)).fetchall()

                parse_date = parse(jf2["published"])

                if parse_date:
                    month_with_padded_zero = str(parse_date.month).zfill(2)
                    day_with_padded_zero = str(parse_date.day).zfill(2)
                    date = "{}{}{}".format(parse_date.year, month_with_padded_zero, day_with_padded_zero)
                else:
                    month_with_padded_zero = str(datetime.datetime.now().month).zfill(2)
                    day_with_padded_zero = str(datetime.datetime.now().day).zfill(2)
                    date = "{}{}{}".format(datetime.datetime.now().year, month_with_padded_zero, day_with_padded_zero)

                if len(in_db) > 0:
                    continue

                ten_random_letters = ''.join(random.choice(string.ascii_lowercase) for _ in range(10))

                cursor.execute("INSERT INTO timeline VALUES (?, ?, ?, ?, ?, ?, ?)", (channel_uid, json.dumps(jf2), date, "unread", jf2["url"], ten_random_letters, 0, ))

def process_xml_feed(entry, feed, url, cursor, channel_uid):
    if entry.get("author"):
        author = {
            "type": "card",
            "name": entry.author,
            "url": entry.author_detail,
            "photo": "https://" + url.replace("https://", "").replace("http://", "").split("/")[0] + "/favicon.ico"
        }
    elif feed.get("author"):
        author = {
            "type": "card",
            "name": feed.feed.author,
            "url": feed.feed.author_detail,
            "photo": "https://" + url.replace("https://", "").replace("http://", "").split("/")[0] + "/favicon.ico"
        }
    else:
        author = {
            "type": "card",
            "name": feed.feed.get("title"),
            "url": feed.feed.get("link"),
            "photo": "https://" + url.replace("https://", "").replace("http://", "").split("/")[0] + "/favicon.ico"
        }

    if entry.get("content"):
        soup = BeautifulSoup(entry.content[0].value, "html.parser")
        content = {
            "text":soup.get_text(),
            "html": entry.content[0].value
        }
    elif entry.get("title") and entry.get("link"):
        # get feed author
        content = {
            "text": entry.title,
            "html": "<a href='" + entry.link + "'>" + entry.title + "</a>"
        }
    elif entry.get("title") and not entry.get("link"):
        # get feed author
        content = {
            "text": entry.title,
            "html": entry.title,
        }
    else:
        content = {}

    print(entry)

    if entry.get("published"):
        month_with_padded_zero = str(entry.published_parsed.tm_mon).zfill(2)
        day_with_padded_zero = str(entry.published_parsed.tm_mday).zfill(2)
        hour_minute_second = str(entry.published_parsed.tm_hour).zfill(2) + ":" + str(entry.published_parsed.tm_min).zfill(2) + ":" + str(entry.published_parsed.tm_sec).zfill(2)
        published = "{}{}{}T{}".format(entry.published_parsed.tm_year, month_with_padded_zero, day_with_padded_zero, hour_minute_second)
    elif entry.get("updated"):
        month_with_padded_zero = str(entry.updated_parsed.tm_mon).zfill(2)
        day_with_padded_zero = str(entry.updated_parsed.tm_mday).zfill(2)
        hour_minute_second = str(entry.updated_parsed.tm_hour).zfill(2) + ":" + str(entry.updated_parsed.tm_min).zfill(2) + ":" + str(entry.updated_parsed.tm_sec).zfill(2)
        published = "{}{}{}T{}".format(entry.updated_parsed.tm_year, month_with_padded_zero, day_with_padded_zero, hour_minute_second)
    else:
        month_with_padded_zero = str(datetime.datetime.now().month).zfill(2)
        day_with_padded_zero = str(datetime.datetime.now().day).zfill(2)
        hour_minute_second = str(datetime.datetime.now().hour).zfill(2) + ":" + str(datetime.datetime.now().minute).zfill(2) + ":" + str(datetime.datetime.now().second).zfill(2)
        published = "{}{}{}T{}".format(datetime.datetime.now().year, month_with_padded_zero, day_with_padded_zero, hour_minute_second)

    result = {
        "type": "entry",
        "author": author,
        "published": published,
        "content": content,
        "post-type": "entry",
        "name": entry.title,
    }

    if entry.get("media_content") and len(entry.get("media_content")) > 0 and entry.get("media_content")[0].get("url") and entry.get("media_content")[0].get("type"):
        result["video"] = entry.media_content[0].get("url")

    published = published.split("T")[0]

    return result, published

def poll_feeds():
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        subscriptions = cursor.execute("SELECT url, channel, etag FROM following;").fetchall()

        for s in subscriptions:
            url = s[0]

            print(url)

            url = "https://rubenerd.com/feed/"

            # get channel uid
            try:
                channel_uid = cursor.execute("SELECT uid FROM channels WHERE uid = ?;", (s[1],)).fetchone()[0]
            except:
                continue

            # get content type of url
            try:
                r = requests.head(url)
            except:
                continue
            if r.headers.get('content-type'):
                content_type = r.headers['content-type']
            else:
                content_type = ""

            if "xml" in content_type or ".xml" in url:
                feed = feedparser.parse(url)

                etag = feed.get("etag", "")

                if etag == s[2]:
                    print("{} has not changed since last poll, skipping".format(url))
                    continue

                last_modified = feed.get("modified_parsed", None)

                if last_modified and datetime.datetime.fromtimestamp(mktime(last_modified)) < datetime.datetime.now() - datetime.timedelta(hours=12):
                    print("{} has not been modified in the last 12 hours, skipping".format(url))
                    continue

                # update following to add new etag so we can track modifications to a feed
                cursor.execute("UPDATE following SET etag = ? WHERE url = ?;", (etag, url))

                for entry in feed.entries:
                    result, published = process_xml_feed(entry, feed, url, cursor, channel_uid)

                    if entry.get("link"):
                        result["url"] = entry.link

                        # check if url in db
                        in_db = cursor.execute("SELECT * FROM timeline WHERE url = ?", (result["url"],)).fetchall()

                        if len(in_db) > 0:
                            continue
                    else:
                        continue

                    ten_random_letters = ''.join(random.choice(string.ascii_lowercase) for _ in range(10))

                    cursor.execute("INSERT INTO timeline VALUES (?, ?, ?, ?, ?, ?, ?)", (channel_uid, json.dumps(result), published, "unread", result["url"], ten_random_letters, 0, ))
            else:
                process_hfeed(url, cursor, channel_uid)

    print("polled all subscriptions")

poll_feeds()