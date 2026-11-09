"""
    If you want to run this yourself make sure to create a Cloudflare API token,
    and set it to have read radar permissions

    Also set UPDATE_FROM_API to True
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
COUNTRY_GRAPHS_DIR = OUT_DIR / "country-graphs"
ANALYSIS_DIR = OUT_DIR / "analysis"

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


def quartile_table(data):
    mean_bot = pd.Series(
        {
            cc: df["bot"].mean()
            for cc, df in data.items()
            if cc and "bot" in df.columns
        },
        name="mean_bot_usage",
    ).dropna()

    if mean_bot.empty:
        raise ValueError("No country bot usage data is available")

    quartile_labels = ["Low", "Medium-low", "Medium-high", "High"]
    table = mean_bot.sort_values().rename_axis("country_code").reset_index()
    table["category"] = pd.qcut(
        table["mean_bot_usage"].rank(method="first"),
        q=4,
        labels=quartile_labels,
    )

    table = (
        table.groupby("category", observed=False)
        .agg(
            country_codes=("country_code", lambda codes: ", ".join(sorted(codes))),
            country_count=("country_code", "count"),
            minimum_mean_bot_usage=("mean_bot_usage", "min"),
            maximum_mean_bot_usage=("mean_bot_usage", "max"),
        )
        .reset_index()
    )
    return table


def main():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    COUNTRY_GRAPHS_DIR.mkdir(parents=True, exist_ok=True)
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
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

    # country graphs
    for cc in COUNTRIES:
        df = data[cc]
        df.plot(
            kind="line",
            figsize=(8, 5),
            title=f"{cc} Human vs Bot HTTP Requests",
            color={"human": "orange", "bot": "blue"},
        )
        plt.ylabel("Percent of Max Requests")
        if (cc == ""): 
            cc = 'global'
        plt.savefig(COUNTRY_GRAPHS_DIR / f"{cc}.png", dpi=150)
        plt.close()

    # combined
    fig, ax = plt.subplots(figsize=(12, 7))
    for cc in COUNTRIES:
        if not cc:
            continue
        df = data.get(cc)
        if df is not None:
            line = ax.plot(df.index, df["bot"], label=cc, linewidth=0.8)[0]
            ax.annotate(
                cc,
                xy=(df.index[-1], df["bot"].iloc[-1]),
                xytext=(-4, 0),
                textcoords="offset points",
                color=line.get_color(),
                ha="right",
                va="center",
                fontsize="small",
            )
    ax.set_title("Bot HTTP Requests by Country")
    ax.set_ylabel("Percent of Max Requests")
    ax.set_xlabel("Time")
    ax.set_xlim(
        pd.Timestamp("2026-10-26", tz="UTC"),
        pd.Timestamp("2026-11-02", tz="UTC")
    )
    fig.tight_layout()
    fig.savefig(ANALYSIS_DIR / "all-countries-bot-usage.png", dpi=150)
    plt.close(fig)

    # table
    bot_usage_table = quartile_table(data)
    bot_usage_table.to_csv(
        ANALYSIS_DIR / "country-codes-by-bot-usage.csv",
        index=False,
    )
    print("\nCountry codes by bot usage:")
    print(bot_usage_table.to_string(index=False))

if __name__ == "__main__":
    main()