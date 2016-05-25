# slug-news
Set of tools to manipulate data from the news.ucsc.edu site


##The Scraper

###Usage

usage: newsparser.py [-h] [-s START_DATE_STRING] [-e END_DATE_STRING]
                     [-i START_INDEX] [--markdown]

optional arguments:
*  -h, --help            show this help message and exit
*  -s START_DATE_STRING  Start date for parsing eg. mm/yyyy. Default is 01/2002 - the first month in the news.ucsc.edu archives.
*  -e END_DATE_STRING    End date for parsing eg. mm/yyyy. Default is current month.
*  -i START_INDEX        The starting index for post and image IDs. Default is 0 - important to avoid id conflicts if the wordpress site  already has content
*  --markdown            Generate Jekyll Markdown Files from Articles

### Design

The scraper has three main sections: a class to collect all the article URLs to be scraped, a class to scrape those articles and generate wordpress import files, and a class to manage a command line display and progress bar.

#### The Command Line Display

The command line display is used to keep the user informed of what is currently going on in the scraping process.  It is used by both the article collector and the article scraper.  It uses the curses module to manipulate the terminal window, and consists of a couple message fields and a progress bar.  The first message field displays the current action happening, eg. "Scraping Articles", and the second displays more detailed information about the action, eg. "Scraping Article: news.ucsc.edu/{year}/{month}/example.html"  The progress bar shows the amount of the action that has been completed.

#### The Article Collector

The article collector takes a start month and year as well as an end month and year for it's main method: get_articles().  The collector takes these dates and generates a list of URLs, one for each monthly news.ucsc.edu archive page, which use the pattern "http://news.ucsc.edu/{year}/{month}".  BeautifulSoup is then used to scrape the individual article links from each archive page into a master list, which is then returned.

#### The Article Scraper

The article scraper takes a list of individual news.ucsc.edu article URLs as input.  It then iterates through each URL in this list, scraping it for the following information:

* title
* subhead - the article subtitle
* author (the user account the article will fall under)
* article_author (the name that will display as the author)
* article_author_role
* article_author_telephone
* message_from
* message_to
* publication date
* categories list
* images dictionary of the form ( image_url:    - image_caption
                                   				- image_height
                                    			- image_width
                                    			- image_id )
- post_id
- article_body (the main text of the article)

Most of these are self explanatory, but a couple warrant a little more depth

##### author, article_author, article_author_role, and article_author_telephone

In a Wordpress import, the author field is used to either assign the article to an existing account, or is used to create a new user account for the author of the post.  However, not all of the writers who wrote for news.ucsc.edu are currently on the staff, and so shouldn't have accounts created for them.  The scraper uses a whitelist of current news.ucsc.edu writer staff to determine whether the author of an article should be placed into the author field, or whether the article should be placed under the generic "Public Information Office" account.  If the latter is the case, then the author's information is placed under article_author, which becomes a custom wordpress field that can then be used by a wordpress theme to display as the author without having to create an account for the writer. The role and telephone fields aren't standard wordpress fields, so they will be placed under custom fields regardless.

##### message_from and message_to

Sometimes, a news.ucsc.edu article will take the form of a message from a specific party to a specific audience, and won't have an author.  In this case, the article will have message_from and message_to fields.  These articles are placed under the "Public Information Office"  and the message fields become custom wordpress fields. A wordpress theme can then be used to display the message_from and message_to fields.

##### The images dictionary

The images dictionary contains information about regular images found in articles.  This means that images in sidebar elements or manually inserted into the article text will not be scraped, and will remain in the text.  However, functionality is included to change the urls for images as well as other links from relative to absolute urls, so that they will still display in wordpress. The scraper collects the image url and caption, and assigns it with an ID.  It then downloads part of the image using the pillow image processing package to get the width and height of the image.  Each article has a dictionary of the images found in the article, where the key is the image url and the values are the four image attributes that were scraped.  This information is then used for two things: to create caption objects in the wordpress article text so that the images will automatically display in text, and to create import items in the wordpress import xml file so that wordpress will download the images from their original source and save them in its media database.  In order to generate the caption objects, the parser creates the urls that the images will have once imported into the wordpress media database according to the pattern that wordpress follows to name and save imported media.

##### The post_id and image_id

Wordpress assigns each imported item an ID. If wordpress finds that an item it is attempting to import has the same ID as an already existing item, it will not import it. This means that it is important to be able to make sure that the IDs that this parser assign to items to be imported can start at a number higher than any current existing ID, so that there will be no conflicts.


The size of each import file is limited to roughly 5MB, because of timeout limitations with wordpress servers.
