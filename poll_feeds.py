import sqlite3
import requests
from dates import find_poll_cadence
from feeds import hfeed, json_feed, xml_feed
import random
import string
import datetime
import json
import os
import mf2py
import feedparser
from time import mktime
import concurrent.futures

poll_cadences = []

# delete feed_items.json file so old records are not added to db again
if os.path.isfile("feed_items.json"):
    os.remove("feed_items.json")

def extract_feed_items(s, url, channel_uid, feed_id):
    session = requests.Session()
    session.max_redirects = 2

    try:
        r = session.head(url, allow_redirects=True, timeout=10)
    except:
        return

    # get content type of url
    if r.headers.get('content-type'):
        content_type = r.headers['content-type']
    else:
        content_type = ""

    print("polling " + url)

    if "xml" in content_type:
        feed = feedparser.parse(url)
        print("entries found: " + str(len(feed.entries)))

        etag = feed.get("etag", "")

        if etag != "" and etag == s[2]:
            print("{} has not changed since last poll, skipping".format(url))
            return

        last_modified = feed.get("modified_parsed", None)

        if last_modified and datetime.datetime.fromtimestamp(mktime(last_modified)) < datetime.datetime.now() - datetime.timedelta(hours=12):
            print("{} has not been modified in the last 12 hours, skipping".format(url))
            return

        dates = []

        for entry in feed.entries[:10]:
            result, published = xml_feed.process_xml_feed(entry, feed, url)

            ten_random_letters = ''.join(random.choice(string.ascii_lowercase) for _ in range(10))

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

            with open("feed_items.json", "a+") as file:
                file.write(json.dumps(record) + "\n")

        poll_cadence = find_poll_cadence(dates)

        poll_cadences.append((poll_cadence, url))

    elif "json" in content_type:
        feed = requests.get(url)

        if feed.status_code != 200:
            return

        # get etag header
        etag = feed.headers.get("etag", "")

        if etag != "" and etag == s[2]:
            print("{} has not changed since last poll, skipping".format(url))
            return

        feed = feed.json()

        dates = []

        for entry in feed.get("items", []):
            result, published = json_feed.process_json_feed(entry, feed)

            if result != None:
                ten_random_letters = ''.join(random.choice(string.ascii_lowercase) for _ in range(10))

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

                with open("feed_items.json", "a+") as file:
                    file.write(json.dumps(record) + "\n")

        poll_cadence = find_poll_cadence(dates)

        poll_cadences.append((poll_cadence, url))

    else:
        session = requests.Session()
        session.max_redirects = 2

        try:
            r = session.get(url, allow_redirects=True, timeout=10)
        except:
            return None

        mf2_raw = mf2py.parse(r.text)

        hcard = [item for item in mf2_raw['items'] if item['type'][0] == 'h-card']

        results = []

        for item in mf2_raw["items"]:
            if item.get("type") and item.get("type")[0] == "h-feed":
                print("entries found: " + str(len(item.get("children"))))
                if item.get("children") == None:
                    return results

                for child in item["children"][:5]:
                    hfeed.process_hfeed(child, hcard, channel_uid, url, feed_id)

def poll_feeds():
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        # don't poll feeds that have been blocked
        # see https://indieweb.org/Microsub-spec#Blocking

        # current hour
        current_hour = datetime.datetime.now().hour

        if current_hour == 0:
            cadence = "daily"
        else:
            cadence = "hourly"
        
        subscriptions = cursor.execute("SELECT url, channel, etag, id FROM following WHERE blocked = 0 AND poll_cadence = ?;",
            (cadence, )).fetchall()

        with concurrent.futures.ThreadPoolExecutor() as executor:
            channel_uids = []
            tasks = []

            for s in subscriptions:
                url = s[0]
                feed_id = s[3]

                # get channel uid
                try:
                    channel_uid = cursor.execute("SELECT uid FROM channels WHERE uid = ?;", (s[1],)).fetchone()[0]
                    channel_uids.append(channel_uid)
                except:
                    continue
            
                tasks.append(executor.submit(extract_feed_items, s, url, channel_uid, feed_id))

            for task in concurrent.futures.as_completed(tasks):
                try:
                    task.result()
                except Exception as e:
                    print(e)

    print("polled all subscriptions")

poll_feeds()

print("adding feed items to database")

with open("feed_items.json", "a+") as f:
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        for p in poll_cadences:
            cursor.execute("UPDATE following SET poll_cadence = ? WHERE url = ?;", (p[0], p[1]))

        last_id = cursor.execute("SELECT MAX(id) FROM timeline;").fetchone()

        if last_id[0] != None:
            last_id = last_id[0] + 1
        else:
            last_id = 0

        for line in f:
            record = json.loads(line)
            
            # check if url in db
            in_db = cursor.execute("SELECT * FROM timeline WHERE url = ?", (record["url"],)).fetchall()

            if len(in_db) > 0:
                continue

            cursor.execute("""INSERT INTO timeline VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                (record["channel_uid"],
                    record["result"],
                    record["published"],
                    record["unread"],
                    record["url"],
                    record["uid"],
                    record["hidden"],
                    record["feed_id"],
                    last_id
                ))

            last_id += 1

            # update following to add new etag so we can track modifications to a feed
            cursor.execute("UPDATE following SET etag = ? WHERE url = ?;", (record["etag"], record["feed_url"]))

if __name__ == "__main__":
    poll_feeds()