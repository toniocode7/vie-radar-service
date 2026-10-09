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

def spec_ids(o):
    """Identifiants de specialisation d'une offre. Le site les envoie sous forme de texte JSON, par exemple ['["9","205"]']."""
    out = []
    def walk(v):
        if isinstance(v, str):
            t = v.strip()
            if t.startswith("["):
                try:
                    walk(json.loads(t)); return
                except ValueError:
                    pass
            if t:
                out.append(t)
        elif isinstance(v, (int, float)):
            out.append(str(int(v)))
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif isinstance(v, dict):
            walk(pick(v, "id", "specializationId", "value"))
    walk(o.get("specialization")); walk(o.get("specializations"))
    res = []
    for x in out:
        if x not in res:
            res.append(x)
    return res

NAME_KEYS = ("name", "label", "libelle", "title", "nameFr", "labelFr", "libelleFr", "specializationName", "text", "value")
CANDIDATES = ["Specialization", "Specializations", "Specialisation", "Specialisations",
              "Specialization/GetAll", "Specializations/GetAll", "Reference/Specializations", "Reference/Specialization",
              "References/Specializations", "Referentiel/Specializations", "Nomenclature/Specializations",
              "Nomenclature/Specialization", "Nomenclatures/Specializations", "Offers/specializations", "Offers/Specializations",
              "Offers/filters", "Filters", "Parameters/Specializations", "Common/Specializations", "Data/Specializations",
              "Specialization/list", "Specializations/list", "Specialization/search", "Offers/GetSpecializations", "Offer/specializations",
              "Reference/GetSpecializations", "Referential/Specializations", "Lists/Specializations", "Parameter/Specializations",
              "Reference/specialization", "References/specializations", "Reference", "References", "Referentiel", "Nomenclature", "Nomenclatures"]

def get(path):
    req = urllib.request.Request(
        "https://civiweb-api-prd.azurewebsites.net/api/" + path, method="GET",
        headers={"Accept": "application/json", "X-API-KEY": API_KEY, "User-Agent": "Mozilla/5.0 (compatible; vie-radar personnel)",
                 "Origin": "https://mon-vie-via.businessfrance.fr", "Referer": "https://mon-vie-via.businessfrance.fr/"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def table(data, wanted):
    """Cherche dans une reponse une liste d'elements {id, nom} et rend {id: nom}."""
    found = {}
    def visit(v):
        if isinstance(v, list):
            for x in v:
                visit(x)
        elif isinstance(v, dict):
            i = pick(v, "id", "Id", "specializationId", "value")
            n = pick(v, *NAME_KEYS)
            if i is not None and isinstance(n, str):
                found[str(i)] = clean(n)
            for x in v.values():
                if isinstance(x, (list, dict)):
                    visit(x)
    visit(data)
    return found

def spec_names(wanted):
    """Essaie plusieurs adresses du site pour retrouver le nom de chaque specialisation."""
    for path in CANDIDATES:
        try:
            data = get(path)
        except urllib.error.HTTPError as e:
            print("Specialisations", path, "-> HTTP", e.code)
            continue
        except Exception as e:
            print("Specialisations", path, "-> erreur", str(e)[:60])
            continue
        t = table(data, wanted)
        print("Specialisations", path, "-> OK,", len(t), "noms, apercu :", json.dumps(data, ensure_ascii=False)[:200])
        if wanted and sum(1 for w in wanted if w in t) >= max(1, len(wanted) // 2):
            print("Specialisations : liste trouvee sur", path)
            return t
    return {}

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
        "spi": spec_ids(o),
        "src": "Business France",
    }

def scan_specs(known):
    """Interroge le site avec chaque numero de specialisation (1 a 400) pour savoir quelles offres il renvoie.
    Cela permet de reconstituer les domaines. Fait une seule fois, le resultat est garde dans offers.json."""
    def ask(value, skip):
        body = {"limit": 100, "skip": skip, "query": "", "activitySectorId": [], "missionsTypesIds": [],
                "missionsDurations": [], "gerographicZones": [], "geographicZones": [], "countriesIds": [],
                "studiesLevelId": [], "companiesSizeIds": [], "specializationsIds": value, "targetIds": [], "teletravail": None}
        return post(body)
    # Cherche la forme que le site accepte : liste de textes, liste de nombres, ou un seul texte
    forms = [lambda x: [str(x)], lambda x: [int(x)], lambda x: str(x), lambda x: int(x)]
    form = None
    for k, f in enumerate(forms):
        try:
            d = ask(f(9), 0)
            print("Scan : forme %d acceptee, %s offres pour le numero 9" % (k, d.get("count")))
            form = f
            break
        except urllib.error.HTTPError as e:
            try:
                msg = e.read().decode("utf-8")[:300]
            except Exception:
                msg = ""
            print("Scan : forme %d refusee (HTTP %s) %s" % (k, e.code, msg))
        except Exception as e:
            print("Scan : forme %d erreur %s" % (k, str(e)[:80]))
    if not form:
        return {}
    res, errs = {}, 0
    for x in range(1, 401):
        ids, skip = [], 0
        try:
            for _ in range(10):
                d = ask(form(x), skip)
                it = d.get("result") or d.get("results") or d.get("items") or []
                ids += [i.get("id") for i in it]
                skip += len(it)
                if not it or skip >= (d.get("count") or 0):
                    break
        except Exception as e:
            errs += 1
            print("Scan", x, "erreur", str(e)[:60])
            if errs >= 10:
                break
            time.sleep(1.5)
            continue
        if ids:
            res[str(x)] = ids
        time.sleep(0.15)
    print("Scan des specialisations : %d numeros renvoient des offres, %d erreurs" % (len(res), errs))
    return res if errs < 10 else {}

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
            if isinstance(data, dict):
                print("Cles de la reponse :", {k: (v if not isinstance(v, (list, dict)) else type(v).__name__) for k, v in data.items()})
            print("Champs de specialisation :", {k: v for k, v in items[0].items() if "special" in k.lower()})
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
    wanted = sorted({i for c in out for i in c["spi"]})
    print("Identifiants de specialisation vus :", len(wanted), wanted[:30])
    names = spec_names(wanted)
    for c in out:
        c["sp"] = [names[i] for i in c["spi"] if i in names]
    print("Offres avec specialisation nommee :", sum(1 for c in out if c["sp"]))
    scan = None
    try:
        with open("offers.json", encoding="utf-8") as f:
            scan = json.load(f).get("specscan")
    except Exception:
        scan = None
    if not scan:
        scan = scan_specs(wanted)
    with open("offers.json", "w", encoding="utf-8") as f:
        json.dump({"updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "total": len(out), "offers": out, "specscan": scan}, f, ensure_ascii=False)
    print("Business France annonce : %s | lues : %d | doublons ignores : %d | sans titre (gardees) : %d | ecrites : %d" % (total, lues, doublons, sans_titre, len(out)))
    types = {}
    for c in out:
        types[c["k"] or "?"] = types.get(c["k"] or "?", 0) + 1
    print("Types :", types)
    print("%d offres ecrites dans offers.json" % len(out))

if __name__ == "__main__":
    main()
