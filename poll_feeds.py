from flask import Flask, request, abort, jsonify, send_from_directory
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

def flatten_properties(items, is_outer=False):
    if isinstance(items, list):
        if len(items) < 1:
            return {}

        if len(items) == 1:
            item = items[0]
            if isinstance(item, dict):
                if 'type' in item:
                    props = {
                        'type': item.get('type', ['-'])[0].split('-')[1:][0]
                    }

                    properties = item.get("properties", {})
                    for prop in properties:
                        props[prop] = flatten_properties(properties[prop])

                    children = item.get('children', [])
                    if children:
                        if len(children) == 1:
                            props['children'] = [flatten_properties(children)]
                        else:
                            props['children'] = flatten_properties(children)
                    return props
                elif 'value' in item:
                    return item['value']
                else:
                    return ''
            else:
                return item
        elif is_outer:
            return {
                'children': [flatten_properties([child]) for child in items]
            }
        else:
            return [flatten_properties([child]) for child in items]
    else:
        return items


def to_jf2(mf2):
    jf2 = flatten_properties([mf2], is_outer=True)
    return jf2

def poll_feeds():
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        subscriptions = cursor.execute("SELECT url, channel FROM following;").fetchall()

        for s in subscriptions:
            url = s[0]

            # get channel uid
            try:
                channel_uid = cursor.execute("SELECT uid FROM channels WHERE uid = ?;", (s[1],)).fetchone()[0]
            except:
                continue

            print(url)

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

                for entry in feed.entries:
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

                    if entry.get("content") and "youtube.com" not in url:
                        soup = BeautifulSoup(entry.content[0].value, "html.parser")
                        content = {
                            "text":soup.get_text(),
                            "html": entry.content[0].value
                        }
                    elif entry.get("description") and "youtube.com" not in url:
                        soup = BeautifulSoup(entry.description, "html.parser")
                        content = {
                            "text":soup.get_text(),
                            "html": entry.description
                        }
                    elif entry.get("content") and "youtube.com" in url:
                        soup = BeautifulSoup(entry.description, "html.parser")
                        # get yt:videoid
                        youtube_videoid = soup.find("yt:videoid")
                        title = soup.find("title")
                        content = {
                            "text": soup.get_text(),
                            "html": "<iframe src='{}'></iframe><p>{}</p>".format(youtube_videoid, title)
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
                        "content": content
                    }

                    published = published.split("T")[0]

                    if entry.get("link"):
                        result["url"] = entry.link

                        # check if url in db
                        in_db = cursor.execute("SELECT * FROM timeline WHERE url = ?", (result["url"],)).fetchall()

                        if len(in_db) > 0:
                            continue
                    else:
                        continue

                    ten_random_letters = ''.join(random.choice(string.ascii_lowercase) for _ in range(10))

                    cursor.execute("INSERT INTO timeline VALUES (?, ?, ?, ?, ?, ?)", (channel_uid, json.dumps(result), published, "unread", result["url"], ten_random_letters, ))
            else:
                r = requests.get(url)

                mf2_raw = mf2py.parse(r.text)

                hcard = [item for item in mf2_raw['items'] if item['type'][0] == 'h-card']

                for item in mf2_raw["items"]:
                    if item.get("type") and item.get("type")[0] == "h-feed":
                        for child in item["children"]:
                            jf2 = to_jf2(child)

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

                            cursor.execute("INSERT INTO timeline VALUES (?, ?, ?, ?, ?, ?)", (channel_uid, json.dumps(jf2), date, "unread", jf2["url"], ten_random_letters, ))

    print("polled all subscriptions")

poll_feeds()