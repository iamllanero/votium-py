from dotenv import load_dotenv
from web3 import Web3
import csv
import datetime
import os

load_dotenv()
WEB3_HTTP_PROVIDER = os.environ.get("WEB3_HTTP_PROVIDER")
w3 = Web3(Web3.HTTPProvider(WEB3_HTTP_PROVIDER))

PROPOSAL_FILE = "cache/snapshot/proposal_list.csv"

with open(PROPOSAL_FILE, "r") as f:
    reader = csv.DictReader(f)
    proposals = list(reader)

for proposal in proposals:
    kc_id = w3.keccak(text=proposal["id"])
    print(f"{proposal['round']} - {proposal['id']} - {kc_id.hex()} - {proposal['title']} - {proposal['start']} - {proposal['end']}")



INITIATED_FILE = "cache/events/0x19BBC3463Dd8d07f55438014b021Fb457EBD4595-Initiated.csv"
BRIBED_FILE = "output/incentives/votium1_incentives.csv"

with open(INITIATED_FILE, "r") as f:
    reader = csv.DictReader(f)
    events = list(reader)

with open(BRIBED_FILE, "r") as f:
    reader = csv.DictReader(f)
    bribes = list(reader)

i = 2
for event in events:
    proposal_id = event["_proposal"]
    block = event["blockNumber"]
    timestamp = w3.eth.get_block(block).timestamp
    date = datetime.datetime.utcfromtimestamp(timestamp)
    num_bribes = len([b for b in bribes if b["_proposal"] == proposal_id])
    if num_bribes > 1:
        print(f"{i:2.0f} - {block} - {date} - {num_bribes:2.0f} - {proposal_id}")
        i += 1
    else:
        print(f"{i:2.0f} - {block} - {date} - {num_bribes:2.0f} - {proposal_id}")