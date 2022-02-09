import feedparser
import indieweb_utils
import mf2py
import requests
from bs4 import BeautifulSoup
from flask import jsonify, request

from feeds import hfeed, json_feed, xml_feed


def process_h_feed_preview(
    r: requests.Request, items_to_return: list, url: str
) -> list:
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

    return items_to_return, content_type


def get_preview_items(content_type: str, url: str, r: requests.Request) -> list:
    items_to_return = []

    if "xml" in content_type or ".xml" in url:
        feed = feedparser.parse(url)

        for entry in feed.entries:
            result, _ = xml_feed.process_xml_feed(entry, feed, url)

            items_to_return.append(result)
    elif "json" in content_type or url.endswith(".json"):
        try:
            feed = requests.get(url, timeout=5).json()
        except requests.exceptions.RequestException:
            return jsonify({"error": "invalid url"}), 400

        for entry in feed.get("items", []):
            result, _ = json_feed.process_json_feed(entry, feed)

            items_to_return.append(result)
    else:
        items_to_return, content_type = process_h_feed_preview(r, items_to_return, url)

    return items_to_return, content_type


def preview(request: request) -> dict:
    url = request.form.get("url")

    # get content type of url
    try:
        r = requests.head(url)
    except requests.exceptions.RequestException:
        return jsonify({"error": "invalid url"}), 400

    soup = BeautifulSoup(r.text, "lxml")

    if r.headers.get("content-type"):
        content_type = r.headers["content-type"]
    else:
        content_type = ""

    items_to_return, content_type = get_preview_items(soup, url, content_type)

    feed = {"url": url, "feed_type": content_type}

    # get homepage favicon
    url_domain = url.split("/")[2]
    url_protocol = url.split("/")[0]

    url_to_check = url_protocol + "//" + url_domain

    soup = BeautifulSoup(requests.get(url_to_check).text, "lxml")

    favicon = soup.find("link", rel="shortcut icon")

    if favicon:
        feed["icon"] = indieweb_utils.canonicalize_url(
            favicon.get("href"), url_domain, favicon.get("href")
        )

    if soup.find("title"):
        feed["title"] = soup.find("title").text

    result = {"feed": feed, "items": items_to_return}

    return jsonify(result), 200
