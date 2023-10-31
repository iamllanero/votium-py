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

OUTPUT_DIR = "output/incentives"
os.makedirs(OUTPUT_DIR, exist_ok=True)

VOTIUM2_INCENTIVES = f"{OUTPUT_DIR}/votium2_incentives.csv"

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


# def get_incentive_v2(start_block, end_block):
#     with open(GAUGES) as f:
#         gauges = json.load(f)
#     votium = load_contract(VOTIUM2_ABI, VOTIUM2_ADDRESS)
#     event_filter = votium.events.NewIncentive().create_filter(
#         fromBlock=start_block, toBlock=end_block)
#     events = event_filter.get_all_entries()
#     bribes = []
#     for event in events:
#         token = event["args"]["_token"]
#         erc20_contract = load_contract(ERC20_ABI, token)
#         token_symbol = erc20_contract.functions.symbol().call()
#         token_name = erc20_contract.functions.name().call()
#         amount = event["args"]["_amount"]
#         choice_index = event["args"]["_gauge"]
#         choice_name = gauges["gauges"][choice_index]["shortName"]
#         block_hash = event["blockHash"].hex()
#         block_number = event["blockNumber"]
#         timestamp = w3.eth.get_block(block_number)["timestamp"]
#         bribes.append([
#             choice_name,
#             amount,
#             token_symbol,
#             timestamp,
#             token,
#             token_name,
#             choice_index,
#             block_hash,
#             block_number
#         ])
#     return bribes

def get_incentive_v2(round):

    with open(GAUGES) as f:
        gauges = json.load(f)

    with open(VOTIUM2_INCENTIVES, "r") as f:
        f.readline()
        reader = csv.reader(f)
        incentives = list(reader)

    # _round,_gauge,_depositor,_index,_token,_amount,_maxPerVote,_excluded,_recycled,event,logIndex,transactionIndex,transactionHash,address,blockHash,blockNumber
    # Filter to round
    incentives = [i for i in incentives if i[0] == str(round)]

    bribes = []
    for incentive in incentives:
        token = incentive[4]
        erc20_contract = load_contract(ERC20_ABI, token)
        token_symbol = erc20_contract.functions.symbol().call()
        token_name = erc20_contract.functions.name().call()
        amount = incentive[5]
        choice_index = incentive[1]
        choice_name = gauges["gauges"][choice_index]["shortName"]
        block_hash = incentive[14]
        block_number = incentive[15]
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
    file_path = f"{OUTPUT_DIR}/round_{round}_incentives.csv"
    if os.path.exists(file_path) and \
        round <= rounds.get_last_completed_round():
        with open(file_path, "r") as f:
            f.readline() # Skip header
            reader = csv.reader(f)
            incentives = list(reader)
        return incentives

    # Get start block
    proposal = snapshot.get_proposal(round)
    start_block = proposal["data"]["proposal"]["snapshot"]

    # Get end block
    if round < rounds.get_last_round():
        proposal = snapshot.get_proposal(round+1)
        end_block = proposal["data"]["proposal"]["snapshot"]
    else:
        end_block = w3.eth.block_number

    # Get from onchain
    print(f"Fetching incentives for round {round} from block {start_block} to {end_block}...")

    if round < 53:
        incentives = get_incentive_v1(round, start_block, end_block)
    else:
        incentives = get_incentive_v2(round)
    

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


def get_incentive_events():
    """Get the NewIncentive events for all rounds."""

    incentives = []
    start_block = 18043767 # Starting block for Votium v2
    end_block = w3.eth.block_number

    # Check if file exists and if so get the highest number block
    if os.path.exists(VOTIUM2_INCENTIVES):
        with open(VOTIUM2_INCENTIVES, "r") as f:
            reader = csv.reader(f)
            next(reader)
            incentives = list(reader)
            start_block = max(int(row[-1]) for row in incentives) + 1

    print(f"Collecting NewIncentive events from {start_block} to {end_block}")
    with open(VOTIUM2_ABI) as f:
        abi = f.read()
    contract = w3.eth.contract(address=VOTIUM2_ADDRESS, abi=abi)
    event_filter = contract.events.NewIncentive().create_filter(
        fromBlock=start_block, toBlock=end_block)
    event_log = event_filter.get_all_entries()

    print(f"Writing {len(event_log)} events to {VOTIUM2_INCENTIVES}")
    for event in event_log:
        incentives.append([
            event["args"]["_round"],
            event["args"]["_gauge"],
            event["args"]["_depositor"],
            event["args"]["_index"],
            event["args"]["_token"],
            event["args"]["_amount"],
            event["args"]["_maxPerVote"],
            event["args"]["_excluded"],
            event["args"]["_recycled"],
            event["event"],
            event["logIndex"],
            event["transactionIndex"],
            event["transactionHash"].hex(),
            event["address"],
            event["blockHash"].hex(),
            event["blockNumber"],
        ])

    with open(VOTIUM2_INCENTIVES, "w") as f:
        writer = csv.writer(f)
        writer.writerow([
            '_round',
            '_gauge',
            '_depositor',
            '_index',
            '_token',
            '_amount',
            '_maxPerVote',
            '_excluded',
            '_recycled',
            'event',
            'logIndex',
            'transactionIndex',
            'transactionHash',
            'address',
            'blockHash',
            'blockNumber',
        ])
        writer.writerows(incentives)

    return incentives


def main():
    """Get the incentives for all rounds."""

    get_incentive_events()

    with alive_bar(rounds.get_last_round()) as bar:
        for round in range(1, rounds.get_last_round()+1):
            bar()
            bar.text(f"Round {round}")
            incentives = get_incentive(round)


if __name__ == "__main__":
    main()


