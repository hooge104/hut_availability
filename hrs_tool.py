# Johan van den Hoogen 2026
# MIT License

import argparse
from datetime import datetime, timedelta
import json
import os
import requests
import pandas as pd

from utils import BASE, COUNTRY_CODES, COUNTRY_DISPLAY
from utils import normalize, resolve_huts, make_session, resolve_huts_by_country

DEFAULT_HUT_NAMES = None    # use all huts in the list
# DEFAULT_HUT_NAMES = ["doree", "vignettes", "dix", "trient", "valsorey", "chanrion"]


# ---------------------------------------------------------------------------
# CLI argument parsing and hut selection
# ---------------------------------------------------------------------------
 
today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)

parser = argparse.ArgumentParser(description="Check Alpine hut bed availability.")
parser.add_argument("--from_date", default=today.strftime("%d.%m.%Y"),
                    help="Start date DD.MM.YYYY (inclusive, default: today)")
parser.add_argument("--to_date",   default=(today + timedelta(days=7)).strftime("%d.%m.%Y"),
                    help="End date DD.MM.YYYY (inclusive, default: today + 7 days)")
 
# --- Hut selection: explicit names OR country/region/altitude discovery
hut_group = parser.add_mutually_exclusive_group()
hut_group.add_argument("--huts", nargs="+", metavar="NAME",
                        help="Partial hut name(s) to query")
hut_group.add_argument("--country", metavar="COUNTRY",
                        help=("Discover all available huts for a country "
                              "(e.g. 'Switzerland', 'France', 'Italy'). "
                              "For Switzerland, swisstopo is queried automatically."))
 
parser.add_argument("--region", metavar="REGION",
                    help=("Sub-filter by region / canton when using --country. "
                          "For Switzerland: 'valais', 'bernese_oberland', "
                          "'graubunden', 'ticino', 'uri', 'vaud', … "
                          "or a raw canton abbreviation (e.g. 'vs')."))
parser.add_argument("--altitude_min", type=float, metavar="M",
                    help="Minimum hut altitude in metres (Switzerland only, "
                         "requires --country CH/Switzerland)")
parser.add_argument("--altitude_max", type=float, metavar="M",
                    help="Maximum hut altitude in metres (Switzerland only)")
parser.add_argument("--csv", default=True, action=argparse.BooleanOptionalAction,
                    help="Write results to a CSV file in output/ (default: true)")

args = parser.parse_args()

if (args.region or args.altitude_min or args.altitude_max) and not args.country:
    parser.error("--region / --altitude_min / --altitude_max require --country")

START_DATE = datetime.strptime(args.from_date, "%d.%m.%Y")
END_DATE   = datetime.strptime(args.to_date,   "%d.%m.%Y")

if args.huts:
    print(f"Resolving huts by name ({len(args.huts)} query/queries):")
    HUTS = resolve_huts(args.huts)
elif args.country:
    country_code = COUNTRY_CODES.get(normalize(args.country), args.country.upper())
    country_display = COUNTRY_DISPLAY.get(country_code, country_code)
    print(f"Discovering {country_display} huts'"
          + (f", region='{args.region}'" if args.region else "")
          + (f", alt≥{args.altitude_min}m" if args.altitude_min else "")
          + (f", alt≤{args.altitude_max}m" if args.altitude_max else "")
          + " …")
    HUTS = resolve_huts_by_country(
        country=args.country,
        region=args.region,
        altitude_min=args.altitude_min,
        altitude_max=args.altitude_max,
    )
    if not HUTS:
        print("ERROR: no matching huts found in hutsList.json for these criteria.")
        raise SystemExit(1)
else:
    parser.error("Provide either --huts NAME [NAME …] or --country COUNTRY")
 
print(f"Resolved {len(HUTS)} hut(s):")
# for hut_id, hut_name in HUTS:
#     print(f"  {hut_name} ({hut_id})")
 

# ---------------------------------------------------------------------------
# session & availability fetch
# ---------------------------------------------------------------------------

date_range = pd.date_range(START_DATE, END_DATE)
col_labels = [d.strftime("%-d/%-m") for d in date_range]

session = make_session()

print("Fetching availability:")
rows = []
for hut_id, hut_name in HUTS:
    r = session.get(
        f"{BASE}/api/v1/reservation/getHutAvailability",
        params={"hutId": hut_id, "step": "WIZARD"},
    )
    if r.status_code == 403:
        # print(f"  {hut_name}: no availability / closed (403)")
        row = {"Hut": hut_name}
        for label in col_labels:
            row[label] = 0
        rows.append(row)
        continue
    r.raise_for_status()
    availability = {}
    for entry in r.json():
        date = datetime.fromisoformat(entry["date"].replace("Z", "+00:00")).replace(tzinfo=None)
        availability[date] = entry["freeBeds"]
    row = {"Hut": hut_name}
    for date, label in zip(date_range, col_labels):
        row[label] = availability.get(date.to_pydatetime(), "")
    rows.append(row)
    print(f"  {hut_name}: done")

if not rows:
    print("ERROR: no availability data fetched.")
    raise SystemExit(1)

rows.sort(key=lambda r: all(r[l] == 0 for l in col_labels))

df = pd.DataFrame(rows).set_index("Hut")
df = df.fillna(0).astype(int)
print("\n" + df.to_string())

if args.huts:
    slug = "-".join(normalize(n) for n in args.huts)
elif args.country:
    slug = normalize(args.country)
    if args.region:
        slug += f"_{normalize(args.region)}"
    if args.altitude_min:
        slug += f"_min{int(args.altitude_min)}m"
    if args.altitude_max:
        slug += f"_max{int(args.altitude_max)}m"

if args.csv:
    os.makedirs("output", exist_ok=True)
    filename = f"availability_{START_DATE.strftime('%Y%m%d')}_{END_DATE.strftime('%Y%m%d')}_{slug}.csv"
    csv_path = os.path.join("output", filename)
    df.to_csv(csv_path)
    print(f"\nSaved to {csv_path}")

