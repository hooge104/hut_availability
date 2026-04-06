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
| `--country` | Country in which hut should be located |
| `--altitude_min` | Minimum altitude at which the hut should be located (optional) |
| `--altitude_max` | Minimum altitude at which the hut should be located (optional) |

Use either the argument(s) `--country` or `--huts`. Arguments `--region`, `--altitude_min` and `--altitude_max` are optional and currently only available for CH.
Regions can be individual cantons, or `central` (LU, OW, NW, SZ, UR, ZG), `east` (AI, AR, GL, GR, SG) and `west` (FR, JU, VD, VS). 

If used, `--huts` should always be last. Hut names can be partial; e.g. `vignettes` will match `Cabane des Vignettes CAS`. Name look up is case-insensitive and umlaut-tolerant (e.g. `schonbiel` or `schoenbiel` both match `Schönbielhütte SAC`). Quotes required for names with spaces (e.g. `"monte rosa"`). 


## Examples

```
$ python hrs_tool.py --from_date 14.04.2026 --to_date 27.04.2026 --huts schonbiel dix trient "monte rosa" vignettes
Resolving huts by name (5):
Resolved 5 hut(s)
Fetching availability:
  Schönbielhütte SAC: done
  Cabane des Dix CAS: done
  Cabane du Trient CAS: done
  Monte Rosa Hütte SAC: done
  Cabane des Vignettes CAS: done
                          14/4  15/4  16/4  17/4  18/4  19/4  20/4  21/4  22/4  23/4  24/4  25/4  26/4  27/4
Hut                                                                                                         
Schönbielhütte SAC           0     0     0     0     0     0     8    20     5    34    26     8    25    26
Cabane des Dix CAS           5     7     0     0     0     0    26    31    14    57    25     4    51    50
Cabane du Trient CAS        73    72    72    52     0    65    56    82    71    79    80    36    72    89
Cabane des Vignettes CAS     6     5    12     0     0    17    16     3     0     7     0     0    49    64
Monte Rosa Hütte SAC         0     0     0     0     0     0     0     0     0     0     0     0     0     0

Saved to output/availability_20260414_20260427_308-10-281-6-226.csv
```
```
python hrs_tool.py --from_date 14.04.2026 --to_date 16.04.2026 --country ch --region west --altitude_min 2700
Discovering Swiss huts', region='west', alt≥2700.0m …
  Using swisstopo API to find Swiss huts …
  swisstopo found 27 candidate hut location(s):
Resolved 11 hut(s):
Fetching availability:
  Cabane des Dix CAS: done
  Cabane de l'A Neuve CAS: done
  Cabane Arpitettaz CAS: done
  Cabane de la Dent Blanche CAS: done
  Bivouac de l'Envers des Dorées: done
  Cresta-Biwak SAC: done
  Fusshornbiwak: done
  Aarbiwak SAC: done
  Mischabeljochbiwak SAC: done
  Arbenbiwak SAC: done
  Schalijochbiwak SAC: done

                                14/4  15/4  16/4
Hut                                             
Cabane des Dix CAS                 5     7     0
Cabane de l'A Neuve CAS            0     0     0
Cabane Arpitettaz CAS              0     3     1
Cabane de la Dent Blanche CAS      0     0     0
Bivouac de l'Envers des Dorées    13    18    13
Cresta-Biwak SAC                   6     6     6
Fusshornbiwak                      8     8     8
Aarbiwak SAC                      10     8     7
Mischabeljochbiwak SAC            24    24    24
Arbenbiwak SAC                    15    15    12
Schalijochbiwak SAC                8     8     8

Saved to output/availability_20260414_20260416_ch_west_min2700m.csv
```

## Troubleshooting 
If a hut is not found, try writing it out in full. If it's not available on [hut-reservation.org](https://www.hut-reservation.org) at all, remove it from the list of huts to query. 
