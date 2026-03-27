# Campsite Availability Scraping

This script scrapes the https://recreation.gov website for campsite availabilities.

## Example Usage

```
$ python camping.py --start-date 2026-07-20 --end-date 2026-07-23 --parks 232448 232450 232447 232770
There are campsites available from 2026-07-20 to 2026-07-23!!!
🏕 LOWER PINES (232450): 11 site(s) available out of 73 site(s)
❌ TUOLUMNE MEADOWS (232448): 0 site(s) available out of 148 site(s)
❌ UPPER PINES (232447): 0 site(s) available out of 235 site(s)
❌ BASIN MONTANA CAMPGROUND (232770): 0 site(s) available out of 30 site(s)
```

You can also read from stdin. Define a file (e.g. `parks.txt`) with IDs like this:

```
232447
232449
232450
232448
```

and then use it like this:

```
$ python camping.py --start-date 2026-07-20 --end-date 2026-07-23 --stdin < parks.txt
```

### Additional Options

- `--nights N`: Look for N consecutive nights of availability (default: entire date range)
- `--show-campsite-info`: Display specific campsite IDs and their available date ranges
- `--json-output`: Output results as JSON for scripting
- `--debug`: Enable debug logging

You'll want to put this script into a 5 minute crontab. You could also pipe the output into `notifier.py` to get notified when sites become available.

## Getting park IDs

Go to https://recreation.gov and search for the campground you want. Click on it in the search sidebar. This should take you to a page for that campground, the URL will look like `https://www.recreation.gov/camping/campgrounds/<number>`. That number is the park ID.

## Installation

Requires Python 3.8+.

```
python3 -m venv myvenv
source myvenv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
# You're good to go!
```

## Notifications

Pipe the output of your command into `notifier.py` to get notified:

```
# Print to stdout
python camping.py --start-date 2026-07-20 --end-date 2026-07-23 --parks 232447 | python notifier.py

# Send to a webhook (ntfy.sh, Slack, Discord, etc.)
python camping.py --start-date 2026-07-20 --end-date 2026-07-23 --parks 232447 | python notifier.py --webhook https://ntfy.sh/my-camping-alerts
```

## Mac OS Notifications

Install [`terminal-notifier`](https://github.com/julienXX/terminal-notifier) (with Homebrew - `brew install terminal-notifier`).

Then run `cron.sh` to send a notification whenever there are campsites:

```sh
VIRTUAL_ENV=/path/to/venv /path/to/cron.sh --start-date 2026-07-11 --end-date 2026-07-12 --parks 232447
```

## Credits

Based on https://github.com/banool/recreation-gov-campsite-checker and https://github.com/bri-bri/yosemite-camping
