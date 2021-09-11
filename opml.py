# read xyz.opml and write xyz.txt

# read opml file
with open('feed.opml', 'r') as f:
    opml = f.read()

# get all urls
import listparser as lp
import requests

feed = lp.parse(opml)

for i in feed.feeds:
    print(i.url)
    channel = input("Channel name: ")
    r = requests.post("http://localhost:5000?action=follow&url={}&channel={}".format(i.url, channel))

    print(r.status_code)