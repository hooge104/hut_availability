# Johan van den Hoogen 2026
# MIT License

import argparse
from datetime import datetime, timedelta
import json
import os
import requests
import pandas as pd

BASE = "https://www.hut-reservation.org"
HUTS_LIST_FILE = os.path.join(os.path.dirname(__file__), "hutsList.json")

DEFAULT_HUT_NAMES = ["doree", "vignettes", "dix", "trient", "valsorey", "chanrion"]


def load_huts_list():
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
    all_huts = load_huts_list()
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


today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)

parser = argparse.ArgumentParser(description="Check Alpine hut bed availability.")
parser.add_argument("--from_date", default=today.strftime("%d.%m.%Y"), help="Start date DD.MM.YYYY (inclusive, default: today)")
parser.add_argument("--to_date",   default=(today + timedelta(days=7)).strftime("%d.%m.%Y"), help="End date DD.MM.YYYY (inclusive, default: today + 7 days)")
parser.add_argument("--huts", nargs="+", default=DEFAULT_HUT_NAMES, metavar="NAME", help="Partial hut name(s) to query (default: Haute Route huts)")
parser.add_argument("--csv", default=True, action=argparse.BooleanOptionalAction, help="Write results to a CSV file in output/ (default: true)")
args = parser.parse_args()

START_DATE = datetime.strptime(args.from_date, "%d.%m.%Y")
END_DATE   = datetime.strptime(args.to_date,   "%d.%m.%Y")

HUTS = resolve_huts(args.huts)
print(f"Resolving huts ({len(HUTS)}):")
for hut_id, hut_name in HUTS:
    print(f"  {hut_name} ({hut_id})")


def make_session():
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    session.get(f"{BASE}/api/v1/csrf")
    csrf_token = session.cookies.get("XSRF-TOKEN")
    session.headers.update({"X-XSRF-TOKEN": csrf_token})
    return session



def get_availability(session, hut_id):
    """Returns dict of {date: free_beds} for the hut."""
    r = session.get(
        f"{BASE}/api/v1/reservation/getHutAvailability",
        params={"hutId": hut_id, "step": "WIZARD"},
    )
    r.raise_for_status()
    result = {}
    for entry in r.json():
        date = datetime.fromisoformat(entry["date"].replace("Z", "+00:00")).replace(tzinfo=None)
        result[date] = entry["freeBeds"]
    return result


session = make_session()

date_range = pd.date_range(START_DATE, END_DATE)
col_labels = [d.strftime("%-d/%-m") for d in date_range]

print("Fetching availability:")
rows = []
for hut_id, hut_name in HUTS:
    availability = get_availability(session, hut_id)
    row = {"Hut": hut_name}
    for date, label in zip(date_range, col_labels):
        row[label] = availability.get(date.to_pydatetime(), "")
    rows.append(row)
    print(f"  {hut_name}: done")

df = pd.DataFrame(rows).set_index("Hut")
print(df.to_string())

if args.csv:
    os.makedirs("output", exist_ok=True)
    hut_slug = "-".join(str(hut_id) for hut_id, _ in HUTS)
    filename = f"availability_{START_DATE.strftime('%Y%m%d')}_{END_DATE.strftime('%Y%m%d')}_{hut_slug}.csv"
    csv_path = os.path.join("output", filename)
    df.to_csv(csv_path)
    print(f"\nSaved to {csv_path}")
