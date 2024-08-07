from votium import rounds
import csv
import datetime
import json
import os
import requests


OUTPUT_DIR = "output/snapshot"
CACHE_DIR = "cache/snapshot"
for dir in [OUTPUT_DIR, CACHE_DIR]:
    os.makedirs(dir, exist_ok=True)


def _snapshot_graphql(query):
    """Base function for querying Snapshot GraphQL"""

    url = "https://hub.snapshot.org/graphql"
    headers = {"Content-Type": "application/json"}
    payload = json.dumps({"query": query})
    response = requests.post(url, headers=headers, data=payload)
    return json.loads(response.text)


def get_snapshot_list():
    """
    Gets the list of the gauge weight proposals (incl. test proposals)
    """

    # Fetch the gauge weight proposals
    print("Fetching gauge weight proposals...")
    response = _snapshot_graphql("""
        query {
            proposals (
                first: 100,
                skip: 0,
                where: {
                    space_in: ["cvx.eth"],
                    title_contains: "Gauge Weight for"
                },
                orderBy: "created",
                orderDirection: asc
            ) {
                id
                title
                start
                end
                author
            }
        }
        """)

    data = response["data"]["proposals"]

    proposal_list = []
    round = 0
    for proposal in data:
        test = False
        title = proposal["title"]
        if title.startswith("(TEST)") or title.startswith("FXN"):
            test = True
        else:
            round += 1
        id = proposal["id"]
        start = datetime.datetime.fromtimestamp(proposal["start"])
        end = datetime.datetime.fromtimestamp(proposal["end"])
        proposal_list.append([round if not test else "0", start, end, id, title])

    # Save to output
    output_file = f"{OUTPUT_DIR}/snapshot_list.csv"
    with open(output_file, "w") as f:
        writer = csv.writer(f)
        writer.writerow(["round", "start", "end", "id", "title"])
        writer.writerows(proposal_list)

    return proposal_list


def get_snapshot(round):
    """Gets the details of a proposal"""

    # Check cache
    cache_file = f"{CACHE_DIR}/round_{round:03d}_snapshot.json"
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            response = json.load(f)

    else:
        # Look up the proposal id
        proposal_list = get_snapshot_list()
        # Filter out any with round 0
        proposal_list = [x for x in proposal_list if x[0] != "0"]
        id = proposal_list[round - 1][3]

        print(f"Fetching proposal {round} - {id}...")
        response = _snapshot_graphql(f"""
            query {{
                proposal(id:"{id}") {{
                    id
                    title
                    body
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
                    scores
                    scores_state
                    scores_total
                    scores_updated
                }}
            }}
            """)

        # Cache the proposal
        with open(cache_file, "w") as f:
            json.dump(response, f, indent=4)

    choices = response["data"]["proposal"]["choices"]
    scores = response["data"]["proposal"]["scores"]

    proposal = []
    for i in range(0, len(choices)):
        proposal.append(
            [
                choices[i],
                i,
                scores[i],
                (scores[i] / response["data"]["proposal"]["scores_total"]),
            ]
        )

    # Save to output
    output_file = f"{OUTPUT_DIR}/round_{round:03d}_snapshot.csv"
    with open(output_file, "w") as f:
        writer = csv.writer(f)
        writer.writerow(["choice_name", "choice_index", "score", "pct_score"])
        writer.writerows(proposal)

    return proposal


def main():
    """Build all snapshots"""

    # Check if there is a current round
    current_round = rounds.get_current_round()
    if current_round is not None:
        round_file = f"{OUTPUT_DIR}/round_{current_round:03d}_snapshot.csv"
        cache_file = f"{CACHE_DIR}/round_{current_round:03d}_snapshot.json"
        print(f"Current round: {current_round}.")
        try:
            if os.path.exists(round_file):
                os.remove(round_file)
                print(f"Deleted {round_file}.")
                os.remove(f"{cache_file}")
        except OSError as e:
            print(f"Error: {e}")

    print("Getting list from Snapshot")
    get_snapshot_list()

    print("Getting details from Snapshot")
    for round in range(1, rounds.get_last_round() + 1):
        snapshot = get_snapshot(round)


if __name__ == "__main__":
    main()
