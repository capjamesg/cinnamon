import datetime
import json
import sqlite3

import indieweb_utils
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse as parse_url
from .clean import clean_html_from_entry


def save_read_later_to_database(record: dict) -> None:
    database = sqlite3.connect("microsub.db")

    with database:
        cursor = database.cursor()

        last_id = cursor.execute("SELECT MAX(id) FROM timeline;").fetchone()

        if last_id[0] is not None:
            last_id = last_id[0] + 1
        else:
            last_id = 0

        last_id += 1

        feed_id = cursor.execute(
            "SELECT id FROM following WHERE channel = 'read-later';"
        ).fetchone()[0]

        cursor.execute(
            """INSERT INTO timeline VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);""",
            (
                "read-later",
                json.dumps(record["result"]),
                record["result"]["published"],
                0,
                record["result"]["url"],
                record["result"]["url"],
                0,
                feed_id,
                last_id,
            ),
        )


def get_read_later_photo(record: dict, soup: BeautifulSoup, url: str) -> dict:
    # we will remove header and nav tags so that we are more likely to find a "featured image" for the post
    # remove <header> tags
    parsed_url = parse_url(url)

    for header in soup.find_all("header"):
        header.decompose()

    # remove <nav> tags
    for nav in soup.find_all("nav"):
        nav.decompose()

    # get all images
    all_images = soup.find_all("img")

    if all_images and len(all_images) > 0 and all_images[0].get("src"):
        all_images = [i for i in all_images if "u-photo" not in i.get("class", [])]

    if len(all_images) > 0:
        record["photo"] = indieweb_utils.canonicalize_url(
            all_images[0]["src"], parsed_url.netloc, all_images[0]["src"]
        )


def read_later(url: str) -> None:
    """
    Processes a URL and saves it to the Microsub timeline.

    :param url: The URL to process.
    :type url: str
    :return: None
    :rtype: None
    """
    parsed_url = parse_url(url)

    try:
        r = requests.get(url, timeout=5, allow_redirects=True)
    except requests.exceptions.RequestException:
        return None

    if r.status_code != 200:
        return None

    soup = BeautifulSoup(r.text, "lxml")

    content = ""

    if soup.find(".h-entry"):
        content = soup.find(".h-entry").get_text(separator="\n")
    elif soup.find("article"):
        content = soup.find("article").get_text(separator="\n")
    else:
        content = clean_html_from_entry(soup)

    date = datetime.datetime.now().strftime("%Y%m%d")

    record = {
        "result": {
            "url": url,
            "type": "summary",
            "content": {"text": content, "html": content},
            "title": soup.title.text,
            "published": date,
        }
    }

    # get og_image tag
    og_image = soup.find("meta", property="og:image")

    if og_image:
        record["photo"] = indieweb_utils.canonicalize_url(
            og_image["content"], parsed_url.netloc, og_image["content"]
        )

    if not record.get("photo"):
        record = get_read_later_photo(record, soup, url)

    save_read_later_to_database(record)
