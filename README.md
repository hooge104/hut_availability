# Hut availability 

Fetches mountain hut bed availability from the [hut-reservation.org](https://www.hut-reservation.org) REST API. Only huts reservable through hut-reservation.org are available; countries included: Switzerland, Austria, Italy, Germany, Liechtenstein. Outputs a wide-format table (huts as rows, dates as columns) and optionally to a CSV file.

## Setup

```
git clone https://github.com/hooge104/hut_availability
cd hut_availability
pip install requests pandas
```

## Usage

```
python hrs_tool.py [--from_date DD.MM.YYYY] [--to_date DD.MM.YYYY] [--huts NAME ...] [--no-csv]
```

### Flags

| Flag | Description |
|---------|-------------|
| `--from_date` | Start date (inclusive), format `DD.MM.YYYY` (default: today) |
| `--to_date` | End date (inclusive), format `DD.MM.YYYY` (default: today + 7 days) |
| `--huts` | One or more partial hut name(s) to query. |
| `--csv` / `--no-csv` | Write results to `output/availability_<from>_<to>_<huts>.csv`. The output directory is created automatically (default: `--csv`) | 

Hut names can be partial; e.g. `vignettes` will match `Cabane des Vignettes CAS`. Name look up is case-insensitive and umlaut-tolerant (e.g. `schonbiel` or `schoenbiel` both match `Schönbielhütte SAC`). Quotes required for names with spaces (e.g. `"monte rosa"`). The default huts are some on the Haute Route: Dorée, Vignettes, Dix, Trient, Valsorey, Chanrion.

## Example

```
$ python hrs_tool.py --from_date 14.04.2026 --to_date 27.04.2026 --huts schonbiel dix trient "monte rosa" vignettes
Resolving huts (5):
  Schönbielhütte SAC (308)
  Cabane des Dix CAS (10)
  Cabane du Trient CAS (281)
  Monte Rosa Hütte SAC (6)
  Cabane des Vignettes CAS (226)
Fetching availability:
  Schönbielhütte SAC: done
  Cabane des Dix CAS: done
  Cabane du Trient CAS: done
  Monte Rosa Hütte SAC: done
  Cabane des Vignettes CAS: done
                          14/4  15/4  16/4  17/4  18/4  19/4  20/4  21/4  22/4  23/4  24/4  25/4  26/4  27/4
Hut                                                                                                         
Schönbielhütte SAC           4    12     6     0     0     0     0    20     0    34    26     7    29    26
Cabane des Dix CAS           0     0     0     0     0     4    26    31     7    45    22     0    53    53
Cabane du Trient CAS        68    67    67    48     0    60    51    77    71    73    77    35    68    84
Monte Rosa Hütte SAC         0     0     0     0     0     0     0     0     0     1     0     0     0     0
Cabane des Vignettes CAS     4     0     0     0     0    21    13     5     0     3     0     1    49    65

Saved to output/availability_20260414_20260427_308-10-281-6-226.csv
```

## Troubleshooting 
If a hut is not found, try writing it out in full. If it's not available on [hut-reservation.org](https://www.hut-reservation.org) at all, remove it from the list of huts to query. 
