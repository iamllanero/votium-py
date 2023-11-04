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


def load_contract(abi, address):
    with open(abi) as f:
        abi = f.read()
    contract = w3.eth.contract(address=address, abi=abi)
    return contract


def get_mapped_proposals():
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


def get_incentive_v1(round, start_block, end_block):
    proposal = get_proposal(round)
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
        round <= get_last_completed_round():
        with open(file_path, "r") as f:
            f.readline() # Skip header
            reader = csv.reader(f)
            incentives = list(reader)
        return incentives

    # Get start block
    proposal = get_proposal(round)
    start_block = proposal["data"]["proposal"]["snapshot"]

    # Get end block
    if round < get_last_round():
        proposal = get_proposal(round+1)
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


def get_all_incentive_events_v1():
    """Get all the Bribed events."""

    incentives = []
    start_block = 13262700 # First block with Bribed event
    end_block = 18043767 - 1 # One less starting block for Votium v2
    # end_block = start_block + 100000

    # Check if file exists and if so get the highest number block
    if os.path.exists(VOTIUM1_INCENTIVES):
        with open(VOTIUM1_INCENTIVES, "r") as f:
            reader = csv.reader(f)
            next(reader)
            incentives = list(reader)
            start_block = max(int(row[-1]) for row in incentives) + 1

    with open(VOTIUM1_ABI) as f:
        abi = f.read()
    contract = w3.eth.contract(address=VOTIUM1_ADDRESS, abi=abi)

    print(f"Collecting Bribed events from {start_block} to {end_block}")
    event_filter = contract.events.Bribed().create_filter(
        fromBlock=start_block, toBlock=end_block)
    event_log = event_filter.get_all_entries()

    print(f"Writing {len(event_log)} events to {VOTIUM1_INCENTIVES}")
    for event in event_log:
        # AttributeDict({'args': AttributeDict({'_proposal': b'\xc8A\xdb\x89*X\x16\x8d!&.\xb8\xe2\xf9}e\x1f\xb3T\x89o\xa9\n\xc3\xd6\xbc\xfa\xd0\x03\x19\xc55',
        #     '_token': '0x6B175474E89094C44Da98b954EedeAC495271d0F',
        #     '_amount': 9600000000000000000000,
        #     '_choiceIndex': 22}),
        #     'event': 'Bribed',
        #     'logIndex': 548,
        #     'transactionIndex': 319,
        #     'transactionHash': HexBytes('0x11d8023e4a99a850f2fbd3727b104d075c9af99458798fa7ae29d6b92882b8c9'),
        #     'address': '0x19BBC3463Dd8d07f55438014b021Fb457EBD4595',
        #     'blockHash': HexBytes('0xc7c4a936dbda35c108faa7d66389a483407aef156e5f5e46977c267044c76dbd'),
        #     'blockNumber': 13262700}),
        incentives.append([
            event["args"]["_proposal"].hex(),
            event["args"]["_token"],
            event["args"]["_amount"],
            event["args"]["_choiceIndex"],
            event["event"],
            event["logIndex"],
            event["transactionIndex"],
            event["transactionHash"].hex(),
            event["address"],
            event["blockHash"].hex(),
            event["blockNumber"],
        ])

    with open(VOTIUM1_INCENTIVES, "w") as f:
        writer = csv.writer(f)
        writer.writerow([
            '_proposal',
            '_token',
            '_amount',
            '_choiceIndex',
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


def get_all_incentive_events_v2():
    """Get all the NewIncentive events."""

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


def get_token(token_address):
    """Get the token name and symbol from the token address."""

    if token_address in TOKEN_MAP:
        return TOKEN_MAP[token_address]
    else:
        erc20_contract = load_contract(ERC20_ABI, token_address)
        token_symbol = erc20_contract.functions.symbol().call()
        token_name = erc20_contract.functions.name().call()
        TOKEN_MAP[token_address] = [token_symbol, token_name]

        return token_symbol, token_name


def get_block_time(block_number):
    """Get the timestamp for a given block number."""

    if block_number in BLOCK_TIME_MAP:
        return BLOCK_TIME_MAP[block_number]
    else:
        timestamp = w3.eth.get_block(block_number)["timestamp"]
        BLOCK_TIME_MAP[block_number] = timestamp
        return timestamp
    

def get_incentives_v1(mapped_proposals, initiated, bribed):
    with alive_bar(52) as bar:
        for round in range(1,53):
            bar()
            bar.text(f"Round {round}")

            # Check if output already exists
            file_path = f"{OUTPUT_DIR}/round_{round}_incentives.csv"
            if os.path.exists(file_path):
                continue

            proposal = get_proposal(round)
            proposal_id = [p for p in mapped_proposals if p[0] == str(round)][0][5]
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


def get_gauge_score(proposal, gauge_address):
    gauge_name = GAUGE_MAP[gauge_address]
    for choice in proposal:
        if choice[0] == gauge_name:
            return gauge_name, choice[2]


def get_incentives_v2(new_incentives):
    with alive_bar(int(get_last_round()) - 52) as bar:
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

        bar()
        print("Mapping all Snapshot proposal IDs to Event proposal IDs")
        mapped_proposals = get_mapped_proposals()

        bar()
        print("Getting all Initiated events from Votium v1")
        initiated = get_events(
            VOTIUM1_ABI,
            VOTIUM1_ADDRESS,
            "Initiated",
            start_block=13209937, # Contract deployed at 13209937
            end_block=18043767-1 # One less starting block for Votium v2
        )

        bar()
        print("Getting all Bribed events from Votium v1")
        bribed = get_events(
            VOTIUM1_ABI,
            VOTIUM1_ADDRESS,
            "Bribed",
            start_block=13209937, # Contract deployed at 13209937
            end_block=18043767-1 # One less starting block for Votium v2
        )

        bar()
        print("Getting all NewIncentive events from Votium v2")
        new_incentives = get_events(
            VOTIUM2_ABI,
            VOTIUM2_ADDRESS,
            "NewIncentive",
            start_block=18043767, # Starting block for Votium v2
            end_block=w3.eth.block_number
        )


    get_incentives_v1(mapped_proposals, initiated, bribed)

    get_incentives_v2(new_incentives)


if __name__ == "__main__":
    main()


