import argparse
import datetime
import re

from scraper import NewsSiteScraper


def parse_month_year(date_string):
    """
    Parses a date string of the form mm/yyyy and returns a tuple of the form
    (month, year)
    :param date_string:
    :return:
    """
    date_regex = re.compile(r"(\d{2})\/(\d{4})")

    matches = date_regex.findall(date_string)

    if matches is None:
        print "Start and end dates must be of the form mm/yyyy"
        exit()

    month_year = matches[0]
    month_year_tuple = (int(month_year[0]), int(month_year[1]))
    return month_year_tuple


parser = argparse.ArgumentParser()

parser.add_argument('-s', action='store', dest='start_date_string',
                    help='Start date for parsing eg. mm/yyyy. Default is 01/2002.')

parser.add_argument('-e', action='store', dest='end_date_string',
                    help='End date for parsing eg. mm/yyyy. Default is current month.')

parser.add_argument('-i', action='store', dest='start_index', type=int,
                    help='The starting index for post and image IDs. Default is 0')

parser.add_argument("--markdown", help="Generate Jekyll Markdown Files from Articles",
                    action="store_true")

results = parser.parse_args()

start_index = results.start_index or 0

now = datetime.datetime.now()

if results.start_date_string is not None:
    start_month_year = parse_month_year(results.start_date_string)
else:
    start_month_year = (1, 2002)

if results.end_date_string is not None:
    end_month_year = parse_month_year(results.end_date_string)
else:
    end_month_year = (now.month, now.year)

print start_month_year
print end_month_year

if start_month_year[1] > end_month_year[1]:
    print "newsparser: Start date may not be after end date"
    exit()

if start_month_year[1] == end_month_year[1] and start_month_year[0] > end_month_year[0]:
    print "newsparser: Start date may not be after end date"
    exit()

nsp = NewsSiteScraper(start_index=start_index)

nsp.get_wordpress_import(results.markdown, start_month_year[0], start_month_year[1], end_month_year[0], end_month_year[1])
