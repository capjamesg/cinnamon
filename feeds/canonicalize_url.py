def canonicalize_url(url, domain, full_url=None):
    if url.startswith("http://") or url.startswith("https://"):
        return url
    elif url.startswith("//"):
        return "https:" + domain.strip("/") + "/" + url
    elif url.startswith("/"):
        return "https://" + domain.strip("/") + "/" + url
    elif url.startswith("./"):
        return full_url + url.replace(".", "")
    elif url.startswith("../"):
        return "https://" + domain.strip("/") + "/" + url[3:]
    else:
        return "https://" + url