import datetime
import pytz

def get_rounds():
    """Return a list of all round dates in form [round_start, round_end]."""

    round_dates = []
    # current_time_utc = datetime.datetime.utcnow()
    current_time_utc = pytz.utc.localize(datetime.datetime.now())
    round = 1
    round_start = pytz.utc.localize(datetime.datetime.strptime('2021-09-16', '%Y-%m-%d'))
    round_end = round_start + datetime.timedelta(days=5)
    while (round_start < current_time_utc):
        # print(f"{round}: {round_start} = {round_end}")
        round_dates.append([round_start, round_end])
        round += 1
        round_start += datetime.timedelta(days=14)
        round_end = round_start + datetime.timedelta(days=5)
    return round_dates


def get_current_round():
    """Return the current round, or None if not in a round."""

    rounds = get_rounds()
    current_time_utc = pytz.utc.localize(datetime.datetime.now())
    for i, (round_start, round_end) in enumerate(rounds):
        if round_start <= current_time_utc <= round_end:
            return i + 1
    return None


def get_round_for_date(date):
    """Return the round for a given date. The date will converted to UTC."""

    utc_date = pytz.utc.localize(date)

    i = 0
    for round_start, round_end in get_rounds():
        i += 1
        if round_start <= utc_date <= round_end:
            return i
    return None


def get_dates_for_round(round):
    """Return the dates [round_start, round_end] for a given round."""

    rounds = get_rounds()
    if 1 <= round <= len(rounds):
        return rounds[round-1]
    return None


def get_last_round():
    """Return the last round completed (or in progress)."""

    rounds = get_rounds()
    return len(rounds)


def get_last_completed_round():
    """Return the last round that was fully completed."""

    current_round = get_current_round()
    if current_round is None:
        return get_last_round() - 1
    else:
        return current_round - 1
