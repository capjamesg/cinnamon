import sqlite3
import requests
from feeds import hfeed, json_feed, xml_feed
import random
import string
import datetime
import json
import feedparser
from time import mktime

def poll_feeds():
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        # don't poll feeds that have been blocked
        # see https://indieweb.org/Microsub-spec#Blocking
        
        subscriptions = cursor.execute("SELECT url, channel, etag, id FROM following WHERE blocked = 0;").fetchall()

        subscriptions = [["https://rhiaro.co.uk", "coffeetsw", "", "s"]]

        for s in subscriptions:
            url = s[0]
            feed_id = s[3]

            # get channel uid
            try:
                channel_uid = cursor.execute("SELECT uid FROM channels WHERE uid = ?;", (s[1],)).fetchone()[0]
            except:
                continue

            session = requests.Session()
            session.max_redirects = 2

            headers = {
                "Accept": "application/json, application/xml, text/html",
            }

            try:
                r = session.head(url, allow_redirects=True, timeout=10, headers=headers)
            except:
                continue

            # get content type of url
            if r.headers.get('content-type'):
                content_type = r.headers['content-type']
            else:
                content_type = ""

            print("polling " + url)

            if "xml" in content_type or url.endswith(".xml") or url.endswith(".atom") or url.endswith(".rss"):
                feed = feedparser.parse(url)
                print("entries found: " + str(len(feed.entries)))

                etag = feed.get("etag", "")

                if etag != "" and etag == s[2]:
                    print("{} has not changed since last poll, skipping".format(url))
                    continue

                last_modified = feed.get("modified_parsed", None)

                if last_modified and datetime.datetime.fromtimestamp(mktime(last_modified)) < datetime.datetime.now() - datetime.timedelta(hours=12):
                    print("{} has not been modified in the last 12 hours, skipping".format(url))
                    continue

                # update following to add new etag so we can track modifications to a feed
                cursor.execute("UPDATE following SET etag = ? WHERE url = ?;", (etag, url))

                for entry in feed.entries[:10]:
                    result, published = xml_feed.process_xml_feed(entry, feed, url)

                    if result != None and entry.get("link"):
                        result["url"] = entry.link

                        # check if url in db
                        in_db = cursor.execute("SELECT * FROM timeline WHERE url = ?", (result["url"],)).fetchall()

                        if len(in_db) > 0:
                            continue
                    else:
                        continue

                    ten_random_letters = ''.join(random.choice(string.ascii_lowercase) for _ in range(10))

                    last_id = cursor.execute("SELECT MAX(id) FROM timeline;").fetchone()

                    if last_id[0] != None:
                        last_id = last_id[0] + 1
                    else:
                        last_id = 0

                    cursor.execute("INSERT INTO timeline VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (channel_uid, json.dumps(result), published, "unread", result["url"], ten_random_letters, 0, feed_id, last_id, ))
            elif "json" in content_type or url.endswith(".json"):
                feed = requests.get(url)

                if feed.status_code != 200:
                    continue

                # get etag header
                etag = feed.headers.get("etag", "")

                if etag != "" and etag == s[2]:
                    print("{} has not changed since last poll, skipping".format(url))
                    continue

                feed = feed.json()

                # update following to add new etag so we can track modifications to a feed
                cursor.execute("UPDATE following SET etag = ? WHERE url = ?;", (etag, url))

                for entry in feed.get("items", []):
                    result, published = json_feed.process_json_feed(entry, feed)

                    if result != None:
                        # check if url in db
                        in_db = cursor.execute("SELECT * FROM timeline WHERE url = ?", (result["url"],)).fetchall()

                        if len(in_db) > 0:
                            continue

                        ten_random_letters = ''.join(random.choice(string.ascii_lowercase) for _ in range(10))

                        last_id = cursor.execute("SELECT MAX(id) FROM timeline;").fetchone()

                        if last_id[0] != None:
                            last_id = last_id[0] + 1
                        else:
                            last_id = 0

                        cursor.execute("INSERT INTO timeline VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (channel_uid, json.dumps(result), published, "unread", result["url"], ten_random_letters, 0, s[3], last_id, ))
            else:
                hfeed.process_hfeed(url, cursor, channel_uid, feed_id)

    print("polled all subscriptions")

if __name__ == "__main__":
    poll_feeds()