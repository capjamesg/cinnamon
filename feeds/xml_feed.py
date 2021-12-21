import requests
import datetime
import indieweb_utils
from bs4 import BeautifulSoup

def process_xml_feed(entry, feed, url):
    if entry.get("author"):
        author = {
            "type": "card",
            "name": entry.author,
            "url": entry.author_detail
        }
    elif feed.get("author"):
        author = {
            "type": "card",
            "name": feed.feed.author,
            "url": feed.feed.author_detail
        }
    else:
        author = {
            "type": "card",
            "name": feed.feed.get("title"),
            "url": feed.feed.get("link")
        }

    # get home page
    # get content type of url
    session = requests.Session()
    session.max_redirects = 2

    try:
        # follow one redirect
        r = session.get(url, allow_redirects=True, timeout=10)
    except:
        return None, None

    soup = BeautifulSoup(r.text, "lxml")

    # get favicon
    favicon = soup.find("link", rel="shortcut icon")

    if favicon:
        author["photo"] = indieweb_utils.canonicalize_url(favicon["href"], url.split("/")[2], favicon["href"])

    if entry.get("content"):
        soup = BeautifulSoup(entry.content[0].value, "lxml")

        content = {
            "text": soup.get_text(separator="\n"),
            "html": entry.content[0].value
        }
    elif entry.get("summary"):
        soup = BeautifulSoup(entry.summary, "lxml")

        content = {
            "text":soup.get_text(separator="\n"),
            "html": entry.summary
        }
    elif entry.get("description"):
        soup = BeautifulSoup(entry.description, "lxml")

        content = {
            "text":soup.get_text(separator="\n"),
            "html": entry.description
        }
    elif entry.get("title") and entry.get("link"):
        # get feed author
        content = {
            "text": entry.get("title"),
            "html": "<a href='" + entry.link + "'>" + entry.get("title") + "</a>"
        }
    elif entry.get("title") and not entry.get("link"):
        # get feed author
        content = {
            "text": entry.get("title"),
            "html": entry.get("title"),
        }
    else:
        content = {}

    if entry.get("published"):
        month_with_padded_zero = str(entry.published_parsed.tm_mon).zfill(2)
        day_with_padded_zero = str(entry.published_parsed.tm_mday).zfill(2)
        hour_minute_second = str(entry.published_parsed.tm_hour).zfill(2) + ":" + str(entry.published_parsed.tm_min).zfill(2) + ":" + str(entry.published_parsed.tm_sec).zfill(2)
        published = "{}{}{}T{}".format(entry.published_parsed.tm_year, month_with_padded_zero, day_with_padded_zero, hour_minute_second)
    elif entry.get("updated"):
        month_with_padded_zero = str(entry.updated_parsed.tm_mon).zfill(2)
        day_with_padded_zero = str(entry.updated_parsed.tm_mday).zfill(2)
        hour_minute_second = str(entry.updated_parsed.tm_hour).zfill(2) + ":" + str(entry.updated_parsed.tm_min).zfill(2) + ":" + str(entry.updated_parsed.tm_sec).zfill(2)
        published = "{}{}{}T{}".format(entry.updated_parsed.tm_year, month_with_padded_zero, day_with_padded_zero, hour_minute_second)
    else:
        month_with_padded_zero = str(datetime.datetime.now().month).zfill(2)
        day_with_padded_zero = str(datetime.datetime.now().day).zfill(2)
        hour_minute_second = str(datetime.datetime.now().hour).zfill(2) + ":" + str(datetime.datetime.now().minute).zfill(2) + ":" + str(datetime.datetime.now().second).zfill(2)
        published = "{}{}{}T{}".format(datetime.datetime.now().year, month_with_padded_zero, day_with_padded_zero, hour_minute_second)

    result = {
        "type": "entry",
        "author": author,
        "published": published,
        "content": content,
        "post-type": "entry",
    }

    if entry.get("title"):
        result["title"] = entry.title
    else:
        result["title"] = url

    if entry.get("link"):
        retrieve_post = requests.get(entry.link)

        parse_post = BeautifulSoup(retrieve_post.text, "lxml")

        # get og_image tag
        og_image = parse_post.find("meta", property="og:image")

        if og_image:
            result["photo"] = indieweb_utils.canonicalize_url(og_image["content"], url.split("/")[2], og_image["content"])

        if not result.get("photo"):
            # we will remove header and nav tags so that we are more likely to find a "featured image" for the post
            # remove <header> tags
            for header in parse_post.find_all("header"):
                header.decompose()

            # remove <nav> tags
            for nav in parse_post.find_all("nav"):
                nav.decompose()

            # get all images
            all_images = parse_post.find_all("img")
            
            if all_images and len(all_images) > 0 and all_images[0].get("src"):
                result["photo"] = indieweb_utils.canonicalize_url(all_images[0]["src"], url.split("/")[2], all_images[0]["src"])

    if content == {} and soup.find("meta", property="description"):
        result["content"] = {
            "text": soup.find("meta", property="description")["content"],
            "html": soup.find("meta", property="description")["content"]
        }
    elif content == {} and soup.find("meta", property="og:description"):
        result["content"] = {
            "text": soup.find("meta", property="og:description")["content"],
            "html": soup.find("meta", property="og:description")["content"]
        }

    if entry.get("links"):
        for link in entry.get("links"):
            if link.get("type") and "video" in link.get("type") and link.get("href"):
                result["video"] = [{"content_type": link.get("type"), "url": link.get("href")}]
                break
            elif link.get("type") and "audio" in link.get("type") and link.get("href"):
                result["audio"] = [{"content_type": link.get("type"), "url": link.get("href")}]
                break

    if entry.get("link"):
        result["url"] = entry.link

    # title
    if entry.get("title"):
        result["title"] = entry.title
    else:
        result["title"] = "Post by {}".format(author.get("name", url.split("/"))[2])
    
    if entry.get("media_content") and len(entry.get("media_content")) > 0:
        for media in entry.get("media_content"):
            if media.get("url"):
                if media.get("url").startswith("https://www.youtube.com") or media.get("url").startswith("http://www.youtube.com"):
                    new_url = media["url"].replace("/v/", "/embed/")
                    media["url"] = new_url

                if media.get("type") and ("video" in media.get("type") or "x-shockwave-flash" in media.get("type")) and media.get("url"):
                    result["video"] = [{"content_type": media.get("type"), "url": media.get("url")}]
                    break
                elif media.get("type") and "audio" in link.get("type") and media.get("url"):
                    result["audio"] = [{"content_type": media.get("type"), "url": media.get("url")}]
                    break

    published = published.split("T")[0]

    return result, published