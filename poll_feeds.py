import sqlite3
import requests
from dates import find_poll_cadence
from config import PROJECT_DIRECTORY, WEBHOOK_TOKEN, WEBHOOK_CHANNEL
from feeds import hfeed, json_feed, xml_feed
import random
import string
import datetime
import json
import os
import mf2py
import feedparser
import concurrent.futures
import logging

logging.basicConfig(
	level=logging.DEBUG, 
	filename="logs/{}.log".format(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
	datefmt='%Y-%m-%d %H:%M:%S'
)

print("Printing logs to logs/{}.log".format(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

poll_cadences = []

# delete feed_items.json file so old records are not added to db again
if os.path.isfile(PROJECT_DIRECTORY.rstrip("/") + "/feed_items.json"):
    os.remove(PROJECT_DIRECTORY.rstrip("/") + "/feed_items.json")

def validate_entry_count(entries, feed_url, feed_id):
    length = len(entries)

    if length < 3:
        published = datetime.datetime.now().isoformat()

        jf2 = {
            "type": "entry",
            "content": {
                "text": "{} feed does not have any posts. Please check that the feed URL is working correctly.".format(feed_url),
                "html": "{} feed does not have any posts. Please check that the feed URL is working correctly.".format(feed_url),
            },
            "published": published,
            "url": "https://webmention.jamesg.blog",
            "wm-property": "article"
        }

        ten_random_letters = ''.join(random.choice(string.ascii_lowercase) for _ in range(10))

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

    try:
        r = session.head(url, allow_redirects=True, timeout=10)
    except:
        return

    print(url)

    # get content type of url
    if r.headers.get('content-type'):
        content_type = r.headers['content-type']
    else:
        content_type = ""

    # # get etag of url
    if r.headers.get('etag'):
        etag = r.headers['etag']
    else:
        etag = ""

    if etag != "" and etag == s[2]:
        logging.debug("{} has not changed since last poll, skipping".format(url))
        return None

    # get last modified date of url
    if r.headers.get('last-modified'):
        last_modified = r.headers['last-modified']
    else:
        last_modified = ""

    if last_modified != "" and datetime.datetime.strptime(last_modified, '%a, %d %b %Y %H:%M:%S %Z') < datetime.datetime.now() - datetime.timedelta(hours=12):
        logging.debug("{} has not been modified in the last 12 hours, skipping".format(url))
        return None

    logging.debug("polling " + url)

    if "xml" in content_type or content_type == "binary/octet-stream":
        feed = feedparser.parse(url)
        print("entries found: " + str(len(feed.entries)))
        logging.debug("entries found: " + str(len(feed.entries)))

        validate_entry_count(feed.entries, url, feed_id)

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

            with open(PROJECT_DIRECTORY + "/feed_items.json", "a+") as file:
                file.write(json.dumps(record) + "\n")

        poll_cadence = find_poll_cadence(dates)

        poll_cadences.append((poll_cadence, url))

    elif "application/json" in content_type:
        try:
            feed = requests.get(url)
        except:
            return

        if feed.status_code != 200:
            return

        # get etag header
        etag = feed.headers.get("etag", "")

        if etag != "" and etag == s[2]:
            logging.debug("{} has not changed since last poll, skipping".format(url))
            return

        feed = feed.json()

        dates = []

        print("entries found: " + str(len(feed.get("items", []))))

        validate_entry_count(feed.get("items", []), url, feed_id)

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

        poll_cadence = find_poll_cadence(dates)

        poll_cadences.append((poll_cadence, url))

    else:
        session = requests.Session()
        session.max_redirects = 2

        accept_headers = {
            "Accept": "text/html",
        }

        try:
            r = session.get(url, allow_redirects=True, timeout=10, headers=accept_headers)
        except:
            return None

        mf2_raw = mf2py.parse(r.text)

        hcard = [item for item in mf2_raw['items'] if item['type'][0] == 'h-card']

        h_feed = [item for item in mf2_raw['items'] if item['type'] and item['type'][0] == 'h-feed']

        if len(h_feed) > 0:
            feed = h_feed[0]["children"]
        else:
            # get all non h-card items
            # this will let the program parse non h-entry feeds such as h-event feeds
            feed = [item for item in mf2_raw['items'] if item['type'] and item['type'][0] != 'h-card']

            if len(feed) == 0:
                return None

        print("entries found: " + str(len(feed)))

        validate_entry_count(feed, url, feed_id)

        for child in feed[:5]:
            result = hfeed.process_hfeed(child, hcard, channel_uid, url, feed_id)

            ten_random_letters = ''.join(random.choice(string.ascii_lowercase) for _ in range(10))

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

def poll_feeds():
    connection = sqlite3.connect(PROJECT_DIRECTORY.rstrip("/") + "/microsub.db")

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

            # subscriptions = [["https://calumryan.com/feeds/atom", "", "", ""]]

            for s in subscriptions:
                if s[0] != None:
                    url = s[0]
                    feed_id = s[3]

                    # get channel uid
                    try:
                        channel_uid = cursor.execute("SELECT uid FROM channels WHERE uid = ?;", (s[1],)).fetchone()
                        if channel_uid:
                            channel_uids.append(channel_uid[0])
                    except Exception as e:
                        print(e)
                        logging.debug("channel uid not found")
                        # continue
            
                tasks.append(executor.submit(extract_feed_items, s, url, channel_uid, feed_id))

            for task in concurrent.futures.as_completed(tasks):
                try:
                    task.result()
                except Exception as e:
                    print(e)

    logging.debug("polled all subscriptions")

def add_feed_items_to_database():
    logging.debug("adding feed items to database")

    with open(PROJECT_DIRECTORY.rstrip("/") + "/feed_items.json", "r") as f:
        connection = sqlite3.connect(PROJECT_DIRECTORY.rstrip("/") + "/microsub.db")

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

                logging.debug("Adding: " + record["url"])
                
                # check if url in db
                in_db = cursor.execute("SELECT * FROM timeline WHERE url = ?", (record["url"],)).fetchall()

                if len(in_db) > 0:
                    continue

                if type(record["channel_uid"]) == list:
                    record["channel_uid"] = record["channel_uid"][0]

                if record["channel_uid"] == WEBHOOK_CHANNEL and WEBHOOK_TOKEN != "":
                    record_jf2 = json.loads(record["result"])
                    # send notification to calibot that a new post has been found
                    data = {
                        "message": "{} ({}) has been published in the {} channel.".format(
                            record_jf2["title"],
                            record_jf2["url"],
                            record["channel_uid"]
                        )
                    }

                    headers = {
                        "Authorization": "Bearer " + WEBHOOK_TOKEN
                    }

                    requests.post("https://cali.jamesg.blog/webhook", data=data, headers=headers)

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
    add_feed_items_to_database()

    # remove feed items file after all items have been added to the database
    os.remove(PROJECT_DIRECTORY + "/feed_items.json")