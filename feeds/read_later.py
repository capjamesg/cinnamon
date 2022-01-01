from bs4 import BeautifulSoup
import datetime
import sqlite3
import requests
import indieweb_utils
import json

def read_later(url):
    try:
        r = requests.get(url, timeout=5, allow_redirects=True)
    except:
        return None
    
    if r.status_code != 200:
        return None
    
    soup = BeautifulSoup(r.text, "lxml")

    if soup.find(".h-entry"):
        content = soup.find(".h-entry").text
    elif soup.find("article"):
        content = soup.find("article").text
    else:
        content = soup.find("body").text

    month_with_padded_zero = str(datetime.datetime.now().month).zfill(2)
    day_with_padded_zero = str(datetime.datetime.now().day).zfill(2)
    hour_minute_second = str(datetime.datetime.now().hour).zfill(2) + ":" + str(datetime.datetime.now().minute).zfill(2) + ":" + str(datetime.datetime.now().second).zfill(2)
    published_date = f"{datetime.datetime.now().year}{month_with_padded_zero}{day_with_padded_zero}T{hour_minute_second}"

    record = {
        "result": {
            "url": url,
            "type": "summary",
            "content": {
                "text": content,
                "html": content
            },
            "title": soup.title.text,
            "published": published_date,

        }
    }

    # get og_image tag
    og_image = soup.find("meta", property="og:image")

    if og_image:
        record["photo"] = indieweb_utils.canonicalize_url(og_image["content"], url.split("/")[2], og_image["content"])

    if not record.get("photo"):
        # we will remove header and nav tags so that we are more likely to find a "featured image" for the post
        # remove <header> tags
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
            record["photo"] = indieweb_utils.canonicalize_url(all_images[0]["src"], url.split("/")[2], all_images[0]["src"])


    database = sqlite3.connect("microsub.db")

    with database:
        cursor = database.cursor()

        last_id = cursor.execute("SELECT MAX(id) FROM timeline;").fetchone()[0]

        feed_id = cursor.execute("SELECT id FROM following WHERE channel = 'read-later';").fetchone()[0]

        last_id += 1

        cursor.execute("""INSERT INTO timeline VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);""",
            (
                "read-later",
                json.dumps(record["result"]),
                record["result"]["published"],
                0,
                record["result"]["url"],
                record["result"]["url"],
                0,
                feed_id,
                last_id
            )
        )

    return url