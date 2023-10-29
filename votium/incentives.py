from alive_progress import alive_bar
from dotenv import load_dotenv
from web3 import Web3
import csv
import json
import os
import snapshot
import votium.rounds as rounds

load_dotenv()
WEB3_HTTP_PROVIDER = os.environ.get("WEB3_HTTP_PROVIDER")
w3 = Web3(Web3.HTTPProvider(WEB3_HTTP_PROVIDER))

VOTIUM1_ADDRESS = '0x19BBC3463Dd8d07f55438014b021Fb457EBD4595'
VOTIUM1_ABI = 'data/abis/votium1.json'

VOTIUM2_ADDRESS = '0x63942E31E98f1833A234077f47880A66136a2D1e'
VOTIUM2_ABI = 'data/abis/votium2.json'

ERC20_ABI = 'data/abis/erc20.json'

GAUGES = 'data/gauges.json'

OUTPUT_DIR = "output/incentives/"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def load_contract(abi, address):
    with open(abi) as f:
        abi = f.read()
    contract = w3.eth.contract(address=address, abi=abi)
    return contract


def get_incentive_v1(round, start_block, end_block):
    proposal = snapshot.get_proposal(round)
    votium = load_contract(VOTIUM1_ABI, VOTIUM1_ADDRESS)
    event_filter = votium.events.Bribed().create_filter(
        fromBlock=start_block, toBlock=end_block)
    bribe_log = event_filter.get_all_entries()
    bribes = []
    for event in bribe_log:
        token = event["args"]["_token"]
        erc20_contract = load_contract(ERC20_ABI, token)
        token_symbol = erc20_contract.functions.symbol().call()
        token_name = erc20_contract.functions.name().call()
        amount = event["args"]["_amount"]
        choice_index = event["args"]["_choiceIndex"]
        choice_name = proposal["data"]["proposal"]["choices"][choice_index-1]
        block_hash = event["blockHash"].hex()
        block_number = event["blockNumber"]
        timestamp = w3.eth.get_block(block_number)["timestamp"]
        bribes.append([
            choice_name,
            amount,
            token_symbol,
            timestamp,
            token,
            token_name,
            choice_index,
            block_hash,
            block_number,
        ])
    return bribes


def get_incentive_v2(start_block, end_block):
    with open(GAUGES) as f:
        gauges = json.load(f)
    votium = load_contract(VOTIUM2_ABI, VOTIUM2_ADDRESS)
    event_filter = votium.events.NewIncentive().create_filter(
        fromBlock=start_block, toBlock=end_block)
    events = event_filter.get_all_entries()
    bribes = []
    for event in events:
        token = event["args"]["_token"]
        erc20_contract = load_contract(ERC20_ABI, token)
        token_symbol = erc20_contract.functions.symbol().call()
        token_name = erc20_contract.functions.name().call()
        amount = event["args"]["_amount"]
        choice_index = event["args"]["_gauge"]
        choice_name = gauges["gauges"][choice_index]["shortName"]
        block_hash = event["blockHash"].hex()
        block_number = event["blockNumber"]
        timestamp = w3.eth.get_block(block_number)["timestamp"]
        bribes.append([
            choice_name,
            amount,
            token_symbol,
            timestamp,
            token,
            token_name,
            choice_index,
            block_hash,
            block_number
        ])
    return bribes


def get_incentive(round):
    """Get the incentives for a given round."""

    # Check for existing file
    file_path = OUTPUT_DIR + f"round_{round}_incentives.csv"
    if os.path.exists(file_path) and \
        round <= rounds.get_last_completed_round():
        with open(file_path, "r") as f:
            f.readline() # Skip header
            reader = csv.reader(f)
            incentives = list(reader)
        return incentives


    # Get from onchain
    print(f"Fetching incentives for round {round}...")

    # Get start block
    proposal = snapshot.get_proposal(round)
    start_block = proposal["data"]["proposal"]["snapshot"]

    # Get end block
    if round < rounds.get_last_round():
        proposal = snapshot.get_proposal(round+1)
        end_block = proposal["data"]["proposal"]["snapshot"]
    else:
        end_block = w3.eth.block_number

    if round < 53:
        incentives = get_incentive_v1(round, start_block, end_block)
    else:
        incentives = get_incentive_v2(start_block, end_block)
    

    # Save as CSV
    with open(file_path, "w") as f:
        writer = csv.writer(f)
        writer.writerow([
            "gauge", 
            "amount", 
            "token_symbol", 
            "timestamp",
            "token",
            "token_name",
            "gauge_ref", 
            "block_hash", 
            "block_number", 
        ])
        writer.writerows(incentives)

    return incentives



def main():
    """Get the incentives for all rounds."""

    with alive_bar(rounds.get_last_round()) as bar:
        for round in range(1, rounds.get_last_round()+1):
            bar()
            bar.text(f"Round {round}")
            incentives = get_incentive(round)


if __name__ == "__main__":
    main()


