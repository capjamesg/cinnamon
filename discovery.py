from .feeds import canonicalize_url
from bs4 import BeautifulSoup
import requests

def feed_discovery(url):
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    elif url.startswith("//"):
        url = "https:" + url

    soup = BeautifulSoup(requests.get(url).text, "html.parser")

    # check for presence of mf2 hfeed
    h_feed = soup.find_all(class_="h-feed")

    feeds = []

    feeds_on_page = soup.find_all("link", rel="alternate") + soup.find_all("link", rel="feed")

    for f in feeds_on_page:
        feeds.append({"link": canonicalize_url.canonicalize_url(f.get("href").strip("/"), url.split("/")[2], f.get("href").strip("/")), "type": f.get("type")})

    return feeds, h_feed