import datetime
from unicodedata import name

import indieweb_utils
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse as parse_url
from .clean import clean_html_from_entry


def get_published_date(entry: dict) -> str:
    if entry.get("published_parsed"):
        month_with_padded_zero = str(entry.published_parsed.tm_mon).zfill(2)
        day_with_padded_zero = str(entry.published_parsed.tm_mday).zfill(2)
        published = str(entry.published_parsed.tm_year)
    elif entry.get("updated_parsed"):
        month_with_padded_zero = str(entry.updated_parsed.tm_mon).zfill(2)
        day_with_padded_zero = str(entry.updated_parsed.tm_mday).zfill(2)
        published = str(entry.updated_parsed.tm_year)
    else:
        month_with_padded_zero = str(datetime.datetime.now().month).zfill(2)
        day_with_padded_zero = str(datetime.datetime.now().day).zfill(2)

        published = str(datetime.datetime.now().year)

    hour_minute_second = (
        str(datetime.datetime.now().hour).zfill(2)
        + ":"
        + str(datetime.datetime.now().minute).zfill(2)
        + ":"
        + str(datetime.datetime.now().second).zfill(2)
    )

    published += month_with_padded_zero
    published += day_with_padded_zero
    published += "T" + hour_minute_second

    return published


def get_content(entry: dict) -> dict:
    if entry.get("content"):
        content = {
            "text": clean_html_from_entry(entry.content[0].value),
            "html": entry.content[0].value,
        }
    elif entry.get("summary"):
        content = {"text": clean_html_from_entry(entry.summary), "html": entry.summary}
    elif entry.get("description"):
        content = {"text": clean_html_from_entry(entry.description), "html": entry.description}
    elif entry.get("title") and entry.get("link"):
        # get feed author
        content = {
            "text": entry.get("title"),
            "html": "<a href='" + entry.link + "'>" + entry.get("title") + "</a>",
        }
    elif entry.get("title") and not entry.get("link"):
        # get feed author
        content = {
            "text": entry.get("title"),
            "html": entry.get("title"),
        }
    else:
        content = {}

    if content == {} and soup.find("meta", property="description"):
        content = {
            "text": soup.find("meta", property="description")["content"],
            "html": soup.find("meta", property="description")["content"],
        }
    elif content == {} and soup.find("meta", property="og:description"):
        content = {
            "text": soup.find("meta", property="og:description")["content"],
            "html": soup.find("meta", property="og:description")["content"],
        }

    return content


def process_media_content(entry: dict, result: dict, link: str) -> dict:
    if entry.get("links"):
        for link in entry.get("links"):
            if link.get("type") and "video" in link.get("type") and link.get("href"):
                result["video"] = [
                    {"content_type": link.get("type"), "url": link.get("href")}
                ]
                break
            elif link.get("type") and "audio" in link.get("type") and link.get("href"):
                result["audio"] = [
                    {"content_type": link.get("type"), "url": link.get("href")}
                ]
                break

    for media in entry.get("media_content"):
        if media.get("url") is None:
            continue

        parsed_url = parse_url(media.get("url"))

        # get domain name
        domain = parsed_url.netloc

        if domain == "youtube.com":
            new_url = media["url"].replace("/v/", "/embed/")
            media["url"] = new_url

        if (
            media.get("type")
            and (
                "video" in media.get("type") or "x-shockwave-flash" in media.get("type")
            )
            and media.get("url")
        ):
            result["video"] = [
                {"content_type": media.get("type"), "url": media.get("url")}
            ]
            break
        elif media.get("type") and "audio" in link.get("type") and media.get("url"):
            result["audio"] = [
                {"content_type": media.get("type"), "url": media.get("url")}
            ]
            break

    return result


def get_featured_photo(result: dict, url: str, parse_post: BeautifulSoup) -> dict:
    # we will remove header and nav tags so that we are more likely to find a "featured image" for the post
    # remove <header> tags
    parsed_url = parse_url(url)
    for header in parse_post.find_all("header"):
        header.decompose()

    # remove <nav> tags
    for nav in parse_post.find_all("nav"):
        nav.decompose()

    # get all images
    all_images = parse_post.find_all("img")

    if all_images and len(all_images) > 0 and all_images[0].get("src"):
        all_images = [i for i in all_images if "u-photo" not in i.get("class", [])]

    if len(all_images) > 0:
        if all_images[0].get("src"):
            result["photo"] = indieweb_utils.canonicalize_url(
                all_images[0]["src"], parsed_url.netloc, all_images[0]["src"]
            )

    return result


def process_xml_feed(entry: dict, feed: str, url: str) -> dict:
    """
    Processes an entry from an XML feed and turns it into a jf2 object.

    :param entry: The entry to process.
    :type entry: dict
    :param feed: The feed the entry came from.
    :type feed: str
    :param url: The URL of the feed.
    :type url: str
    :return: The processed entry.
    :rtype: dict
    """
    parsed_url = parse_url(url)

    if not entry or not entry.get("link"):
        return None, None

    if entry.get("author"):
        author = {"type": "card", "name": entry.author, "url": entry.author_detail}
    elif feed.get("author"):
        author = {
            "type": "card",
            "name": feed.feed.author,
            "url": feed.feed.author_detail,
        }
    else:
        author = {
            "type": "card",
            "name": feed.feed.get("title"),
            "url": feed.feed.get("link"),
        }

    # get home page
    # get content type of url
    session = requests.Session()
    session.max_redirects = 2

    try:
        # follow one redirect
        r = session.get(url, allow_redirects=True, timeout=10)
    except requests.exceptions.RequestException:
        return None, None

    soup = BeautifulSoup(r.text, "lxml")

    # get favicon
    favicon = soup.find("link", rel="shortcut icon")

    if favicon:
        author["photo"] = indieweb_utils.canonicalize_url(
            favicon["href"], parsed_url.netloc, favicon["href"]
        )

    content = get_content(entry)

    published = get_published_date(entry)

    result = {
        "type": "entry",
        "author": author,
        "published": published,
        "content": content,
        "post-type": "entry",
        "title": "",
        "url": entry.link,
    }

    if entry.get("title"):
        result["title"] = entry.title
    else:
        result["title"] = f"Post by {author.get('name', url.split('/')[2])}"

    try:
        retrieve_post = requests.get(entry.link, timeout=10)
    except:
        return None, None

    parse_post = BeautifulSoup(retrieve_post.text, "lxml")

    # get og_image tag
    og_image = parse_post.find("meta", property="og:image")

    if og_image:
        result["photo"] = indieweb_utils.canonicalize_url(
            og_image["content"], url.split("/")[2], og_image["content"]
        )

    if not result.get("photo"):
        result = get_featured_photo(result, url, parse_post)

    published = published.split("T")[0]

    if not entry.get("media_content"):
        return result, published

    result = process_media_content(entry, result, published)

    return result, published
