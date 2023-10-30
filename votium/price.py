from alive_progress import alive_bar
from votium import rounds
import requests
import snapshot
import incentives
import csv
import os

OUTPUT_DIR = "output/price"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# Tokens that are missing / need to use coingecko
MANUAL_PRICES = {
    "USDM:1634232288": "1.0",
    "USDM:1635553502": "1.0",
    "LUNA:1638166693": "49.97057261602858",
    "LUNA:1639194085": "61.032431508730056",
    "LUNA:1640219788": "85.53254278439978",
    "LUNA:1640219878": "85.53254278439978",
    "LUNA:1641603266": "68.88043797219528",
    "LUNA:1642820274": "64.39269522104948",
    "LUNA:1642933760": "62.60645063584536",
    "T:1643032930": "0.08858019868648463",
    "LUNA:1643856451": "47.722832144087256",
    "LUNA:1644191725": "55.48483663183234",
    "LUNA:1645316587": "50.50251006449115",
    "LUNA:1645320009": "50.50251006449115",
    "APEFI:1670471615": "0.003379061468807522",
    "sdFXS:1681663955": "10.246017123185558",
    "sdFXS:1691400455": "6.475601695530601",
    "sdFXS:1692603575": "6.04753134843985",
    "sdFXS:1693817279": "5.422331650380933",
}

def price_round(round):
    """Get a round"""

    file_path = f"{OUTPUT_DIR}/round_{round}_price.csv"
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            f.readline()
            reader = csv.reader(f)
            return list(reader)
    
    rv = snapshot.get_snapshot(round)
    ri = incentives.get_incentive(round)

    prices = []
    for i in ri:
        (gauge, amount, token_symbol, timestamp, token, token_name, choice_index, block_hash, block_number) = i

        if token_symbol in ['USDC', 'UST', 'LUNA']:
            amount = float(amount) / 1e6
        elif token_symbol in ['EURS']:
            amount = float(amount) / 1e2
        else:
            amount = float(amount) / 1e18

        # Get votes for the gauge
        votes = 0
        for v in rv:
            # print(v)
            (v_gauge, v_choice_index, v_votes, v_pct_votes) = v
            if v_gauge == gauge:
                votes += float(v_votes)

        # Check / get price from manual prices
        if f"{token_symbol}:{timestamp}" in MANUAL_PRICES:

            price = MANUAL_PRICES[f"{token_symbol}:{timestamp}"]
            usd_value = float(amount) * float(price)
            per_vote = usd_value / votes if votes != 0 else 0

        else:

            # Get price from defillama
            url = f"https://coins.llama.fi/prices/historical/{timestamp}/ethereum:{token}"
            response = requests.get(url)
            if response.status_code == 200:
                json = response.json()
                if "coins" in json and f"ethereum:{token}" in json["coins"]:
                    price = response.json()["coins"][f"ethereum:{token}"]["price"]
                    usd_value = float(amount) * float(price)
                    per_vote = usd_value / votes if votes != 0 else 0
                else:
                    print(f"{round}-{gauge}: Missing {token_symbol} {timestamp}")
                    price = 'MISSING'
                    usd_value = 'MISSING'
                    per_vote = 'MISSING'
            else:
                print(f"{round}-{gauge}: Error {response.status_code}")
                price = 'ERROR'
                usd_value = 'ERROR'
                per_vote = 'ERROR'

        prices.append([
            gauge,
            amount,
            token_symbol,
            price,
            usd_value,
            votes,
            token,
            token_name,
            per_vote
        ])

    # Save to CSV file
    with open(file_path, "w") as f:
        writer = csv.writer(f)
        writer.writerow([
            "gauge",
            "amount",
            "token_symbol",
            "token_price",
            "usd_value",
            "votes",
            "token",
            "token_name",
            "per_vote",
        ])
        writer.writerows(prices)

def main():

    with alive_bar(rounds.get_last_round()) as bar:
        for round in range(1, rounds.get_last_round()+1):
            bar()
            bar.text(f"Round {round}")
            price_round(round)


if __name__ == "__main__":
    main()