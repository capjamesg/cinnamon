import requests
import random
import string
import mf2py
import datetime
import json
from dateutil.parser import parse
from bs4 import BeautifulSoup
from .canonicalize_url import canonicalize_url as canonicalize_url

def process_hfeed(url, cursor=None, channel_uid=None, add_to_db=True, feed_id=None):
    print('s')
    session = requests.Session()
    session.max_redirects = 2

    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8,application/json",
    }

    try:
        r = session.get(url, allow_redirects=True, timeout=10, headers=headers)
    except:
        return None

    mf2_raw = mf2py.parse(r.text)

    hcard = [item for item in mf2_raw['items'] if item['type'][0] == 'h-card']

    results = []

    is_list_of_h_entries = [item for item in mf2_raw['items'] if item['type'][0] == 'h-entry']
    is_mf2_h_feed = [item for item in mf2_raw['items'] if item['type'][0] == 'h-feed']

    if is_list_of_h_entries:
        iterate_object = is_list_of_h_entries
    else:
        iterate_object = is_mf2_h_feed

    for item in iterate_object:
        print(item)
        print("entries found: " + str(len(item.get("children"))))

        if item.get("children") == None:
            return results

        for child in item["children"][:5]:
            jf2 = {
                "type": "entry",
                "url": canonicalize_url(child["properties"]["url"][0], url.split("/")[2], child["properties"]["url"][0]),
            }

            # check if in timeline before proceeding
            # we don't want to add duplicate records to the timeline
            # without this precaution, any post without a published date will resurface at the top of every feed

            if cursor != None:
                in_timeline = cursor.execute("SELECT * FROM timeline WHERE url = ?", (jf2["url"],)).fetchall()

                if len(in_timeline) > 0:
                    continue

            if hcard:
                jf2["author"] = {
                    "type": "card",
                    "name": hcard[0]["properties"]["name"][0],
                    "url": canonicalize_url(hcard[0]["properties"]["url"][0], url.split("/")[2], child["properties"]["url"][0]),
                }
                
                if hcard[0]["properties"].get("photo"):
                    jf2["photo"] = canonicalize_url(hcard[0]["properties"]["photo"][0], url.split("/")[2], child["properties"]["url"][0])

            if not child.get("properties"):
                continue

            if child["properties"].get("photo"):
                jf2["photo"] = [canonicalize_url(child["properties"].get("photo")[0], url.split("/")[2], child["properties"]["url"][0])]

            if child["properties"].get("category"):
                jf2["category"] = child["properties"].get("category")

            if child["properties"].get("name"):
                jf2["name"] = child["properties"].get("name")[0]

            if child["properties"].get("summary"):
                jf2["content"] = {
                    "text": BeautifulSoup(child["properties"].get("summary")[0], "html.parser").get_text(),
                    "html": child["properties"].get("summary")[0]
                }
            elif child["properties"].get("content") and child["properties"].get("content")[0].get("html"):
                jf2["content"] = {
                    "text": BeautifulSoup(child["properties"].get("content")[0]["html"], "html.parser").get_text(),
                    "html": child["properties"].get("content")[0]["html"]
                }
            elif child["properties"].get("content") and type(child["properties"].get("content")[0]) == str:
                jf2["content"] = {
                    "text": BeautifulSoup(child["properties"].get("content")[0], "html.parser").get_text(),
                    "html": child["properties"].get("content")[0]
                }

            if child["properties"].get("video"):
                jf2["video"] = [{"content_type": "video/mp3", "url": canonicalize_url(child["properties"].get("video")[0], url.split("/")[2], child["properties"]["url"][0])}]

            wm_properties = ["in-reply-to", "like-of", "bookmark-of", "repost-of"]

            for w in wm_properties:
                if child["properties"].get(w):
                    jf2[w] = child["properties"].get(w)[0]

            if child.get("published"):
                parse_date = parse(child["published"][0])

                if parse_date:
                    month_with_padded_zero = str(parse_date.month).zfill(2)
                    day_with_padded_zero = str(parse_date.day).zfill(2)
                    date = "{}{}{}".format(parse_date.year, month_with_padded_zero, day_with_padded_zero)
                else:
                    month_with_padded_zero = str(datetime.datetime.now().month).zfill(2)
                    day_with_padded_zero = str(datetime.datetime.now().day).zfill(2)
                    date = "{}{}{}".format(datetime.datetime.now().year, month_with_padded_zero, day_with_padded_zero)
            else:
                date = datetime.datetime.now().strftime("%Y%m%d")

            ten_random_letters = ''.join(random.choice(string.ascii_lowercase) for _ in range(10))

            jf2["published"] = date

            if add_to_db == True:
                feed_id = cursor.execute("SELECT id FROM timeline WHERE url = ?", (url,)).fetchone()

                if not feed_id:
                    continue

                last_id = cursor.execute("SELECT MAX(id) FROM timeline;").fetchone()

                if last_id[0] != None:
                    last_id = last_id[0] + 1
                else:
                    last_id = 0
                
                cursor.execute("INSERT INTO timeline VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (channel_uid, json.dumps(jf2), date, "unread", jf2["url"], ten_random_letters, 0, feed_id, last_id, ))
            
            results.append(jf2)

    return results