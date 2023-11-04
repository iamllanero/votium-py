from alive_progress import alive_bar
from dotenv import load_dotenv
from web3 import Web3
import csv
import json
import os
from snapshot import get_proposal
from votium.rounds import get_last_round, get_last_completed_round
from votium.events import get_events

load_dotenv()
WEB3_HTTP_PROVIDER = os.environ.get("WEB3_HTTP_PROVIDER")
w3 = Web3(Web3.HTTPProvider(WEB3_HTTP_PROVIDER))

SNAPSHOT_PROPOSALS_FILE = "output/snapshot/proposals.csv"
MAPPED_PROPOSALS_FILE = "output/incentives/proposals_mapped.csv"

VOTIUM1_ADDRESS = '0x19BBC3463Dd8d07f55438014b021Fb457EBD4595'
VOTIUM1_ABI = 'data/abis/votium1.json'

# Votium v2 starts round 53 (Sept 13, 2023)
VOTIUM2_ADDRESS = '0x63942E31E98f1833A234077f47880A66136a2D1e'
VOTIUM2_ABI = 'data/abis/votium2.json'

ERC20_ABI = 'data/abis/erc20.json'

GAUGES = 'data/gauges.json'

OUTPUT_DIR = "output/incentives"
os.makedirs(OUTPUT_DIR, exist_ok=True)

VOTIUM1_INCENTIVES = f"{OUTPUT_DIR}/votium1_incentives.csv"
VOTIUM2_INCENTIVES = f"{OUTPUT_DIR}/votium2_incentives.csv"

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
        timestamp = w3.eth.get_block(block_number)["timestamp"]
        BLOCK_TIME_MAP[block_number] = timestamp
        return timestamp


def get_gauge_score(proposal, gauge_address):
    gauge_name = GAUGE_MAP[gauge_address]
    for choice in proposal:
        if choice[0] == gauge_name:
            return gauge_name, choice[2]


def load_contract(abi, address) -> object:
    with open(abi) as f:
        abi = f.read()
    contract = w3.eth.contract(address=address, abi=abi)
    return contract


def get_mapped_proposals() -> list:
    """Map the proposal_id from Snapshot to the Votium Event proposal_id."""

    if os.path.exists(MAPPED_PROPOSALS_FILE):
        with open(MAPPED_PROPOSALS_FILE, "r") as f:
            reader = csv.reader(f)
            next(reader)
            proposals = list(reader)
        return proposals

    proposals = [[
        "round",
        "start",
        "end",
        "id",
        "title",
        "keccak_id",
    ]]

    with open(SNAPSHOT_PROPOSALS_FILE) as f:
        reader = csv.reader(f)
        next(reader)
        proposals = list(reader)

    mapped_proposals = []
    for proposal in proposals:
        proposal_id = proposal[3]
        if proposal_id.startswith("0x"):
            keccak_id = w3.keccak(hexstr=proposal_id)
        else:
            keccak_id = w3.keccak(text=proposal_id)
        mapped_proposals.append([
            proposal[0],
            proposal[1],
            proposal[2],
            proposal[3],
            proposal[4],
            keccak_id.hex(),
        ])

    with open(MAPPED_PROPOSALS_FILE, "w") as f:
        writer = csv.writer(f)
        writer.writerow([
            "round",
            "start",
            "end",
            "id",
            "title",
            "keccak_id",
        ])
        writer.writerows(mapped_proposals)

    return mapped_proposals


def get_incentives(round) -> dict:
    """Get the incentives for a given round."""

    file_path = f"{OUTPUT_DIR}/round_{round}_incentives.csv"
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            reader = csv.DictReader(f)
            incentives = list(reader)
        return incentives
    else:
        return None


def get_incentive_events_v1(mapped_proposals, initiated, bribed):
    with alive_bar(52) as bar:
        bar.title("Building Votium v1")
        for round in range(1, 53):
            bar()
            bar.text(f"Round {round}")

            # Check if output already exists
            file_path = f"{OUTPUT_DIR}/round_{round}_incentives.csv"
            if os.path.exists(file_path):
                continue

            proposal = get_proposal(round)
            proposal_id = [
                p for p in mapped_proposals if p[0] == str(round)][0][5]
            events = [b for b in bribed if b[0] == proposal_id[2:]]
            incentives = []
            for e in events:
                choice_index = int(e[3]) - 1
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
                    "score",
                ])
                writer.writerows(incentives)


def get_incentive_events_v2(new_incentives):
    """Get all NewIncentive events for Votium v2."""

    with alive_bar(int(get_last_round()) - 52) as bar:
        bar.title("Building Votium v2")
        for round in range(53, get_last_round() + 1):
            bar()
            print(f"Round {round}")
            bar.text(f"Round {round}")

            # Check if output already exists
            file_path = f"{OUTPUT_DIR}/round_{round}_incentives.csv"
            if os.path.exists(file_path):
                continue

            proposal = get_proposal(round)
            incentives = []
            events = [e for e in new_incentives if e[0] == str(round)]
            for e in events:
                gauge_address = e[1]
                (gauge, score) = get_gauge_score(proposal, gauge_address)
                token_address = e[4]
                token_symbol, token_name = get_token(token_address)
                amount = e[5]
                transaction_hash = e[12]
                block_hash = e[14]
                block_number = e[15]
                timestamp = get_block_time(block_number)
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
                    "score",
                ])
                writer.writerows(incentives)


def main():
    """Get the incentives for all rounds."""

    with alive_bar(4) as bar:
        bar.title("Gathering data    ")

        bar()
        print("Mapping all Snapshot proposal IDs to Event proposal IDs")
        mapped_proposals = get_mapped_proposals()

        bar()
        print("Getting all Initiated events from Votium v1")
        initiated = get_events(
            VOTIUM1_ABI,
            VOTIUM1_ADDRESS,
            "Initiated",
            start_block=13209937,  # Contract deployed at 13209937
            end_block=18043767-1  # One less starting block for Votium v2
        )

        bar()
        print("Getting all Bribed events from Votium v1")
        bribed = get_events(
            VOTIUM1_ABI,
            VOTIUM1_ADDRESS,
            "Bribed",
            start_block=13209937,  # Contract deployed at 13209937
            end_block=18043767-1  # One less starting block for Votium v2
        )

        bar()
        print("Getting all NewIncentive events from Votium v2")
        new_incentives = get_events(
            VOTIUM2_ABI,
            VOTIUM2_ADDRESS,
            "NewIncentive",
            start_block=18043767,  # Starting block for Votium v2
            end_block=w3.eth.block_number
        )

    get_incentive_events_v1(mapped_proposals, initiated, bribed)

    get_incentive_events_v2(new_incentives)


if __name__ == "__main__":
    main()
