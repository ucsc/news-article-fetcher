from nspExceptions import ContentNotHTMLException, NoDateException, ImageException
from GremlinZapper import GremlinZapper
import bs4
from bs4 import BeautifulSoup
from unidecode import unidecode
from PIL import Image
import re
import datetime
import requests
import pprint
import curses
import urllib
import cStringIO
from urlparse import urljoin
from tidylib import tidy_fragment
import traceback


class CommandLineDisplay(object):
    """
    This class is used to display and update a progress bar on the command line
    """

    def __init__(self):
        self.stdscr = None

    def start_session(self):
        """
        Starts a Curses session
        :return:
        """
        self.stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()

    def end_session(self):
        """
        Ends any active curses session
        :return:
        """
        curses.echo()
        curses.nocbreak()
        curses.endwin()

    def update_description(self, description, url):
        """
        Updates only the messages
        :param description:
        :param url:
        :return:
        """
        self.stdscr.addstr(2, 0, "{0}: {1}".format(description, url))
        self.stdscr.move(3, 0)
        self.stdscr.clrtoeol()
        self.stdscr.refresh()

    def report_progress(self, header, description, url, progress_percent):
        """
        Updates progress bar and messages
        :param header:
        :param: description:
        :param stdscr: the terminal screen object to write to
        :param url: the url currently being processed
        :param progress_percent: the percentage of articles that has been processed
        :return:
        """
        self.stdscr.move(0, 0)
        self.stdscr.clrtoeol()
        self.stdscr.addstr(0, 0, "{0}".format(header))
        self.stdscr.addstr(1, 0, "Total progress: [{1:50}] {0}%".
                           format(progress_percent, "#" * (progress_percent / 2)))
        self.stdscr.move(2, 0)
        self.stdscr.clrtoeol()
        self.stdscr.addstr(2, 0, "{0}: {1}".format(description, url))
        self.stdscr.move(3, 0)
        self.stdscr.clrtoeol()
        self.stdscr.refresh()


class ArticleCollector(object):
    """
    Class that iterates through the archives of news.ucsc.edu and returns a list of article urls.
    """

    def get_soup_from_url(self, page_url):
        """
        Takes the url of a web page and returns a BeautifulSoup Soup object representation
        :param page_url: the url of the page to be parsed
        :param article_url: the url of the web page
        :raises: r.raise_for_status: if the url doesn't return an HTTP 200 response
        :return: A Soup object representing the page html
        """
        r = requests.get(page_url)
        if r.status_code != requests.codes.ok:
            r.raise_for_status()
        if r.headers['content-type'] != 'text/html; charset=UTF-8':
            raise ContentNotHTMLException
        return BeautifulSoup(r.content, 'lxml')

    def dict_keys_to_list(self, dict_to_convert):
        """
        Converts the keys in a dictionary to a list
        :param dict_to_convert: the dictionary to convert
        :return: a list of the keys in the dictionary
        """
        keys_list = []

        for key in dict_to_convert:
            keys_list.append(key)
        return keys_list

    def generate_urls(self, start_month, start_year, end_month, end_year):
        """
        Generates a list of news.ucsc.edu archive index urls from the first issue, 2002/01, to the current month
        :return: a list of all news.ucsc.edu archive index urls
        """
        now = datetime.datetime.now()

        if end_year is None:
            end_year = now.year

        if end_month is None:
            if end_year < now.year:
                end_month = 12
            else:
                end_month = now.month

        url_list = []

        for v in xrange(start_year, end_year):
            for i in xrange(start_month, 13):
                current_url = 'http://news.ucsc.edu/' + str(v) + '/' + "%02d" % (i,) + '/'
                url_list.append(current_url)

        for i in xrange(1, end_month + 1):
            current_url = 'http://news.ucsc.edu/' + str(end_year) + '/' + "%02d" % (i,) + '/'
            url_list.append(current_url)

        return url_list

    def get_articles_from_url(self, archive_url):
        """
        Takes a news.ucsc.edu archive index urls and returns a list of all articles
        contained in those archive indexes
        :param archive_url: the archive index url to search for articles
        :return: a list of articles contained in the archive_url
        """

        try:
            soup = self.get_soup_from_url(archive_url)
            archive_lists = soup.find_all('ul', {'class': "archive-list"})

            article_dictionary = dict()

            for archive_list in archive_lists:
                links = archive_list.find_all('a')
                for link in links:
                    url = archive_url + link['href']
                    article_dictionary[url] = ""
            return self.dict_keys_to_list(article_dictionary)
        except requests.exceptions.HTTPError:
            return []

    def get_articles(self, screen=None, start_month=1, start_year=2002, end_month=None, end_year=None):
        """
        Returns a list of the urls of all articles in the news.ucsc.edu archive
        :param screen: the command line screen to write updates to
        :return: a list of all news.ucsc.edu article urls
        """
        url_list = self.generate_urls(start_month, start_year, end_month, end_year)
        article_list = []

        num_urls = len(url_list)
        current_url_num = 1
        prog_percent = 0

        for url in url_list:
            if screen is not None:
                screen.report_progress('Getting Article URLs', 'Getting Articles From', url, prog_percent)
                prog_percent = int(((current_url_num + 0.0) / num_urls) * 100)
                current_url_num += 1
            article_list.extend(self.get_articles_from_url(url))
        return article_list


class ArticleScraper(object):
    """
    Takes a list of news.ucsc.edu articles, scrapes and writes them to files so that they can be used
    by jekyll to create a wordpress import file.  Also creates a file of statistics on the scrapeability
    the articles
    """
    def __init__(self, start_index=0):
        """
        Initializes the index counter for parsed objects to start_index or 0 if none is given
        :return:
        """
        self.gremlin_zapper = GremlinZapper()
        self.object_index = start_index
        self.article_slug_regex = re.compile(r".*\/([^\/\.]+)(?:.[^\.\/]+$)*")
        self.article_ending_regex = re.compile(r".*\/([^\/]+)")
        self.date_regex = re.compile(r"[A-Za-z]+\s*\d{1,2}\,\s*\d{4}")
        self.word_regex = re.compile(r"([^\s\n\r\t]+)")
        self.author_regex = re.compile(r"By\s*(.+)")

    def get_next_index(self):
        """
        Used as a counter to give each item (posts, images, and videos) a unique ID
        :return: the next unique id
        """
        self.object_index += 1
        return self.object_index

    def zap_tag_contents(self, tag):
        """
        Converts any Windows cp1252 or unicode characters in the text of
        a BeautifulSoup bs4.element.Tag Object to ASCII equivalents
        :rtype: bs4.element.Tag
        :param tag: the Tag object to convert
        :return: None
        """
        if hasattr(tag, 'contents'):
            content_length = len(tag.contents)

            gzapper = GremlinZapper()

            for x in range(0, content_length):
                if isinstance(tag.contents[x], bs4.element.NavigableString):
                    unicode_entry = gzapper.kill_gremlins(tag.contents[x])
                    unicode_entry = unidecode(unicode_entry)
                    tag.contents[x].replace_with(unicode_entry)
                elif isinstance(tag.contents[x], bs4.element.Tag):
                    self.zap_tag_contents(tag.contents[x])

    def get_nicename(self, name):
        """
        Returns the nicename version of a string; converts to lowercase and replaces
        spaces with dashes
        :param name:
        :return:
        """
        name = name.replace(' ', '-')
        name = name.lower()

        return name

    def get_image_dimens(self, image_url):
        """
        Uses the PIL Pillow fork to get the width and height of an image from a url
        :param image_url: the url of the image to get the dimensions for
        :return: height, width
        """
        try:
            url_connection = urllib.urlopen(image_url)
            image_file = cStringIO.StringIO(url_connection.read())
            im = Image.open(image_file)
            return im.size
        except IOError as e:
            raise ImageException(image_url)

    def get_soup_from_url(self, page_url):
        """
        Takes the url of a web page and returns a BeautifulSoup Soup object representation
        :param page_url: the url of the page to be parsed
        :param article_url: the url of the web page
        :raises: r.raise_for_status: if the url doesn't return an HTTP 200 response
        :return: A Soup object representing the page html
        """
        r = requests.get(page_url)
        if r.status_code != requests.codes.ok:
            r.raise_for_status()
        if r.headers['content-type'] != 'text/html; charset=UTF-8':
            raise ContentNotHTMLException()
        return BeautifulSoup(r.content, 'lxml')

    def get_url_slug(self, page_url):
        """
        Returns the last section of a url eg. 'posts' for 'wordpress.com/posts.html'
        :raises Exception: if the regex is unable to locate the url slug
        :param page_url: the page url
        :return: the url slug
        """
        slug_match = self.article_slug_regex.findall(page_url)
        if slug_match and len(slug_match) == 1:
            return slug_match[0]
        else:
            raise Exception("unable to find slug for article: " + page_url + "\n")

    def get_url_ending(self, page_url):
        """
        Gets the url slug plus the file ending eg:
        www.example.com/example.html -> example.html
        :param page_url: the url to get the ending from
        :return: the url ending
        """
        slug_match = self.article_ending_regex.findall(page_url)
        if slug_match and len(slug_match) == 1:
            return slug_match[0]
        else:
            raise Exception("unable to find ending for article: " + page_url + "\n")

    def get_author_info(self, body):
        """
        finds and returns the author info from a news.ucsc.edu article, or None
        :param body: the BeautifulSoup object representing the news.ucsc.edu article body
        :return: author, author_role, author_telephone: of the news.ucsc.edu article
        """
        author_tag = body.find("span", {"class": "name"})
        if author_tag is not None:
            self.zap_tag_contents(author_tag)
            author = author_tag.get_text()
        else:
            author = 'Public Information Office'

        author_telephone_tag = body.find("span", {"class": "tel"})
        if author_telephone_tag is not None:
            self.zap_tag_contents(author_telephone_tag)
            author_telephone = author_telephone_tag.get_text()
        else:
            author_telephone = ''

        author_role_tag = body.find("span", {"class": "role"})
        if author_role_tag is not None:
            self.zap_tag_contents(author_role_tag)
            author_role = author_role_tag.get_text()
        else:
            author_role = ''

        return author, author_role, author_telephone

    def get_campus_message_info(self, body):
        """
        Gets the sender and audience for a campus message
        :param body:
        :return:
        """
        raw_message_from = body.find("span", {"class": "message-from"})
        if raw_message_from is not None:
            message_from = self.gremlin_zapper.zap_string(raw_message_from.get_text())
        else:
            message_from = ''

        raw_message_to = body.find("span", {"class": "message-to"})
        if raw_message_to is not None:
            message_to = self.gremlin_zapper.zap_string(raw_message_to.get_text())
        else:
            message_to = ''

        return message_from, message_to

    def get_date(self, body):
        """
        returns date of news.ucsc.edu article or raises exception
        :param body:
        :raises
        :return:
        """
        date_tag = body.find("p", {"class": "date"})
        if date_tag is not None:
            date_string = date_tag.get_text()
            matches = self.date_regex.findall(date_string)
            if matches:
                # Convert date from Month, Day Year to Year-Month-Day
                try:
                    raw_date = matches[0]
                    raw_date = raw_date.rstrip()
                    raw_date = raw_date.lstrip()
                    return datetime.datetime.strptime(raw_date, "%B %d, %Y").strftime("%Y-%m-%d")
                except ValueError:
                    raise NoDateException()
        else:
            raise NoDateException()

    def get_headers(self, body):
        """
        returns title and subhead of news.ucsc.edu article
        :param body:
        :return:
        """
        title_tag = body.find("h1", {"id": "title"})
        if title_tag is not None:
            raw_title = title_tag.get_text()
            title = self.gremlin_zapper.zap_string(raw_title)
        else:
            title = None

        subhead_tag = body.find("p", {"class": "subhead"})
        if subhead_tag is not None:
            raw_subhead = subhead_tag.get_text()
            subhead = self.gremlin_zapper.zap_string(raw_subhead)
        else:
            subhead = ''

        return title, subhead

    def get_images(self, article_url, body):
        """
        Creates a dictionary of dictionaries of information about images in the article
        :param article_url
        :param body:
        :return:
        """

        images_dictionary = dict()

        figures = body.findAll("figure", {"class": "article-image"})

        for figure in figures:

            image_tag = figure.find("img")
            if image_tag is not None:
                image_relative_src = image_tag['src']
                image_src = urljoin(article_url, image_relative_src)

                image_src = image_src.replace(' ', '%20')
                image_src = image_src.replace('_', '%5F')

                image_id = str(self.get_next_index())

                caption_tag = figure.find("figcaption", {"class": "caption"})
                if caption_tag is not None:
                    raw_caption = caption_tag.get_text()
                    matches = self.word_regex.findall(raw_caption)
                    image_caption = ' '.join(matches)
                    image_caption = self.gremlin_zapper.zap_string(image_caption)
                else:
                    image_caption = ''

                image_width, image_height = self.get_image_dimens(image_src)
                if 'height' in image_tag:
                    image_height = image_tag['height']
                if 'width' in image_tag:
                    image_width = image_tag['width']

                images_dictionary[image_src] = {
                    'image_caption': image_caption,
                    'image_height': str(image_height),
                    'image_width': str(image_width),
                    'image_id': image_id
                }

        sidebars = body.findAll("div", {"class": "callout-right narrow"})
        if sidebars is not None:
            for sidebar in sidebars:
                self.zap_tag_contents(sidebar)

                images = sidebar.findAll("img")
                if images is not None:
                    for image in images:
                        image_relative_src = image['src']
                        image_src = urljoin(article_url, image_relative_src)
                        image['src'] = image_src

                iframes = sidebar.findAll("iframe")
                if iframes is not None:
                    for iframe in iframes:
                        iframe_relative_src = iframe['src']
                        iframe_src = urljoin(article_url, iframe_relative_src)
                        iframe['src'] = iframe_src

                links = sidebar.findAll("a")
                if links is not None:
                    for link in links:
                        link_relative_src = link['href']
                        link_src = urljoin(article_url, link_relative_src)
                        link['href'] = link_src

        return images_dictionary

    def get_article_text(self, body):
        """
        Gets the article main text
        :param body:
        :return:
        """
        raw_article_body = body.find("div", {"class": "article-body"})

        if raw_article_body is not None:
            self.zap_tag_contents(raw_article_body)
            article_body = ''
            for item in raw_article_body.contents:
                article_body += str(item)
        else:
            article_body = ''

        document, errors = tidy_fragment(article_body, options={'numeric-entities': 1})

        return document

    def get_categories(self, page_html):
        """
        Gets the categories of the given news.ucsc.edu article page
        :param page_html:
        :return:
        """
        category_tags = page_html.findAll(attrs={"name": "category"})

        categories = []

        for category_tag in category_tags:
            self.zap_tag_contents(category_tag)
            categories.append(category_tag['content'])

        return categories

    def scrape_article(self, article_url):
        """

        :param article_url:
        :return:
        """
        soup = self.get_soup_from_url(article_url)

        categories = self.get_categories(soup)

        body = soup.find("div", {"id": "main"})

        author, author_role, author_telephone = self.get_author_info(body)

        date = self.get_date(body)

        title, subhead = self.get_headers(body)

        # images_dictionary = dict()

        images_dictionary = self.get_images(article_url, body)

        message_from, message_to = self.get_campus_message_info(body)

        slug = self.get_url_slug(article_url)

        source_permalink = "[source](" + article_url + " \"Permalink to " + slug + "\")"

        file_name = date + '-' + slug + ".md"

        article_body = self.get_article_text(body)

        return {
            'file_name': file_name,
            'source_permalink': source_permalink,
            'author': author,
            'author_telephone': author_telephone,
            'author_role': author_role,
            'categories': categories,
            'message_from': message_from,
            'message_to': message_to,
            'date': date,
            'title': title,
            'subhead': subhead,
            'images_dictionary': images_dictionary,
            'article_body': article_body,
            'post_id': str(self.get_next_index())
        }

    def write_article(self, article_dict):
        """

        :param article_info_dict:
        :return:
        """
        """
        Given a dictionary of article values:
        creates a new file in the current directory with title, author, date, and images in YAML format metadata
        followed by the Markdown format article body
        and finally a permalink to the article source link

        currently overwrites existing files if generated filenames are the same

        :param article_dict: A dictionary of scraped values for a UCSC Currents online magazine article
        :return None
        """

        title = article_dict['title'] or ''
        title = title.replace('"', "'")
        subhead = article_dict['subhead']
        subhead = subhead.replace('"', "'")
        author = article_dict['author'] or ''
        post_id = article_dict['post_id']
        raw_date = article_dict['date']
        author_telephone = article_dict['author_telephone']
        author_role = article_dict['author_role']
        message_from = article_dict['message_from']
        message_to = article_dict['message_to']
        categories = article_dict['categories']

        # Attempts to format the date correctly in order to predict urls for media urls uploaded to
        # a locally hosted wordpress site.  If this can't be done, it means that the parser was
        # unable to find an exact date for the article.  This means that the article will be
        # ignored by Jekyll's import process, and it is therefore pointless to write it to a file
        try:
            formatted_date = datetime.datetime.strptime(raw_date, "%Y-%m-%d").strftime("%Y/%m/")
        except ValueError:
            raise NoDateException()

        fo = open(article_dict['file_name'], "w")
        fo.write("---\n")
        fo.write("layout: post\n")
        fo.write("title: \"" + title + "\"\n")
        fo.write("subhead: \"" + subhead + "\"\n")

        fo.write("author:\n")
        fo.write("    - name: " + author + "\n")
        fo.write("      role: " + author_role + "\n")
        fo.write("      telephone: " + author_telephone + "\n")

        fo.write("campus_message:\n")
        fo.write("    - from: \"" + message_from + "\"\n")
        fo.write("      to: \"" + message_to + "\"\n")

        fo.write("post_id: " + post_id + "\n")

        fo.write("categories:\n")
        for category_name in categories:
            category_nicename = self.get_nicename(category_name)
            fo.write("  - name: " + category_name + "\n")
            fo.write("    nicename: " + category_nicename + "\n")

        fo.write("images:\n")
        for key in article_dict['images_dictionary']:
            fo.write("  - file: " + key + "\n")

            values_dict = article_dict['images_dictionary'][key]
            image_id = values_dict['image_id']

            fo.write('    image_id: ' + image_id + '\n')
            if values_dict['image_caption'] is not None:
                replaced = values_dict['image_caption'].replace('"', "'")
                fo.write("    caption: \"" + replaced + "\"\n")
            else:
                fo.write("    caption: \n")

        fo.write("---\n\n")

        for image_url in article_dict['images_dictionary']:
            values_dict = article_dict['images_dictionary'][image_url]

            image_caption = values_dict['image_caption'] or ""
            image_width = values_dict['image_width']
            image_height = values_dict['image_height']
            image_id = values_dict['image_id']

            url_ending = self.get_url_ending(image_url)

            fo.write("[caption id=\"attachment_" +
                     image_id + "\" align=\"alignright\" width=\"" + image_width +
                     "\"]<a href=\"http://localhost/mysite/wp-content/uploads/" +
                     formatted_date + url_ending + "\">"
                     "<img class=\"size-full wp-image-" + image_id + "\" "
                     "src=\"http://localhost/mysite/wp-content/uploads/" +
                     formatted_date + url_ending +
                     "\" alt=\"" + image_caption + "\" width=\"" + image_width +
                     "\" height=\"" + image_height + "\" /></a>" + image_caption +
                     "[/caption]\n")
        fo.write(article_dict['article_body'])
        fo.write("\n")
        fo.write(article_dict['source_permalink'] + "\n")
        fo.close()

    def scrape_articles(self, article_list, screen=None):
        """

        :param article_list:
        :param screen:
        :return:
        """
        num_urls = len(article_list)
        current_url_num = 1
        prog_percent = 0

        not_article_list = []
        other_format_author_list = []
        author_list = []

        article_info_dict = dict()

        for article in article_list:
            if screen is not None:
                screen.report_progress('Scraping Articles', 'Scraping Article', article, prog_percent)
                prog_percent = int(((current_url_num + 0.0) / num_urls) * 100)
                current_url_num += 1

            try:
                article_info = self.scrape_article(article)

                self.write_article(article_info)

            except Exception as e:
                not_article_list.append(article)

                screen.end_session()
                traceback.print_exc()
                print str(e)
                print article
                exit()

        return {
            'article_info_dict': article_info_dict,
            'not_article_list': not_article_list,
        }


class NewsSiteParser(object):
    """
    Class that iterates through all the news archives of news.ucsc.edu and generates markdown files for them
    """

    def __init__(self, start_index=0):
        """
        :return:
        """
        self.screen = CommandLineDisplay()
        self.article_collector = ArticleCollector()
        self.article_scraper = ArticleScraper(start_index=start_index)

    def run(self, start_month=1, start_year=2002, end_month=None, end_year=None):

        self.screen.start_session()

        article_list = self.article_collector.get_articles(self.screen, start_month, start_year, end_month, end_year)

        diagnostic_dictionary = self.article_scraper.scrape_articles(article_list, screen=self.screen)

        self.screen.end_session()

        print(pprint.pformat(article_list, indent=4))
        print(len(article_list))
