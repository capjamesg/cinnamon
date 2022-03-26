from bs4 import BeautifulSoup

def clean_html_from_entry(text):
    content = BeautifulSoup(text, "lxml").get_text(
        separator="\n"
    )
    
    # only allow p tags, a tags, divs, sections, and hrs
    soup = BeautifulSoup(content, "lxml")

    for tag in soup.find_all(reject=["p", "a", "div", "section", "hr"]):
        tag.extract()

    return soup.get_text(separator="\n")