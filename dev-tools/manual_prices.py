import requests
import datetime

MISSING = [
    ('sdFXS', 1681663955),
    ('sdFXS', 1691400455),
    ('sdFXS', 1692603575),
    ('sdFXS', 1693817279)
]

coin_map = {
    "usdm": "usd-mars",
    "luna": "terra-luna",
    "t": "threshold-network-token",
    "apefi": "ape-finance",
    "sdfxs": "frax-share",
}

def fetch(symbol, timestamp):
    coin_id = coin_map[symbol.lower()]
    date_str = datetime.datetime.utcfromtimestamp(timestamp).strftime('%d-%m-%Y')
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/history?date={date_str}&localization=false"
    response = requests.get(url)
    if response.status_code == 200:
        json = response.json()
        if "market_data" in json:
            price = json["market_data"]["current_price"]["usd"]
        else:
            price = f"MISSING {response.text}"
    else:
        price = f"ERROR {response.status_code}"

    return price

print("MANUAL_PRICES={")
for (symbol, timestamp) in MISSING:
    price = fetch(symbol, timestamp)
    print(f'    "{symbol}:{timestamp}":"{price}",')
print("}")