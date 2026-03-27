#!/usr/bin/env python3

import argparse
import json
import logging
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from itertools import count, groupby

import requests
from dateutil import rrule
from fake_useragent import UserAgent


LOG = logging.getLogger(__name__)
formatter = logging.Formatter("%(asctime)s - %(process)s - %(levelname)s - %(message)s")
sh = logging.StreamHandler()
sh.setFormatter(formatter)
LOG.addHandler(sh)


BASE_URL = "https://www.recreation.gov"
AVAILABILITY_ENDPOINT = "/api/camps/availability/campground/{park_id}/month"
MAIN_PAGE_ENDPOINT = "/api/camps/campgrounds/{park_id}"

INPUT_DATE_FORMAT = "%Y-%m-%d"
ISO_DATE_FORMAT_REQUEST = "%Y-%m-%dT00:00:00.000Z"
ISO_DATE_FORMAT_RESPONSE = "%Y-%m-%dT00:00:00Z"

SUCCESS_EMOJI = "\U0001f3d5"
FAILURE_EMOJI = "\u274c"

headers = {"User-Agent": UserAgent().random}


def format_date(date_object, format_string=ISO_DATE_FORMAT_REQUEST):
    return datetime.strftime(date_object, format_string)


def send_request(url, params):
    resp = requests.get(url, params=params, headers=headers)
    if resp.status_code != 200:
        raise RuntimeError(
            "failedRequest",
            "ERROR, {} code received from {}: {}".format(
                resp.status_code, url, resp.text
            ),
        )
    return resp.json()


def get_park_information(park_id, start_date, end_date):
    """Query availability by month. The API requires querying one month at a
    time with start_date set to the first of the month.

    Returns: {"<campsite_id>": [<available_date_str>, ...]}
    """
    start_of_month = datetime(start_date.year, start_date.month, 1)
    months = list(rrule.rrule(rrule.MONTHLY, dtstart=start_of_month, until=end_date))

    data = {}
    for month_date in months:
        params = {"start_date": format_date(month_date)}
        url = BASE_URL + AVAILABILITY_ENDPOINT.format(park_id=park_id)
        LOG.debug("Querying for {} with params: {}".format(park_id, params))
        resp = send_request(url, params)
        LOG.debug(
            "Information for {}: {}".format(
                park_id, json.dumps(resp, indent=1)
            )
        )
        for campsite_id, campsite_data in resp["campsites"].items():
            a = data.setdefault(campsite_id, [])
            for date, status in campsite_data["availabilities"].items():
                if status == "Available":
                    a.append(date)

    return data


def get_name_of_site(park_id):
    url = BASE_URL + MAIN_PAGE_ENDPOINT.format(park_id=park_id)
    resp = send_request(url, {})
    return resp["campground"]["facility_name"]


def get_num_available_sites(park_information, start_date, end_date, nights=None):
    maximum = len(park_information)

    num_available = 0
    num_days = (end_date - start_date).days
    dates = [end_date - timedelta(days=i) for i in range(1, num_days + 1)]
    dates = set(format_date(i, format_string=ISO_DATE_FORMAT_RESPONSE) for i in dates)

    if nights is None or nights not in range(1, num_days + 1):
        nights = num_days

    available_dates_by_campsite_id = defaultdict(list)
    for site, availabilities in park_information.items():
        desired_available = [d for d in availabilities if d in dates]
        if not desired_available:
            continue

        appropriate_ranges = consecutive_nights(desired_available, nights)
        if appropriate_ranges:
            num_available += 1
            LOG.debug("Available site {}: {}".format(num_available, site))
            for r in appropriate_ranges:
                available_dates_by_campsite_id[site].append(
                    {"start": r[0], "end": r[1]}
                )

    return num_available, maximum, available_dates_by_campsite_id


def consecutive_nights(available, nights):
    """Returns list of (start, end) date tuples with enough consecutive nights."""
    ordinal_dates = sorted(
        datetime.strptime(d, ISO_DATE_FORMAT_RESPONSE).toordinal()
        for d in available
    )
    c = count()
    consecutive_ranges = [
        list(g) for _, g in groupby(ordinal_dates, lambda x: x - next(c))
    ]

    results = []
    for r in consecutive_ranges:
        if len(r) < nights:
            continue
        for start_idx in range(len(r) - nights + 1):
            start_nice = format_date(
                datetime.fromordinal(r[start_idx]),
                format_string=INPUT_DATE_FORMAT,
            )
            end_nice = format_date(
                datetime.fromordinal(r[start_idx + nights - 1] + 1),
                format_string=INPUT_DATE_FORMAT,
            )
            results.append((start_nice, end_nice))
    return results


def valid_date(s):
    try:
        return datetime.strptime(s, INPUT_DATE_FORMAT)
    except ValueError:
        msg = "Not a valid date: '{0}'.".format(s)
        raise argparse.ArgumentTypeError(msg)


def positive_int(i):
    i = int(i)
    if i <= 0:
        raise argparse.ArgumentTypeError("Not a valid number of nights: {}".format(i))
    return i


def _main(parks, start_date, end_date, nights=None, json_output=False, show_campsite_info=False):
    out = []
    availabilities = False
    json_data = {}
    for park_id in parks:
        park_information = get_park_information(park_id, start_date, end_date)
        name_of_site = get_name_of_site(park_id)
        current, maximum, available_dates = get_num_available_sites(
            park_information, start_date, end_date, nights=nights
        )
        if current:
            emoji = SUCCESS_EMOJI
            availabilities = True
            json_data[park_id] = available_dates
        else:
            emoji = FAILURE_EMOJI

        out.append(
            "{} {} ({}): {} site(s) available out of {} site(s)".format(
                emoji, name_of_site, park_id, current, maximum
            )
        )

        if show_campsite_info and available_dates:
            for site_id, date_ranges in available_dates.items():
                out.append("  * Site {} is available on the following dates:".format(site_id))
                for dr in date_ranges:
                    out.append("    * {} -> {}".format(dr["start"], dr["end"]))

    if json_output:
        print(json.dumps(json_data))
    else:
        if availabilities:
            print(
                "There are campsites available from {} to {}!!!".format(
                    start_date.strftime(INPUT_DATE_FORMAT),
                    end_date.strftime(INPUT_DATE_FORMAT),
                )
            )
        else:
            print("There are no campsites available :(")
        print("\n".join(out))

    return availabilities


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", "-d", action="store_true", help="Debug log level")
    parser.add_argument(
        "--start-date", required=True, help="Start date [YYYY-MM-DD]", type=valid_date
    )
    parser.add_argument(
        "--end-date",
        required=True,
        help="End date [YYYY-MM-DD]. You expect to leave this day, not stay the night.",
        type=valid_date,
    )
    parser.add_argument(
        "--nights",
        help="Number of consecutive nights (default is all nights in the given range).",
        type=positive_int,
    )
    parser.add_argument(
        "--show-campsite-info",
        action="store_true",
        help="Display campsite ID and availability dates.",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Output JSON instead of human readable output.",
    )

    parks_group = parser.add_mutually_exclusive_group(required=True)
    parks_group.add_argument(
        "--parks", dest="parks", metavar="park", nargs="+", help="Park ID(s)", type=int
    )
    parks_group.add_argument(
        "--stdin",
        "-",
        action="store_true",
        help="Read list of park ID(s) from stdin instead",
    )

    args = parser.parse_args()

    if args.debug:
        LOG.setLevel(logging.DEBUG)

    parks = args.parks or [p.strip() for p in sys.stdin]

    try:
        _main(
            parks,
            args.start_date,
            args.end_date,
            nights=args.nights,
            json_output=args.json_output,
            show_campsite_info=args.show_campsite_info,
        )
    except Exception:
        print("Something went wrong")
        raise
