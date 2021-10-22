import sqlite3
import requests
from bs4 import BeautifulSoup
import random
import string
import mf2py
import datetime
import json
import feedparser
from dateutil.parser import parse
import microformats2
from time import mktime

def canonicalize_url(url, domain):
    if url.startswith("http://") or url.startswith("https://"):
        return url
    elif url.startswith("//"):
        return "https:" + domain.strip() + "/" + url
    elif url.startswith("/"):
        return "https://" + domain.strip() + "/" + url
    else:
        return "https://" + url

def process_hfeed(url, cursor=None, channel_uid=None, add_to_db=True):
    r = requests.get(url)

    mf2_raw = mf2py.parse(r.text)

    hcard = [item for item in mf2_raw['items'] if item['type'][0] == 'h-card']

    results = []

    for item in mf2_raw["items"]:
        if item.get("type") and item.get("type")[0] == "h-feed":
            for child in item["children"]:
                
                jf2 = {
                    "type": "entry",
                    "url": canonicalize_url(child["properties"]["url"][0], url.split("/")[2]),
                }

                # check if in timeline before proceeding
                # we don't want to add duplicate records to the timeline
                # without this precaution, any post without a published date will resurface at the top of every feed

                # in_timeline = cursor.execute("SELECT * FROM timeline WHERE url = ?", (jf2["url"],)).fetchall()

                # if len(in_timeline) > 0:
                #     continue

                if hcard:
                    jf2["author"] = {
                        "type": "card",
                        "name": canonicalize_url(hcard[0]["properties"]["name"][0], url.split("/")[2]),
                        "url": canonicalize_url(hcard[0]["properties"]["url"][0], url.split("/")[2]) 
                    }

                if add_to_db == True:
                    in_db = cursor.execute("SELECT * FROM timeline WHERE url = ?", (jf2["url"],)).fetchall()

                    if len(in_db) > 0:
                        continue

                if mf2_raw["properties"].get("photo"):
                    jf2["photo"] = canonicalize_url(mf2_raw["properties"].get("photo")[0], url.split("/")[2]) 

                if child["properties"].get("category"):
                    jf2["category"] = child["properties"].get("category")[0]

                if child["properties"].get("name"):
                    jf2["name"] = child["properties"].get("name")[0]

                if child["properties"].get("summary"):
                    jf2["content"] = {
                        "text": BeautifulSoup(child["properties"].get("summary")[0]).get_text(),
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

                if add_to_db == True:
                    cursor.execute("INSERT INTO timeline VALUES (?, ?, ?, ?, ?, ?, ?)", (channel_uid, json.dumps(jf2), date, "unread", jf2["url"], ten_random_letters, 0, ))
                
                results.append(jf2)

    return results

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
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "html.parser")

    # get favicon
    favicon = soup.find("link", rel="shortcut icon")

    if favicon:
        author["photo"] = favicon["href"]

    if entry.get("content"):
        soup = BeautifulSoup(entry.content[0].value, "html.parser")

        content = {
            "text":soup.get_text(),
            "html": entry.content[0].value
        }
    elif entry.get("summary"):
        soup = BeautifulSoup(entry.summary, "html.parser")

        content = {
            "text":soup.get_text(),
            "html": entry.summary
        }
    elif entry.get("description"):
        soup = BeautifulSoup(entry.description, "html.parser")

        content = {
            "text":soup.get_text(),
            "html": entry.description
        }
    elif entry.get("title") and entry.get("link"):
        # get feed author
        content = {
            "text": entry.title,
            "html": "<a href='" + entry.link + "'>" + entry.title + "</a>"
        }
    elif entry.get("title") and not entry.get("link"):
        # get feed author
        content = {
            "text": entry.title,
            "html": entry.title,
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
        "name": entry.title,
    }

    if entry.get("link"):
        retrieve_post = requests.get(entry.link)

        parse_post = BeautifulSoup(retrieve_post.text, "html.parser")

        # get og_image tag
        og_image = parse_post.find("meta", property="og:image")

        if og_image:
            result["photo"] = og_image["content"]

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
            
            if all_images:
                result["photo"] = all_images[0]["src"]

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

    if entry.get("media_content") and len(entry.get("media_content")) > 0 and entry.get("media_content")[0].get("url") and entry.get("media_content")[0].get("type"):
        if url.startswith("https://www.youtube.com") or url.startswith("http://www.youtube.com"):
            result["video"] = "https://www.youtube.com/embed/" + entry.media_content[0].get("url").split("/")[-1].split("?")[0]
        else:
            result["video"] = entry.media_content[0].get("url")

    published = published.split("T")[0]

    return result, published

def poll_feeds():
    connection = sqlite3.connect("microsub.db")

    with connection:
        cursor = connection.cursor()

        subscriptions = cursor.execute("SELECT url, channel, etag FROM following;").fetchall()

        for s in subscriptions:
            url = s[0]

            # get channel uid
            try:
                channel_uid = cursor.execute("SELECT uid FROM channels WHERE uid = ?;", (s[1],)).fetchone()[0]
            except:
                continue

            # get content type of url
            try:
                r = requests.head(url)
            except:
                continue

            if r.headers.get('content-type'):
                content_type = r.headers['content-type']
            else:
                content_type = ""

            print("polling " + url)

            if "xml" in content_type or ".xml" in url:
                feed = feedparser.parse(url)

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

                for entry in feed.entries:
                    result, published = process_xml_feed(entry, feed, url)

                    if entry.get("link"):
                        result["url"] = entry.link

                        # check if url in db
                        in_db = cursor.execute("SELECT * FROM timeline WHERE url = ?", (result["url"],)).fetchall()

                        if len(in_db) > 0:
                            continue
                    else:
                        continue

                    ten_random_letters = ''.join(random.choice(string.ascii_lowercase) for _ in range(10))

                    cursor.execute("INSERT INTO timeline VALUES (?, ?, ?, ?, ?, ?, ?)", (channel_uid, json.dumps(result), published, "unread", result["url"], ten_random_letters, 0, ))
            else:
                process_hfeed(url, cursor, channel_uid)

    print("polled all subscriptions")

if __name__ == "__main__":
    poll_feeds()