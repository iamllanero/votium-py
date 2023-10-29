from alive_progress import alive_bar
from votium import rounds
import csv
import datetime
import json
import os
import requests


OUTPUT_DIR = "output/snapshot/"
CACHE_DIR = "cache/snapshot/"


# Make necessary directories
for dir in [OUTPUT_DIR, CACHE_DIR]:
    if not os.path.exists(dir):
        os.makedirs(dir)


def _snapshot_graphql(query):
    """Base function for querying Snapshot GraphQL"""

    url = 'https://hub.snapshot.org/graphql'
    headers = {
        'Content-Type': 'application/json'
    }
    payload = json.dumps({
        'query': query
    })
    response = requests.post(url, headers=headers, data=payload)
    return json.loads(response.text)


def get_proposal_list():
    """
    Gets the list of the gauge weight proposals. 
    Generally should use the cached get_proposals().
    """

    # Check cache
    cache_file = CACHE_DIR + "proposal_list.csv"
    if os.path.exists(cache_file):
        with open(CACHE_DIR + "proposal_list.csv", "r") as f:
            f.readline() # Skip header
            reader = csv.reader(f)
            proposal_list = list(reader)

        # Check if current round is in the list


        return proposal_list

    # Fetch the gauge weight proposals
    print(f"Fetching gauge weight proposals...")
    response = _snapshot_graphql('''
        query {
            proposals (
                first: 100,
                skip: 0,
                where: {
                    space_in: ["cvx.eth"],
                    title_contains: "gauge weight for"
                },
                orderBy: "created",
                orderDirection: desc
            ) {
                id
                title
                start
                end
                author
            }
        }
        ''')
    # Throw out the ones with "(TEST)" in the title
    filtered_response = [proposal for proposal in response['data']
                         ['proposals'] if "(TEST)" not in proposal['title']]

    proposal_list = []
    round = len(filtered_response)
    for proposal in filtered_response:
        id = proposal['id']
        title = proposal['title']
        start = datetime.datetime.fromtimestamp(proposal['start'])
        end = datetime.datetime.fromtimestamp(proposal['end'])
        proposal_list.append([
            round,
            start,
            end,
            id,
            title
            ])
        round -= 1
    
    # Sort proposal_list by round
    proposal_list.sort(key=lambda x: x[0])

    # Save to cache
    with open(cache_file, "w") as f:
        writer = csv.writer(f)
        writer.writerow(["round", "start", "end", "id", "title"])
        writer.writerows(proposal_list)

    return proposal_list


def get_proposal(round):
    """Gets the details of a proposal"""

    # Check cache
    cache_file = CACHE_DIR + f"round_{round}_proposal.json"
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            proposal = json.load(f)
        return proposal

    # Look up the proposal id
    proposal_list = get_proposal_list()
    id = proposal_list[round-1][3]

    print(f"Fetching proposal {round} - {id}...")
    response = _snapshot_graphql(f'''
        query {{
            proposal(id:"{id}") {{
                id
                title
                start
                end
                snapshot
                state
                author
                created
                space {{
                    id
                    name
                }}
                choices
            }}
        }}
        ''')
    
    # Cache the proposal
    with open(cache_file, "w") as f:
        json.dump(response, f, indent=4)

    return response["data"]["proposal"]


def get_votes(round):
    """
    Actual URL fetcher for getting the votes for a proposal.
    Generally should use the cached get_votes(proposal_id).
    """

    # Check cache
    cache_file = CACHE_DIR + f"round_{round}_votes.json"
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            votes = json.load(f)
        return votes

    # Look up the proposal id
    proposal_list = get_proposal_list()
    id = proposal_list[round-1][3]

    # Get the votes
    print(f"Fetching votes {round} - {id}...")
    response = _snapshot_graphql(f'''
    query {{
        votes (
            first: 1000
            skip: 0
            where: {{
            proposal: "{id}"
            }}
            orderBy: "created",
            orderDirection: desc
        ) {{
            id
            voter
            vp
            vp_state
            created
            proposal {{
                id
            }}
            space {{
                id
            }}
            choice
        }}
        }}
    ''')
    votes = response["data"]["votes"]

    vote_choices = {}

    for vote in votes:
        vp = vote["vp"]
        choices = vote["choice"]
        choice_total = sum(choices.values())
        for key, value in choices.items():
            if key not in vote_choices:
                vote_choices[key] = 0
            vote_choices[key] += (value / choice_total) * vp

    # Cache the votes if the round is complete
    if round <= rounds.get_last_completed_round():
        with open(cache_file, "w") as f:
            json.dump(vote_choices, f, indent=4)

    return vote_choices


def get_snapshot(round):

    # Get proposal
    proposal = get_proposal(round)

    # Get votes
    votes = get_votes(round)


    # Sum of all votes
    total_votes = sum(votes.values())

    # Cross-reference the vote keys with the choice index
    choice_votes = []
    for key, vote_count in votes.items():
        index = int(key) - 1  # Assuming the keys are 1-based
        if 0 <= index < len(proposal["data"]["proposal"]["choices"]):
            choice_name = proposal["data"]["proposal"]["choices"][index]
            choice_votes.append((choice_name, index, vote_count, (vote_count/total_votes)))
        else:
            print(f"ERROR: Invalid choice index {index} for {key}")

    # Write to CSV
    file_path = OUTPUT_DIR + f"round_{round}_snapshot.csv"
    with open(file_path, 'w', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(["choice_name", "choice_index", "votes", "pct_votes"])  # headers
        for row in choice_votes:
            csv_writer.writerow(row)

    return choice_votes

def main():
    """Build all snapshots"""
    with alive_bar(rounds.get_last_round()+1) as bar:
        bar.text("Proposal list")
        bar()
        get_proposal_list()
        for round in range(1, rounds.get_last_round()+1):
            bar.text(f"Round {round}")
            bar()
            # proposal = get_proposal(round)
            # votes = get_votes(round)
            snapshot = get_snapshot(round)


if __name__ == "__main__":
    main()