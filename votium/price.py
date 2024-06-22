import csv
import os
from collections import defaultdict

import requests
from incentives import get_incentives
from incentives import main as incentives_main
from snapshot import get_snapshot

from votium.rounds import get_current_round, get_last_round

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
    "xETH:1705845467": "1.32",
    "xETH:1709526839": "2.77",
    "SPELL:1711647035": "0.00126146",
    "ALCX:1711698179": "34.33",
    "TXJP:1712817803": "80.72",
    "FXS:1713139895": "5.16",
    "FXS:1713163667": "5.16",
    "FXS:1713164243": "5.16",
    "FXS:1713165731": "5.16",
    "FXS:1713201047": "4.92",
    "TXJP:1714020371": "81.22",
    "TXJP:1715315723": "68.77",
    "TXJP:1716684239": "83.52",
    "sdFXS:1717853147": "4.54",
    "TXJP:1717900079": "79.75",
    "TXJP:1719030383": "71.49",
}


def price_round(round):
    """Get a round"""

    file_path = f"{OUTPUT_DIR}/round_{round:03d}_price.csv"
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            reader = csv.reader(f)
            next(reader)
            print(f"Using {file_path} as it already exists")
            return list(reader)

    snapshot = get_snapshot(round)

    # Get the total votes
    total_score = sum([x[2] for x in snapshot])
    print(f"Total score in snapshot: {total_score}")

    incentives = get_incentives(round)

    # Get the votes and adjust split across gauges
    # Get the number of incentive deposits for each gauge
    incentive_deposits = defaultdict(int)
    for i in incentives:
        # gauge,amount,token_symbol,timestamp,token_address,token_name,transaction_hash,block_hash,block_number,unadj_score
        (
            gauge,
            amount,
            token_symbol,
            timestamp,
            token_address,
            token_name,
            transaction_hash,
            block_hash,
            block_number,
            unadj_score,
        ) = i
        incentive_deposits[gauge] += 1

    prices = []
    total_score = 0
    for i in incentives:
        (
            gauge,
            amount,
            token_symbol,
            timestamp,
            token_address,
            token_name,
            transaction_hash,
            block_hash,
            block_number,
            unadj_score,
        ) = i

        if token_symbol in ["USDC", "UST", "LUNA", "PYUSD"]:
            amount = float(amount) / 1e6
        elif token_symbol in ["EURS"]:
            amount = float(amount) / 1e2
        else:
            amount = float(amount) / 1e18

        # Get votes for the gauge
        if unadj_score == 0:
            score = 0.0
        else:
            score = float(unadj_score) / incentive_deposits[gauge]

        # Check / get price from manual prices
        if f"{token_symbol}:{timestamp}" in MANUAL_PRICES:
            price = MANUAL_PRICES[f"{token_symbol}:{timestamp}"]
            usd_value = float(amount) * float(price)
            per_vote = usd_value / score if score != 0 else 0

        else:
            # Get price from defillama
            url = f"https://coins.llama.fi/prices/historical/{timestamp}/ethereum:{token_address}"
            response = requests.get(url)
            if response.status_code == 200:
                json = response.json()
                if "coins" in json and f"ethereum:{token_address}" in json["coins"]:
                    price = response.json()["coins"][f"ethereum:{token_address}"][
                        "price"
                    ]
                    usd_value = float(amount) * float(price)
                    per_vote = usd_value / score if score != 0 else 0
                else:
                    print(f"{round}-{gauge}: Missing {token_symbol} {timestamp}")
                    price = "MISSING"
                    usd_value = "MISSING"
                    per_vote = "MISSING"
            else:
                print(f"{round}-{gauge}: Error {response.status_code}")
                price = "ERROR"
                usd_value = "ERROR"
                per_vote = "ERROR"

        prices.append(
            [
                gauge,
                amount,
                token_symbol,
                price,
                usd_value,
                score,
                token_address,
                token_name,
                per_vote,
                transaction_hash,
                block_hash,
                block_number,
            ]
        )

    # Save to CSV file
    with open(file_path, "w") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "gauge",
                "amount",
                "token_symbol",
                "token_price",
                "usd_value",
                "score",
                "token",
                "token_name",
                "per_vote",
                "transaction_hash",
                "block_hash",
                "block_number",
            ]
        )
        writer.writerows(prices)

    print(f"Round {round} - Total votes: {total_score}")


def main():
    # Check if there is a current round
    current_round = get_current_round()
    if current_round is not None:
        round_file = f"{OUTPUT_DIR}/round_{current_round:03d}_price.csv"
        print(f"Current round: {current_round}.")
        try:
            os.remove(round_file)
            print(f"Deleted {round_file}.")
        except OSError as e:
            print(f"Error: {e}")

    # incentives_main()

    for round in range(1, get_last_round() + 1):
        print(f"Pricing round {round}")
        price_round(round)


if __name__ == "__main__":
    main()
