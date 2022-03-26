import datetime

import indieweb_utils
from bs4 import BeautifulSoup
from dateutil.parser import parse
from urllib.parse import urlparse as parse_url
from .clean import clean_html_from_entry


def process_json_feed_author(item: dict, feed: dict, result: dict) -> dict:
    domain_name = parse_url(item.get("url")).netloc

    if feed.get("author") and not item.get("author"):
        result["author"] = {"type": "card", "name": feed.get("author").get("name")}
        if feed.get("home_page_url"):
            result["author"]["url"] = indieweb_utils.canonicalize_url(
                feed.get("home_page_url"),
                domain_name,
                feed.get("home_page_url"),
            )
        else:
            result["author"]["url"] = indieweb_utils.canonicalize_url(
                feed.get("feed_url"),
                domain_name,
                feed.get("feed_url"),
            )
    elif item.get("author") is not None and item["author"].get("url"):
        author_url_domain = parse_url(item["author"].get("url")).netloc

        result["author"] = {
            "type": "card",
            "name": item.get("author").get("name"),
            "url": indieweb_utils.canonicalize_url(
                item["author"].get("url"),
                author_url_domain,
                item["author"].get("url"),
            ),
        }

        if item["author"].get("avatar"):
            result["author"]["photo"] = item["author"].get("avatar")
    else:
        author_url_domain = parse_url(item["author"].get("url")).netloc

        result["author"] = {
            "type": "card",
            "name": feed.get("title"),
            "url": indieweb_utils.canonicalize_url(
                item["author"].get("url"),
                author_url_domain,
                item["author"].get("url"),
            ),
        }

    return result


def process_attachments(item: dict, result: dict) -> dict:
    for i in item.get("attachments"):
        if "audio" in i.get("mime_type"):
            result["audio"] = [
                {"content_type": i.get("mime_type"), "url": i.get("url")}
            ]
            break
        elif "video" in i.get("mime_type"):
            result["video"] = [
                {"content_type": i.get("mime_type"), "url": i.get("url")}
            ]
            break

    return result


def process_json_feed(item: dict, feed: dict) -> dict:
    parsed_url = parse_url(item.get("url"))
    result = {
        "type": "entry",
        "url": indieweb_utils.canonicalize_url(
            item.get("url"), parsed_url.netloc, item.get("url")
        ),
    }

    if item.get("image"):
        result["photo"] = item.get("image")

    result = process_json_feed_author(item, feed, result)

    # get audio or video attachment
    # only collect one because clients will only be expected to render one attachment
    if item.get("attachments"):
        result = process_attachments(item, result)

    if item.get("published"):
        parse_date = parse(item["published"])

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

    result["published"] = date

    if item.get("content_html"):
        result["content"] = {}
        result["content"]["text"] = clean_html_from_entry(item.get("content_html"))
        result["content"]["html"] = item.get("content_html")

    if item.get("title"):
        result["title"] = item.get("title")
    else:
        result[
            "title"
        ] = f"Post by {result['author'].get('name', item.get('url').split('/')[2])}"

    if item.get("url"):
        result["url"] = item.get("url")

    if item.get("post_type"):
        result["post-type"] = indieweb_utils.get_post_type(item)

    return result, date
