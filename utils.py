# !/usr/bin/env python3
# Nicole Clerx 2026
# additional tools for expanding hut availability search

import os
import re
import json
from networkx import hits
import requests

BASE = "https://www.hut-reservation.org"
HUTS_LIST_FILE = os.path.join(os.getcwd(), "hutsList.json")

SWISSTOPO_SEARCH = "https://api3.geo.admin.ch/rest/services/api/SearchServer"
SWISSTOPO_HEIGHT = "https://api3.geo.admin.ch/rest/services/height"

SWISS_REGIONS = {
    "valais":            ["vs"],
    "bernese_oberland":  ["be"],
    "graubunden":        ["gr"],
    "ticino":            ["ti"],
    "uri":               ["ur"],
    "glarus":            ["gl"],
    "appenzell":         ["ar", "ai"],
    "vaud":              ["vd"],
    "fribourg":          ["fr"],
    "jura":              ["ju"],
    "central":           ["ur", "sz", "ow", "nw", "zg", "lu"],
    "east":              ["sg", "ar", "ai", "gl", "gr"],
    "west":              ["vs", "vd", "fr", "ju"],
}

HUT_KEYWORDS = [
    "cabane", "refuge", "hütte", "hutte", "capanna", "bivouac", "bivak",
    "biwak", "bivacco",
]

# map user-facing country names/codes → 2-letter code used in hutsList.json
COUNTRY_CODES = {
    "switzerland": "CH",
    "swiss":       "CH",
    "ch":          "CH",
    "suisse":      "CH",
    "schweiz":     "CH",
    "svizzera":    "CH",
    "france":      "FR",
    "frankreich":  "FR",
    "fr":          "FR",
    "italy":       "IT",
    "italien":     "IT",
    "italia":      "IT",
    "it":          "IT",
    "austria":     "AT",
    "osterreich":  "AT",  # normalised (ö -> o)
    "at":          "AT",
    "germany":     "DE",
    "deutschland": "DE",
    "de":          "DE",
    "liechtenstein": "LI",
    "li":            "LI",
}

COUNTRY_DISPLAY = {
    "CH": "Swiss",
    "AT": "Austrian",
    "DE": "German",
    "IT": "Italian",
    "LI": "Liechtenstein",
    "FR": "French",
}

SWISS_COUNTRY_CODES = {"CH"}


def _load_huts_list():
    if not os.path.exists(HUTS_LIST_FILE):
        return []
    with open(HUTS_LIST_FILE) as f:
        return json.load(f)


def normalize(s):
    s = s.lower()
    s = s.replace("ä", "a").replace("ö", "o").replace("ü", "u")
    s = s.replace("ae", "a").replace("oe", "o").replace("ue", "u")
    return s


def resolve_huts(names):
    """Resolve partial hut name strings to (hut_id, hut_name) tuples."""
    all_huts = _load_huts_list()
    resolved = []
    for query in names:
        matches = [h for h in all_huts if normalize(query) in normalize(h["hutName"])]
        if not matches:
            print(f"  ERROR: no hut found matching '{query}'")
            raise SystemExit(1)
        if len(matches) > 1:
            options = ", ".join(f"{h['hutName']} ({h['hutId']})" for h in matches[:5])
            print(f"  ERROR: '{query}' is ambiguous: {options}")
            raise SystemExit(1)
        resolved.append((matches[0]["hutId"], matches[0]["hutName"]))
    return resolved


def make_session():
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    session.get(f"{BASE}/api/v1/csrf")
    csrf_token = session.cookies.get("XSRF-TOKEN")
    if not csrf_token:
        print("  WARNING: CSRF token not received - requests may fail with 403")
    session.headers.update({"X-XSRF-TOKEN": csrf_token})
    return session


# ---------------------------------------------------------------------------
# swisstopo helpers
# ---------------------------------------------------------------------------

def _lv95_to_wgs84_approx(e, n):
    """
    Fast approximate conversion from LV95 (CH1903+) to WGS84.
    Accurate to ~1m, good enough for altitude lookups.
    Reference: swisstopo approximation formulas.
    """
    e_ = (e - 2_600_000) / 1_000_000
    n_ = (n - 1_200_000) / 1_000_000
    lat = (16.9023892
           + 3.238272   * n_
           - 0.270978   * e_**2
           - 0.002528   * n_**2
           - 0.0447     * e_**2 * n_
           - 0.0140     * n_**3)
    lon = (2.6779094
           + 4.728982   * e_
           + 0.791484   * e_ * n_
           + 0.1306     * e_ * n_**2
           - 0.0436     * e_**3)
    lat = lat * 100 / 36
    lon = lon * 100 / 36
    return lat, lon


def get_altitude_swisstopo(easting, northing):
    """Query swisstopo height service for a LV95 point. Returns metres or None."""
    try:
        r = requests.get(
            SWISSTOPO_HEIGHT,
            params={"easting": easting, "northing": northing},
            timeout=5,
        )
        r.raise_for_status()
        return r.json().get("height")
    except Exception:
        return None


def _is_hut_location(label, detail):
    text = normalize(label + " " + detail)
    if "flurname" in text:
        return False
    if not any(kw in normalize(label) for kw in HUT_KEYWORDS):
        return False
    if normalize(label.strip()) in {normalize(kw) for kw in HUT_KEYWORDS}:
        return False
    return True


def search_swiss_huts_by_region(region, altitude_min=None, altitude_max=None,
                                 query_terms=None):
    """
    Search swisstopo for hut-like named locations in a given region.

    Parameters
    ----------
    region : str or None
        Key from SWISS_REGIONS dict, or a raw canton abbreviation (e.g. 'vs').
    altitude_min, altitude_max : float or None
        Altitude filter in metres.
    query_terms : list[str] or None
        Name fragments to search for. Defaults to common hut keywords.

    Returns
    -------
    list of dict with keys: name, detail, altitude, easting, northing, lat, lon
    """
    if query_terms is None:
        query_terms = HUT_KEYWORDS

    region_cantons = None
    if region:
        region_key = normalize(region)
        region_cantons = SWISS_REGIONS.get(region_key, [region_key])
    
    canton_bboxes = []
    if region_cantons:
        for canton in region_cantons:
            try:
                r = requests.get(
                    SWISSTOPO_SEARCH,
                    params={"searchText": canton, "type": "locations",
                            "origins": "kantone", "sr": 21781, "limit": 1},
                    timeout=10,
                )
                r.raise_for_status()
                hits = r.json().get("results", [])
                if hits:
                    box = hits[0]["attrs"].get("geom_st_box2d", "")
                    nums = box.replace("BOX(", "").replace(")", "").replace(",", " ").split()
                    if len(nums) == 4:
                        canton_bboxes.append(tuple(float(v) for v in nums))
            except Exception:
                pass  # if bbox lookup fails, region filter is skipped for this canton

    def _in_canton_bbox(y, x):
        # y = easting, x = northing, both in LV03
        if not canton_bboxes:
            return True
        for xmin, ymin, xmax, ymax in canton_bboxes:
            if xmin <= y <= xmax and ymin <= x <= ymax:
                return True
        return False

    results = []
    seen_names = set()

    for term in query_terms:
        params = {
            "searchText": term,
            "type": "locations",
            "origins": "gazetteer",
            "limit": 50,
        }
        try:
            r = requests.get(SWISSTOPO_SEARCH, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            print(f"  WARNING: swisstopo search failed for '{term}': {exc}")
            continue

        for item in data.get("results", []):
            attrs  = item.get("attrs", {})
            label = re.sub(r"<[^>]+>", "", attrs.get("label", "")).strip()
            label = re.sub(r"\s*\([A-Z]{0,2}\)\s*-.*$", "", label).strip()
            
            label_lower = label.lower()
            cut = None
            for kw in HUT_KEYWORDS:
                pos = label_lower.find(kw)
                if pos == -1:
                    continue
                while pos > 0 and label[pos - 1 ] not in (" ", "\t"):
                    pos -= 1
                if cut is None or pos < cut:
                     cut = pos
            label = label[cut:].strip() if cut is not None else label
            detail = attrs.get("detail", "")
            y = attrs.get("y")   # easting  (LV95)
            x = attrs.get("x")   # northing (LV95)

            if not label or label in seen_names:
                continue
            if not _is_hut_location(label, detail):
                continue
            if region_cantons and not _in_canton_bbox(y or 0, x or 0):
                continue

            # Altitude filter
            altitude = None
            if (altitude_min is not None or altitude_max is not None) and y and x:
                altitude = get_altitude_swisstopo(y, x)
                if altitude is not None:
                    altitude = float(altitude)
                    if altitude_min is not None and altitude < altitude_min:
                        continue
                    if altitude_max is not None and altitude > altitude_max:
                        continue

            lat = attrs.get("lat")
            lon = attrs.get("lon")

            seen_names.add(label)
            results.append({
                "name":     label,
                "detail":   detail,
                "altitude": altitude,
                "easting":  y,
                "northing": x,
                "lat":      lat,
                "lon":      lon,
            })

    return results


def hut_names_from_swisstopo(region=None, altitude_min=None, altitude_max=None):
    """
    Return bare hut name strings from swisstopo, ready for fuzzy-matching
    against hutsList.json.
    """
    hits = search_swiss_huts_by_region(
        region=region,
        altitude_min=altitude_min,
        altitude_max=altitude_max,
    )
    if not hits:
        print("  WARNING: swisstopo returned no hut locations for these criteria.")
        return []
    print(f"  swisstopo found {len(hits)} candidate hut location(s):")
    # for h in hits:
    #     alt_str = f"  ~{h['altitude']:.0f}m" if h["altitude"] else ""
    #     print(f"    {h['name']}{alt_str}  ({h['detail']})")

    return [h["name"] for h in hits]


# ---------------------------------------------------------------------------
# Main resolver
# ---------------------------------------------------------------------------

def resolve_huts_by_country(country, region=None, altitude_min=None,
                             altitude_max=None):
    """
    Discover huts in hutsList.json that match a country/region/altitude filter.
    For Switzerland, additionally queries swisstopo to find candidate hut names.

    Returns list of (hut_id, hut_name).
    """
    all_huts = _load_huts_list()
    country_code = COUNTRY_CODES.get(normalize(country), country.upper())

    if country_code in SWISS_COUNTRY_CODES:
        print("  Using swisstopo API to find Swiss huts …")
        candidate_names = hut_names_from_swisstopo(
            region=region,
            altitude_min=altitude_min,
            altitude_max=altitude_max,
        )

        if candidate_names:
            resolved = []
            for cname in candidate_names:
                cname_norm = normalize(cname)
                matches = [
                    h for h in all_huts
                    if cname_norm in normalize(h["hutName"])
                    and normalize(h["hutName"]) in cname_norm  # bidirectional: names must be close
                ]
                if not matches and len(cname.split()) >= 3:
                            matches = [h for h in all_huts if cname_norm in normalize(h["hutName"])]
                for m in matches:
                    entry = (m["hutId"], m["hutName"])
                    if entry not in resolved:
                        resolved.append(entry)
            if resolved:
                return resolved
            print("  WARNING: none of the swisstopo hut names matched hutsList.json.")

        print(f"  Falling back to hutsList.json scan for country code '{country_code}' …")
        return [
            (h["hutId"], h["hutName"]) for h in all_huts
            if h.get("hutCountry", h.get("country", "")).strip().upper() == country_code
        ]

    resolved = []
    for h in all_huts:
        hut_country = h.get("country", h.get("hutCountry", "")).strip().upper()
        if hut_country != country_code:
            continue
        if region:
            hut_region = normalize(h.get("region", h.get("hutRegion", h.get("hutName", ""))))
            if normalize(region) not in hut_region:
                continue
        resolved.append((h["hutId"], h["hutName"]))

    return resolved