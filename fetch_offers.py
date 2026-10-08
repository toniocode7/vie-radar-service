import json, re, sys, time, html, os, urllib.request, urllib.error

API = "https://civiweb-api-prd.azurewebsites.net/api/Offers/search"
SITE = "https://mon-vie-via.businessfrance.fr"
KEY = os.environ.get("VIE_API_KEY", "l+KwpoLPiXlsjxNT/NQ2iOFz8+iuygxAODs9FeAEWYM=")
PAGE = 100
MAX_PAGES = 20
MAX_DESC = 1500

BODY = {"limit": PAGE, "skip": 0, "query": "", "activitySectorId": [],
        "missionsTypesIds": [], "countriesIds": [], "studiesLevelId": [],
        "companiesSizes": [], "specializationsIds": [], "entreprisesIds": [],
        "missionStartDate": None, "gerographicZones": [],
        "countriesFilterOperator": "OR", "specializationsFilterOperator": "OR"}

def post(body):
    req = urllib.request.Request(
        API, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/plain, */*",
                 "X-API-KEY": KEY,
                 "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                 "Origin": SITE, "Referer": SITE + "/"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))

def pick(d, *keys):
    for k in keys:
        v = d.get(k)
        if v not in (None, "", []):
            return v
    return None

def clean(t):
    t = html.unescape(re.sub(r"<[^>]+>", " ", str(t or "")))
    return re.sub(r"\s+", " ", t).strip()

def convert(o):
    oid = pick(o, "id", "offerId")
    desc = " ".join(clean(pick(o, k)) for k in
                    ("missionDescription", "description", "missionProfile", "profile") if pick(o, k))
    try:
        ind = float(pick(o, "indemnite", "indemnity") or 0)
    except (TypeError, ValueError):
        ind = 0
    return {
        "id": "bf-%s" % oid,
        "t": clean(pick(o, "missionTitle", "title")),
        "c": clean(pick(o, "organizationName", "companyName")),
        "p": clean(pick(o, "countryName", "country")),
        "v": clean(pick(o, "cityName", "city")),
        "i": ind,
        "dur": pick(o, "missionDuration", "duration"),
        "u": "%s/offres/%s" % (SITE, oid),
        "d": desc[:MAX_DESC],
        "date": str(pick(o, "startBroadcastDate", "creationDate") or "")[:10],
        "src": "Business France",
    }

def main():
    out, seen = [], set()
    for page in range(MAX_PAGES):
        body = dict(BODY, skip=page * PAGE)
        try:
            data = post(body)
        except urllib.error.HTTPError as e:
            sys.exit("Erreur HTTP %s. Si c'est 401, la cle d'acces a peut-etre change." % e.code)
        except Exception as e:
            sys.exit("Impossible de joindre Business France : %s" % e)
        items = data.get("result") if isinstance(data, dict) else data
        if not items:
            break
        if page == 0:
            print("Champs recus :", sorted(items[0].keys()))
        new = 0
        for it in items:
            if str(pick(it, "missionType") or "VIE").upper() == "VIA":
                continue
            c = convert(it)
            if c["t"] and c["id"] not in seen:
                seen.add(c["id"])
                out.append(c)
                new += 1
        if new == 0:
            break
        time.sleep(0.7)
    if not out:
        sys.exit("Aucune offre lue.")
    with open("offers.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print("%d offres ecrites dans offers.json" % len(out))

if __name__ == "__main__":
    main()
