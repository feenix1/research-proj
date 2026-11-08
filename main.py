"""
    If you want to run this yourself make sure to create a Cloudflare API token,
    set it to have read radar permissions, then do:

    pip install cloudflare pandas matplotlib
    export CLOUDFLARE_API_TOKEN="..."
"""

import os
import time
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd
from cloudflare import Cloudflare

DATE_START = "2026-10-05T00:00:00Z"
DATE_END = "2026-11-02T00:00:00Z"
AGG_INTERVAL = "1h"

UPDATE_FROM_API = False

COUNTRIES = [
    "US", "CA", "MX", "BR", "AR", "CL", "CO", "PE",
    "GB", "IE", "FR", "DE", "ES", "IT", "NL", "SE", "PL", "UA", "TR", "RU", "GR", "RO", 
    "EG", "SA", "AE", "IL", "IR", "PK",
    "NG", "ZA", "KE", "MA",
    "IN", "BD", "ID", "TH", "VN", "PH", "MY",
    "CN", "JP", "KR", "AU", "NZ",  
    "" # global
]

OUT_DIR = Path("data")
CACHE_DIR = OUT_DIR / "cache"  
GRAPHS_DIR = OUT_DIR / "country-graphs"

def label_columns(cols):
    mapping = {}
    for c in cols:
        print(c)
        if c == "timestamps":
            continue
        lc = c.lower()
        if "human" in lc:
            mapping[c] = "human"
        elif "bot" in lc or "auto" in lc:
            mapping[c] = "bot"
    if sorted(mapping.values()) != ["bot", "human"]:
        raise ValueError(f"Could not identify bot/human columns in {list(cols)}")
    return mapping

def fetch_country(client, cc):
    cache = CACHE_DIR / f"{cc}.csv"

    if cache.exists() and not UPDATE_FROM_API:
        return pd.read_csv(cache, index_col=0, parse_dates=True)

    response = client.radar.http.timeseries_groups_v2(
        dimension="BOT_CLASS",
        agg_interval=AGG_INTERVAL,
        date_start=[DATE_START],
        date_end=[DATE_END],
        location=[cc],
        normalization="MIN0_MAX",  # both series scaled by max
    )
    data = response.to_dict()

    # just in case? not sure if will happen but good to know
    norm = data["meta"].get("normalization")
    if norm != "MIN0_MAX":
        print(f"  warning: {cc} came back with normalization={norm}")

    df = pd.DataFrame(data["serie_0"])
    df["timestamps"] = pd.to_datetime(df["timestamps"], utc=True)
    df = df.rename(columns={"timestamps": "timestamp"}).set_index("timestamp")
    df = df.apply(pd.to_numeric, errors="coerce")
    df = df.rename(columns=label_columns(df.columns))

    df.to_csv(cache)
    return df


def main():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    GRAPHS_DIR.mkdir(parents=True, exist_ok=True)
    client = Cloudflare(api_token=os.environ.get("CLOUDFLARE_API_TOKEN"))

    data = {}
    failed = []
    for cc in COUNTRIES:
        print(f"Fetching {cc}")
        try:
            df = fetch_country(client, cc)
            data[cc] = df
        except Exception as e:
            print(f"  failed: {e}")
            failed.append(cc)
            continue

    if (UPDATE_FROM_API):
        time.sleep(0.5) 

    # graph
    for cc in COUNTRIES:
        df = data[cc]
        df.plot(kind="line", figsize=(8, 5), title=f"{cc} Human vs Bot HTTP Requests")
        plt.ylabel("Percent of Max Requests")
        if (cc == ""): 
            cc = 'global'
        plt.savefig(GRAPHS_DIR / f"{cc}.png", dpi=150)
        plt.close()

if __name__ == "__main__":
    main()