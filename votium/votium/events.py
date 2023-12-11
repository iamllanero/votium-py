from web3 import Web3
from dotenv import load_dotenv
import csv
import os

load_dotenv()
WEB3_HTTP_PROVIDER = os.environ.get("WEB3_HTTP_PROVIDER")
w3 = Web3(Web3.HTTPProvider(WEB3_HTTP_PROVIDER))

CACHE_DIR = "cache/events"
os.makedirs(CACHE_DIR, exist_ok=True)

def get_events(abi_file_path: str,
               contract_address: str,
               event_name: str,
               start_block: int,
               end_block: int) -> list:
    """
    Get and cache all specified events.

    WARNING: The cache only works if the end_block is increasing. If the start
    block is changed, or if the end block is set to an earlier block, be sure
    to manually delete the cache file.
    """

    print(f"Getting events for {event_name} from {start_block} to {end_block}")

    CACHE_FILE = f"{CACHE_DIR}/{contract_address}-{event_name}.csv"

    events = []

    # Check if file exists and if so get the highest number block
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            reader = csv.reader(f)
            next(reader)
            events = list(reader)
            highest_block = max(int(row[-1]) for row in events) + 1
            start_block = highest_block
            print(f"Found {len(events)} events in cache. Starting from block {start_block}")

    with open(abi_file_path) as f:
        abi = f.read()
    contract = w3.eth.contract(address=contract_address, abi=abi)

    fx = getattr(contract.events, event_name)
    event_filter = fx.create_filter(fromBlock=start_block, toBlock=end_block)

    print(f"Filtering {event_name} events from {start_block} to {end_block}")
    event_log = event_filter.get_all_entries()

    print(f"Found {len(event_log)} {event_name} events{CACHE_FILE}")
    for event in event_log:

        values = []
        for key, value in event["args"].items():
            if isinstance(value, bytes):
                values.append(value.hex())
            else:
                values.append(value)

        values.extend([
            event["event"],
            event["logIndex"],
            event["transactionIndex"],
            event["transactionHash"].hex(),
            event["address"],
            event["blockHash"].hex(),
            event["blockNumber"],
        ])

        events.append(values)

    if len(event_log) > 0:
        print(f"Found {len(event_log)} {event_name} events{CACHE_FILE}")
        with open(CACHE_FILE, "w") as f:
            writer = csv.writer(f)
            headers = []
            for key, value in event["args"].items():
                headers.append(key)
            headers.extend([
                'event',
                'logIndex',
                'transactionIndex',
                'transactionHash',
                'address',
                'blockHash',
                'blockNumber',
            ])
            writer.writerow(headers)
            writer.writerows(events)
    else:
        print(f"No {event_name} events found.")

    return events
