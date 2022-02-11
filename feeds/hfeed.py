import datetime
import json
import random
import string

import indieweb_utils
from bs4 import BeautifulSoup
from dateutil.parser import parse
from urllib.parse import urlparse as parse_url


def process_hfeed_author(
    jf2: dict, url: str, child: dict, hcard: dict, feed_title: str, feed_icon: str
) -> dict:
    domain_name = parse_url(url).netloc

    if hcard:
        jf2["author"] = {
            "type": "card",
            "name": hcard[0]["properties"]["name"][0],
            "url": indieweb_utils.canonicalize_url(
                hcard[0]["properties"]["url"][0],
                domain_name,
                child["properties"]["url"][0],
            ),
        }

        if hcard[0]["properties"].get("photo"):
            jf2["photo"] = indieweb_utils.canonicalize_url(
                hcard[0]["properties"]["photo"][0],
                domain_name,
                child["properties"]["url"][0],
            )

    elif child["properties"].get("author") is not None and isinstance(
        child["properties"].get("author"), dict
    ):
        if type(child["properties"].get("author")[0]["properties"]) == str:
            h_card = [{"properties": {"name": child["properties"].get("author")[0]}}]
        elif child["properties"].get("author")[0]["properties"].get("url"):
            h_card = indieweb_utils.discover_author(
                child["properties"].get("author")[0]["properties"].get("url")[0]
            )
        else:
            h_card = []

        if h_card and len(h_card) > 0:
            jf2["author"] = {
                "type": "card",
                "name": h_card["properties"]["name"][0],
                "url": indieweb_utils.canonicalize_url(
                    h_card["properties"]["url"][0],
                    domain_name,
                    child["properties"]["url"][0],
                ),
            }

            if h_card["properties"].get("photo"):
                jf2["photo"] = indieweb_utils.canonicalize_url(
                    h_card["properties"]["photo"][0],
                    domain_name,
                    child["properties"]["url"][0],
                )
    elif feed_title is not None:
        jf2["author"] = {
            "type": "card",
            "name": feed_title,
            "url": indieweb_utils.canonicalize_url(
                url, domain_name, child["properties"]["url"][0]
            ),
        }

        if feed_icon is not None:
            jf2["author"]["photo"] = feed_icon

    return jf2


def get_name_and_content(child: dict, jf2: dict, url: str) -> dict:
    if child["properties"].get("name"):
        jf2["title"] = child["properties"].get("name")[0]
    elif jf2.get("author") and jf2["author"]["name"]:
        jf2["title"] = f"Post by {jf2['author']['name']}"
    else:
        jf2["title"] = f"Post by {url.split('/')[2]}"

    if child["properties"].get("content"):
        jf2["content"] = {
            "html": child["properties"].get("content")[0]["html"],
            "text": BeautifulSoup(
                child["properties"].get("content")[0]["value"], "lxml"
            ).get_text(separator="\n"),
        }
    elif child["properties"].get("summary"):
        jf2["content"] = {
            "text": BeautifulSoup(
                child["properties"].get("summary")[0], "lxml"
            ).get_text(separator="\n"),
            "html": child["properties"].get("summary")[0],
        }

    return jf2


def process_hfeed(
    child, hcard, channel_uid, url, feed_id, feed_title=None, feed_icon=None
):
    parsed_url = parse_url(url)
    domain_name = parsed_url.netloc

    if not child.get("properties") or not child["properties"].get("url"):
        return {}

    jf2 = {
        "url": indieweb_utils.canonicalize_url(
            child["properties"]["url"][0],
            domain_name,
            child["properties"]["url"][0],
        ),
    }

    if child["properties"].get("content"):
        jf2["type"] = indieweb_utils.get_post_type(child)
    else:
        jf2["type"] = "article"

    jf2 = process_hfeed_author(jf2, url, child, hcard, feed_title, feed_icon)

    if child["properties"].get("photo"):
        jf2["photo"] = indieweb_utils.canonicalize_url(
            child["properties"].get("photo")[0],
            domain_name,
            child["properties"]["url"][0],
        )

    if child["properties"].get("video"):
        video_url = indieweb_utils.canonicalize_url(
            child["properties"].get("video")[0],
            domain_name,
            child["properties"]["url"][0],
        )
        jf2["video"] = [{"content_type": "", "url": video_url}]

    if child["properties"].get("category"):
        jf2["category"] = child["properties"].get("category")[0]

    jf2 = get_name_and_content(child, jf2, url)

    wm_properties = ["in-reply-to", "like-of", "bookmark-of", "repost-of"]

    for w in wm_properties:
        if child["properties"].get(w):
            jf2[w] = child["properties"].get(w)[0]

    if child.get("published"):
        parse_date = parse(child["published"][0])

        if parse_date:
            month_with_padded_zero = str(parse_date.month).zfill(2)
            day_with_padded_zero = str(parse_date.day).zfill(2)
            date = f"{parse_date.year}{month_with_padded_zero}{day_with_padded_zero}"
        else:
            month_with_padded_zero = str(datetime.datetime.now().month).zfill(2)
            day_with_padded_zero = str(datetime.datetime.now().day).zfill(2)
            date = f"{datetime.datetime.now().year}{month_with_padded_zero}{day_with_padded_zero}"
    else:
        date = datetime.datetime.now().strftime("%Y%m%d")

    ten_random_letters = "".join(
        random.choice(string.ascii_lowercase) for _ in range(10)
    )

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
