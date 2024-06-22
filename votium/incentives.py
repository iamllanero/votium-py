from dotenv import load_dotenv
from snapshot import get_snapshot
from votium.events import get_events
from votium.rounds import get_last_round
from web3 import Web3
import csv
import json
import os

load_dotenv()
WEB3_HTTP_PROVIDER = os.environ.get("WEB3_HTTP_PROVIDER")
w3 = Web3(Web3.HTTPProvider(WEB3_HTTP_PROVIDER))

SNAPSHOT_LIST_FILE = "output/snapshot/snapshot_list.csv"
SNAPSHOT_LIST_MAPPED_FILE = "output/incentives/snapshot_list_mapped.csv"

VOTIUM1_ADDRESS = '0x19BBC3463Dd8d07f55438014b021Fb457EBD4595'
VOTIUM1_ABI = 'data/abis/votium1.json'

# Votium v2 starts round 53 (Sept 13, 2023)
VOTIUM2_ADDRESS = '0x63942E31E98f1833A234077f47880A66136a2D1e'
VOTIUM2_ABI = 'data/abis/votium2.json'

ERC20_ABI = 'data/abis/erc20.json'

GAUGES = 'data/gauges.json'

OUTPUT_DIR = "output/incentives"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# VOTIUM1_INCENTIVES = f"{OUTPUT_DIR}/votium1_incentives.csv"
# VOTIUM2_INCENTIVES = f"{OUTPUT_DIR}/votium2_incentives.csv"
VOTIUM2_EVENT_FILE = "cache/events/0x63942E31E98f1833A234077f47880A66136a2D1e-NewIncentive.csv"

TOKEN_MAP = {}
BLOCK_TIME_MAP = {}
GAUGE_MAP = {}

with open(GAUGES) as f:
    json = json.load(f)
    for key, value in json["gauges"].items():
        GAUGE_MAP[key] = value["shortName"]


def get_token(token_address) -> tuple:
    """Get the token name and symbol from the token address."""

    if token_address in TOKEN_MAP:
        return TOKEN_MAP[token_address]
    else:
        erc20_contract = load_contract(ERC20_ABI, token_address)
        token_symbol = erc20_contract.functions.symbol().call()
        token_name = erc20_contract.functions.name().call()
        TOKEN_MAP[token_address] = [token_symbol, token_name]

        return token_symbol, token_name


def get_block_time(block_number) -> int:
    """Get the timestamp for a given block number."""

    if block_number in BLOCK_TIME_MAP:
        return BLOCK_TIME_MAP[block_number]
    else:
        # print(block_number)
        # print(type(block_number))
        block = w3.eth.get_block(int(block_number))
        # print(block)
        timestamp = block["timestamp"]
        BLOCK_TIME_MAP[block_number] = timestamp
        return timestamp


def get_gauge_score(snapshot, gauge_address):
    gauge_name = GAUGE_MAP[gauge_address]
    if snapshot is not None:
        for choice in snapshot:
            if choice[0] == gauge_name:
                return gauge_name, choice[2]

    return gauge_name, 0


def load_contract(abi, address) -> object:
    with open(abi) as f:
        abi = f.read()
    contract = w3.eth.contract(address=address, abi=abi)
    return contract


def get_snapshot_list_map() -> list:
    """Map the proposal_id from Snapshot to the Votium Event proposal_id."""

    # if os.path.exists(MAPPED_SNAPSHOTS_FILE):
    #     with open(MAPPED_SNAPSHOTS_FILE, "r") as f:
    #         reader = csv.reader(f)
    #         next(reader)
    #         proposals = list(reader)
    #     return proposals

    snapshot_list = [[
        "round",
        "start",
        "end",
        "id",
        "title",
    ]]

    with open(SNAPSHOT_LIST_FILE) as f:
        reader = csv.reader(f)
        next(reader)
        snapshot_list = list(reader)

    snapshot_list_map = []
    for snapshot in snapshot_list:
        snapshot_id = snapshot[3]
        if snapshot_id.startswith("0x"):
            keccak_id = w3.keccak(hexstr=snapshot_id)
        else:
            keccak_id = w3.keccak(text=snapshot_id)
        snapshot_list_map.append([
            snapshot[0],
            snapshot[1],
            snapshot[2],
            snapshot[3],
            snapshot[4],
            keccak_id.hex(),
        ])

    with open(SNAPSHOT_LIST_MAPPED_FILE, "w") as f:
        writer = csv.writer(f)
        writer.writerow([
            "round",
            "start",
            "end",
            "id",
            "title",
            "keccak_id",
        ])
        writer.writerows(snapshot_list_map)

    return snapshot_list_map


def get_incentives(round) -> list:
    """Get the incentives for a given round."""

    file_path = f"{OUTPUT_DIR}/round_{round:03d}_incentives.csv"
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            reader = csv.reader(f)
            next(reader)
            incentives = list(reader)
        return incentives
    else:
        return None


def process_incentive_events_v1(snapshot_list_map, initiated, bribed):
    for round in range(1, 53):

        # Check if output already exists
        file_path = f"{OUTPUT_DIR}/round_{round:03d}_incentives.csv"
        if os.path.exists(file_path):
            print(f"Using cached {file_path}")
            continue

        print(f"Processing round {round} incentives in {file_path}")
        proposal = get_snapshot(round)
        proposal_id = [
            p for p in snapshot_list_map if p[0] == str(round)][0][5]
        events = [b for b in bribed if b[0] == proposal_id[2:]]
        incentives = []
        for e in events:
            choice_index = int(e[3])
            gauge = proposal[choice_index][0]
            token_address = e[1]
            token_symbol, token_name = get_token(token_address)
            amount = e[2]
            transaction_hash = e[7]
            block_hash = e[9]
            block_number = e[10]
            timestamp = get_block_time(block_number)
            score = proposal[choice_index][2]
            incentives.append([
                gauge,
                amount,
                token_symbol,
                timestamp,
                token_address,
                token_name,
                transaction_hash,
                block_hash,
                block_number,
                score,
            ])

        # Save as CSV
        with open(file_path, "w") as f:
            writer = csv.writer(f)
            writer.writerow([
                "gauge",
                "amount",
                "token_symbol",
                "timestamp",
                "token_address",
                "token_name",
                "transaction_hash",
                "block_hash",
                "block_number",
                "unadj_score",
            ])
            writer.writerows(incentives)


def process_incentive_events_v2():
    """Create incentive CSV files based on Votium v2 NewIncentive."""

    with open(VOTIUM2_EVENT_FILE) as f:
        reader = csv.reader(f)
        next(reader)
        incentives = list(reader)

    # Get the max round in the incentives file
    max_round = max([int(row[0]) for row in incentives])  # Assuming _round is in the first column
    print(f"Max round: {max_round}")

    # Process the incentives for each round
    for round in range(53, max_round + 1):
        file_path = f"{OUTPUT_DIR}/round_{round:03d}_incentives.csv"

        if os.path.exists(file_path):
            print(f"Using cached {file_path}")
            continue

        print(f"Processing round {round} to {file_path}")
        last_round = get_last_round()
        if round < int(last_round) + 1:
            snapshot = get_snapshot(round)
        else:
            snapshot = None
        # Filter to relevant events for the round
        events = [e for e in incentives if e[0] == str(round)]
        round_incentives = []
        for event in events:
            gauge, score = get_gauge_score(snapshot, event[1])
            token_symbol, token_name = get_token(event[4])
            round_incentives.append([
                gauge,  # gauge
                event[5],  # amount
                token_symbol,  # token_symbol
                get_block_time(event[15]),  # timestamp
                event[4],  # token_address
                token_name,  # token_name
                event[12],  # transaction_hash
                event[14],  # block_hash
                event[15],  # block_number
                score,  # unadj_score
            ])
        with open(file_path, "w") as f:
            writer = csv.writer(f)
            writer.writerow(['gauge',
            'amount',
            'token_symbol',
            'timestamp',
            'token_address',
            'token_name',
            'transaction_hash',
            'block_hash',
            'block_number',
            'unadj_score'])
            writer.writerows(round_incentives)


def main():
    """Get the incentives for all rounds."""

    # TODO Delete incentive cache files for the current round and beyond
    current_round = get_last_round()
    print(f"Current round: {current_round}")
    cache_files = os.listdir(OUTPUT_DIR)
    for f in cache_files:
        if f.startswith("round_") and f.endswith("_incentives.csv"):
            round = int(f.split("_")[1])
            if round >= int(current_round):
                print(f"Deleting {f}")
                os.remove(f"{OUTPUT_DIR}/{f}")

    print("Mapping all Snapshot proposal IDs to Event proposal IDs")
    snapshot_list_map = get_snapshot_list_map()

    print("Getting all Initiated events from Votium v1")
    initiated = get_events(
        VOTIUM1_ABI,
        VOTIUM1_ADDRESS,
        "Initiated",
        start_block=13209937,  # Contract deployed at 13209937
        end_block=18043767-1  # One less starting block for Votium v2
    )

    print("Getting all Bribed events from Votium v1")
    bribed = get_events(
        VOTIUM1_ABI,
        VOTIUM1_ADDRESS,
        "Bribed",
        start_block=13209937,  # Contract deployed at 13209937
        end_block=18043767+20000  # 10K past starting block for Votium v2
    )

    process_incentive_events_v1(snapshot_list_map, initiated, bribed)

    print("Getting all NewIncentive events from Votium v2")
    new_incentives = get_events(
        VOTIUM2_ABI,
        VOTIUM2_ADDRESS,
        "NewIncentive",
        start_block=18043767,  # Starting block for Votium v2
        end_block=w3.eth.block_number
    )

    process_incentive_events_v2()


if __name__ == "__main__":
    main()
