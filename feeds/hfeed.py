import random
import string
import datetime
import json
from dateutil.parser import parse
from bs4 import BeautifulSoup
from .canonicalize_url import canonicalize_url as canonicalize_url
from .authorship import discover_author as discover_author
from . import post_type_discovery as post_type_discovery

def process_hfeed(child, hcard, channel_uid, url, feed_id):
    jf2 = {
        "url": canonicalize_url(child["properties"]["url"][0], url.split("/")[2], child["properties"]["url"][0]),
    }

    jf2["type"] = post_type_discovery.get_post_type(child)

    if hcard:
        jf2["author"] = {
            "type": "card",
            "name": hcard[0]["properties"]["name"][0],
            "url": canonicalize_url(hcard[0]["properties"]["url"][0], url.split("/")[2], child["properties"]["url"][0]),
        }
        
        if hcard[0]["properties"].get("photo"):
            jf2["photo"] = canonicalize_url(hcard[0]["properties"]["photo"][0], url.split("/")[2], child["properties"]["url"][0])
    elif child["properties"].get("author"):
        if type(child["properties"].get("author")[0]) == str:
            h_card = discover_author(child["properties"].get("author")[0])
        elif child["properties"].get("author")[0].get("url"):
            h_card = discover_author(child["properties"].get("author")[0].get("url"))
        else:
            h_card = []

        if h_card != []:
            jf2["author"] = {
                "type": "card",
                "name": h_card[0]["properties"]["name"][0],
                "url": canonicalize_url(h_card[0]["properties"]["url"][0], url.split("/")[2], child["properties"]["url"][0]),
            }

            if h_card[0]["properties"].get("photo"):
                jf2["photo"] = canonicalize_url(h_card[0]["properties"]["photo"][0], url.split("/")[2], child["properties"]["url"][0])

    if not child.get("properties"):
        return

    if child["properties"].get("photo"):
        jf2["photo"] = canonicalize_url(child["properties"].get("photo")[0], url.split("/")[2], child["properties"]["url"][0]) 

    if child["properties"].get("video"):
        video_url = canonicalize_url(child["properties"].get("video")[0], url.split("/")[2], child["properties"]["url"][0]) 
        jf2["video"] = [{"content_type": "", "url": video_url}]

    if child["properties"].get("category"):
        jf2["category"] = child["properties"].get("category")[0]

    if child["properties"].get("name"):
        jf2["name"] = child["properties"].get("name")[0]
    elif jf2.get("author") and jf2["author"]["name"]:
        jf2["name"] = "Post by {}".format(jf2["author"]["name"])
    else:
        jf2["name"] = "Post by {}".format(url.split("/")[2])

    if child["properties"].get("content"):
        jf2["content"] = child["properties"].get("content")[0]
    elif child["properties"].get("summary"):
        jf2["content"] = {
            "text": BeautifulSoup(child["properties"].get("summary")[0], "lxml").get_text(separator="\n"),
            "html": child["properties"].get("summary")[0]
        }

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

    record = {
        "channel_uid": channel_uid,
        "result": json.dumps(jf2),
        "published": date,
        "unread": "unread",
        "url": jf2["url"],
        "uid": ten_random_letters,
        "hidden": 0,
        "feed_id": feed_id,
        "etag": "",
        "feed_url": url,
    }

    with open("feed_items.json", "a+") as file:
        file.write(json.dumps(record) + "\n")

    return jf2