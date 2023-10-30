# Votium-py

These are a set of scripts to help pull data from Snapshot and Votium v2 for
Convex Finance incentives.

There are three primary scripts, intended to be run in listed order:

`snapshot.py` - Gets the proposal and voting data from Snapshot.

`incentives.py` - Gets incentives from Votium v1 and v2.

`price.py` - Merges and prices the Snapshot and incentives data.

Each script works be creating a CSV in the output directory. The CSVs are
used by other scripts, but are also the primary useful output from these
scripts.

The `price.py` script actually calls all other scripts so in reality, if you
are interested only in the final product, you can just run `price.py`.

## More Details

All of the scripts do cache their data to reduce API calls. If you are fiddling
with the scripts and need to rewrite data, be sure to delete the file(s) from
the cache directory.

`snapshot.py`

Snapshot pulls data from Snapshot API using graphql. I avoid using any libs
because the the call is simple.

`incentives.py`

Incentives pulls data directly from the blockchain so you will need to set an
environment variable (or create a .env file) for `WEB3_HTTP_PROVIDER`.

`price.py`

Price gets the data from the excellent DefiLlama API. Don't abuse it.

