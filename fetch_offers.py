"""Lit les offres VIE publiées sur Business France et écrit offers.json.
Usage : python fetch_offers.py
Aucune dépendance à installer (Python 3.9 ou plus).
Une exécution toutes les 30 minutes suffit."""
import json, os, re, sys, time, html, datetime, urllib.request, urllib.error

API = "https://civiweb-api-prd.azurewebsites.net/api/Offers/search"
SITE = "https://mon-vie-via.businessfrance.fr/offres/"
PAGE = 100
API_KEY = os.environ.get("VIE_API_KEY", "l+KwpoLPiXlsjxNT/NQ2iOFz8+iuygxAODs9FeAEWYM=")
MAX_DESC = 1500

def post(body):
    req = urllib.request.Request(
        API, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json", "X-API-KEY": API_KEY,
                 "User-Agent": "Mozilla/5.0 (compatible; vie-radar personnel)",
                 "Origin": "https://mon-vie-via.businessfrance.fr",
                 "Referer": "https://mon-vie-via.businessfrance.fr/"})
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
    oid = pick(o, "id", "offerId", "reference")
    desc = " ".join(clean(pick(o, k)) for k in
                    ("missionDescription", "description", "missionProfile", "profile", "missionDescriptionEn") if pick(o, k))
    ind = pick(o, "indemnite", "indemnity", "indemniteMensuelle", "monthlyIndemnity")
    try:
        ind = float(ind)
    except (TypeError, ValueError):
        ind = 0
    return {
        "id": "bf-%s" % oid,
        "t": clean(pick(o, "missionTitle", "title", "libelle")),
        "c": clean(pick(o, "organizationName", "companyName", "company", "organization")),
        "p": clean(pick(o, "countryName", "countryNameEn", "country", "pays")),
        "v": clean(pick(o, "cityName", "cityNameEn", "city", "ville")),
        "i": ind,
        "dur": pick(o, "missionDuration", "duration", "durationMonths"),
        "u": SITE + str(oid),
        "d": desc[:MAX_DESC],
        "date": str(pick(o, "creationDate", "startBroadcastDate", "publicationDate", "startDate") or ""),
        "k": clean(pick(o, "missionType", "missionTypeName", "missionTypeLabel", "type")),
        "src": "Business France",
    }

def main():
    body = {"limit": PAGE, "skip": 0, "query": "", "activitySectorId": [], "missionsTypesIds": [],
            "missionsDurations": [], "gerographicZones": [], "geographicZones": [], "countriesIds": [],
            "studiesLevelId": [], "companiesSizeIds": [], "specializationsIds": [], "targetIds": [], "teletravail": None}
    out, seen, total = [], set(), None
    lues, doublons, sans_titre = 0, 0, 0
    while True:
        try:
            data = post(body)
        except urllib.error.HTTPError as e:
            sys.exit("Erreur HTTP %s. Business France a peut-etre change son interface : voir README, partie 'Si ca ne marche pas'." % e.code)
        except Exception as e:
            sys.exit("Impossible de joindre Business France : %s" % e)
        items = data.get("result") or data.get("results") or data.get("items") or (data if isinstance(data, list) else [])
        if not isinstance(data, list):
            total = data.get("count", total)
        if body["skip"] == 0 and items:
            print("Champs recus (utile si un champ est vide) :", sorted(items[0].keys()))
        if not items:
            break
        for it in items:
            lues += 1
            c = convert(it)
            if not c["t"]:
                c["t"] = "Offre sans titre"
                sans_titre += 1
            if c["id"] in seen:
                doublons += 1
                continue
            seen.add(c["id"])
            out.append(c)
        body["skip"] += len(items)
        if total and body["skip"] >= total:
            break
        time.sleep(0.7)
    if not out:
        sys.exit("Aucune offre lue. Voir README, partie 'Si ca ne marche pas'.")
    with open("offers.json", "w", encoding="utf-8") as f:
        json.dump({"updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "total": len(out), "offers": out}, f, ensure_ascii=False)
    print("Business France annonce : %s | lues : %d | doublons ignores : %d | sans titre (gardees) : %d | ecrites : %d" % (total, lues, doublons, sans_titre, len(out)))
    types = {}
    for c in out:
        types[c["k"] or "?"] = types.get(c["k"] or "?", 0) + 1
    print("Types :", types)
    print("%d offres ecrites dans offers.json" % len(out))

if __name__ == "__main__":
    main()
