# ucsc-news-site-scraper
Python Scraper to convert news.ucsc.edu articles to wordpress import files.  

##Usage

usage: newsparser.py [-h] [-s START_DATE_STRING] [-e END_DATE_STRING]
                     [-i START_INDEX]

optional arguments:
  -h, --help            show this help message and exit
  -s START_DATE_STRING  Start date for parsing eg. mm/yyyy. Default is
                        01/2002 - the first month in the news.ucsc.edu archives.
  -e END_DATE_STRING    End date for parsing eg. mm/yyyy. Default is current
                        month.
  -i START_INDEX        The starting index for post and image IDs. Default is
                        0 - important to avoid id conflicts if the wordpress site 
                        already has content

## Design

The scraper has three main sections: a class to collect all the article URLs to be scraped, a class to scrape those articles and generate wordpress import files, and a class to manage a command line display and progress bar.

### The Command Line Display

The command line display is used to keep the user informed of what is currently going on in the scraping process.  It is used by both the article collector and the article scraper.  It uses the curses module to manipulate the terminal window, and consists of a couple message fields and a progress bar.  The first message field displays the current action happening, eg. "Scraping Articles", and the second displays more detailed information about the action, eg. "Scraping Article: news.ucsc.edu/{year}/{month}/example.html"  The progress bar shows the amount of the action that has been completed.

### The Article Collector

The article collector takes a start month and year as well as an end month and year for it's main method: get_articles().  The collector takes these dates and generates a list of URLs, one for each monthly news.ucsc.edu archive page, which use the pattern http://news.ucsc.edu/{year}/{month}.  BeautifulSoup is then used to scrape the individual article links from each archive page into a master list, which is then returned.

## The Article Scraper



The size of each import file is limited to roughly 5MB, because of timeout limitations with wordpress servers.
