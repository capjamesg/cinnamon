# Source: https://github.com/capjamesg/indieweb-search/blob/main/crawler/authorship_discovery.py
# I have removed the rel check stage because this is already done by mf2py for each entry

import mf2py

def discover_author(h_card_url):	
	# if rel=author, look for h-card on the rel=author link
    h_card = None
    
    new_h_card = mf2py.parse(url=h_card_url)

    if new_h_card.get("rels") and new_h_card.get("rels").get("me"):
        rel_mes = new_h_card['rels']['me']
    else:
        rel_mes = []

    for j in new_h_card["items"]:
        if j.get('type') and j.get('type') == ['h-card'] and j['properties']['url'] == h_card_url and j['properties'].get('uid') == j['properties']['url']:
            h_card = j
            break
        elif j.get('type') and j.get('type') == ['h-card'] and j['properties'].get('url') in rel_mes:
            h_card = j
            break
        elif j.get('type') and j.get('type') == ['h-card'] and j['properties']['url'] == h_card_url:
            h_card = j
            break

    return h_card