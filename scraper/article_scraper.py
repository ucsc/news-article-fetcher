from utils import GremlinZapper, CommandLineDisplay, ArticleUtils
import bs4
from bs4 import BeautifulSoup
from unidecode import unidecode
import re
import datetime
import requests
import pprint
from urlparse import urljoin
from tidylib import tidy_fragment
import os
import time
from email.utils import formatdate


class ContentNotHTMLException(Exception):
    """
    Exception for when a url doesn't return html content
    """
    def __init__(self):
        Exception.__init__(self, "Content type not text/html; charset=UTF-8")


class NoDateException(Exception):
    """
    Exception for when an article doesn't contain a date
    """
    def __init__(self):
        Exception.__init__(self, "Article does not contain a date")


class BodyIsNoneException(Exception):
    """
    Exception for when an article doesn't contain a date
    """
    def __init__(self):
        Exception.__init__(self, "Body is None")


class ImageException(Exception):
    def __init__(self, image_url):
        Exception.__init__(self, "Error getting height and width of image " + image_url)


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

        if start_year == end_year:
            for i in xrange(start_month, end_month + 1):
                current_url = 'http://news.ucsc.edu/' + str(end_year) + '/' + "%02d" % (i,) + '/'
                url_list.append(current_url)
        else:
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


class ArticleWriter(object):
    """
    Takes an articles_dictionary and generates a wordpress import file.  also generates jekyll
    markdown files if specified to do so
    """
    def __init__(self):
        self.utils = ArticleUtils()

    def write_markdown(self, article_url, article_dict):
        """
        Given a dictionary of article values:
            - title
            - subhead (the subtitle)
            - author (the user account the article will fall under)
            - article_author (the name that will display as the author)
            - article_author_role
            - article_author_telephone
            - message_from
            - message_to
            - raw_date (the date in yyyy-mm-dd format)
            - categories list
            - images dictionary ( image_url:    - image_caption
                                                - image_height
                                                - image_width
                                                - image_id )
            - post_id
            - article_body (the main text of the article)

        Creates a new file in the current directory with all data except article_body and date in YAML
        metadata format:
            ---
            layout: post
            title: "The Article Title"
            subhead: "An Optional Subtitle"
            author: John Doe
            article_author: Richard Smith
            article_author_role: Writer
            article_author_telephone: 000-0000
            campus_message:
                - from: "Campus Administration"
                  to: "Student Body"
            post_id: 1
            categories:
              - name: Press Release
                nicename: press-release
              - name: Regular News
                nicename: regular-news
            images:
            ---

        :param article_dict:
        :param article_url:
        :return:
        """

        title = article_dict['title'] or ''
        title = title.replace('"', "'")
        subhead = article_dict['subhead'] or ''
        subhead = subhead.replace('"', "'")
        author = article_dict['author'] or ''
        article_author = article_dict['article_author'] or ''
        post_id = article_dict['post_id']
        raw_date = article_dict['date']
        article_author_telephone = article_dict['article_author_telephone'] or ''
        article_author_title = article_dict['article_author_title'] or ''
        message_from = article_dict['message_from'] or ''
        message_to = article_dict['message_to'] or ''
        categories = article_dict['categories']

        upload_url = 'http://dev-ucsc-news.pantheonsite.io/'
        image_upload_string = 'wp-content/uploads/'

        article_url_ending = self.utils.get_url_ending(article_url)

        try:
            date_object = datetime.datetime.strptime(raw_date, "%Y-%m-%d")
            image_url_date = date_object.strftime("%Y/%m/")

            post_date_string = formatdate(time.mktime(date_object.timetuple()))
            date_string_no_tz = date_object.strftime("%Y-%m-%d %H:%M:%S")

        except ValueError:
            raise NoDateException()

        fo = open(article_dict['file_name'], "w")
        fo.write("---\n")
        fo.write("layout: post\n")
        fo.write("title: \"" + title + "\"\n")
        fo.write("subhead: \"" + subhead + "\"\n")

        fo.write("author: " + author + "\n")
        fo.write("article_author: " + article_author + "\n")
        fo.write("article_author_role: " + article_author_title + "\n")
        fo.write("article_author_telephone: " + article_author_telephone + "\n")

        fo.write("campus_message:\n")
        fo.write("    - from: \"" + message_from + "\"\n")
        fo.write("      to: \"" + message_to + "\"\n")

        fo.write("post_id: " + post_id + "\n")

        fo.write("categories:\n")
        for category_name in categories:
            category_nicename = self.utils.get_nicename(category_name)
            fo.write("  - name: " + category_name + "\n")
            fo.write("    nicename: " + category_nicename + "\n")

        fo.write("images:\n")
        for key in article_dict['images_dictionary']:

            url_ending = self.utils.get_url_ending(key)
            hacky_url_ending = url_ending
            hacky_url_ending = hacky_url_ending.replace("%", "")

            fo.write("  - file: " + key + "\n")

            values_dict = article_dict['images_dictionary'][key]
            image_id = values_dict['image_id']

            fo.write('    image_id: ' + image_id + '\n')
            if values_dict['image_caption'] is not None:
                replaced = values_dict['image_caption'].replace('"', "'")
                fo.write("    caption: \"" + replaced + "\"\n")
            else:
                fo.write("    caption: \n")

            fo.write('    permalink: \"' + upload_url + image_url_date + article_url_ending +
                     '/attachment/' + image_id + '/\"\n')
            fo.write('    _wp_attached_file: \"' + image_url_date + hacky_url_ending + '\"\n')

        fo.write("---\n\n")

        for image_url in article_dict['images_dictionary']:
            values_dict = article_dict['images_dictionary'][image_url]

            image_caption = values_dict['image_caption'] or ""
            image_width = values_dict['image_width']
            image_height = values_dict['image_height']
            image_id = values_dict['image_id']

            url_ending = self.utils.get_url_ending(image_url)
            hacky_url_ending = url_ending
            hacky_url_ending = hacky_url_ending.replace("%", "")

            fo.write("[caption id=\"attachment_" +
                     image_id + "\" align=\"alignright\" width=\"" + image_width +
                     "\"]<a href=\"" + upload_url +
                     image_url_date + hacky_url_ending + "\">"
                     "<img class=\"size-full wp-image-" + image_id + "\" "
                     "src=\"" + upload_url +
                     image_url_date + hacky_url_ending +
                     "\" alt=\"" + image_caption + "\" width=\"" + image_width +
                     "\" height=\"" + image_height + "\" /></a>" + image_caption +
                     "[/caption]\n")
        fo.write(article_dict['article_body'])
        fo.write("\n")
        fo.write(article_dict['source_permalink'] + "\n")
        fo.close()

    def write_wordpress_import_file(self, articles_dictionary, markdown=False):
        """
        Takes a list of dictionaries with information about an article and
        creates a wordpress import files of maximum size 5MB
        :param articles_dictionary:
        :param markdown:
        :return:
        """

        import_file_num = 0

        five_megabytes = 5242880

        upload_url = 'http://dev-ucsc-news.pantheonsite.io/'

        image_upload_string = 'wp-content/uploads/'

        fo = open('wordpress-news-site-scraper-import-' + str(import_file_num) + '.xml', "w")
        fo.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        fo.write('<rss version="2.0"\n')
        fo.write('    xmlns:excerpt="http://wordpress.org/export/1.2/excerpt/"\n')
        fo.write('    xmlns:content="http://purl.org/rss/1.0/modules/content/"\n')
        fo.write('    xmlns:wfw="http://wellformedweb.org/CommentAPI/"\n')
        fo.write('    xmlns:dc="http://purl.org/dc/elements/1.1/"\n')
        fo.write('    xmlns:wp="http://wordpress.org/export/1.2/">\n\n')
        fo.write('  <channel>\n\n')
        fo.write('    <language>en-US</language>\n')
        fo.write('    <wp:wxr_version>1.2</wp:wxr_version>\n\n\n')

        for article_url, article_dict in articles_dictionary.iteritems():

            if markdown:
                self.write_markdown(article_url, article_dict)

            old_file_position = fo.tell()
            fo.seek(0, os.SEEK_END)
            size = fo.tell()
            fo.seek(old_file_position, os.SEEK_SET)

            if size > five_megabytes:
                import_file_num += 1
                fo.write('\n  </channel>\n')
                fo.write('</rss>\n\n')
                fo.close()
                fo = open('wordpress-news-site-scraper-import-' + str(import_file_num) + '.xml', "w")
                fo.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                fo.write('<rss version="2.0"\n')
                fo.write('    xmlns:excerpt="http://wordpress.org/export/1.2/excerpt/"\n')
                fo.write('    xmlns:content="http://purl.org/rss/1.0/modules/content/"\n')
                fo.write('    xmlns:wfw="http://wellformedweb.org/CommentAPI/"\n')
                fo.write('    xmlns:dc="http://purl.org/dc/elements/1.1/"\n')
                fo.write('    xmlns:wp="http://wordpress.org/export/1.2/">\n\n')
                fo.write('  <channel>\n\n')
                fo.write('    <language>en-US</language>\n')
                fo.write('    <wp:wxr_version>1.2</wp:wxr_version>\n\n\n')

            title = article_dict['title'] or ''
            title = title.replace('"', "'")
            subhead = article_dict['subhead']
            if subhead is not None:
                subhead = subhead.replace('"', "'")
            author = article_dict['author'] or ''
            article_author = article_dict['article_author']
            post_id = article_dict['post_id']
            raw_date = article_dict['date']
            article_author_telephone = article_dict['article_author_telephone']
            article_author_title = article_dict['article_author_title']
            message_from = article_dict['message_from']
            message_to = article_dict['message_to']
            categories = article_dict['categories']
            url_slug = self.utils.get_url_slug(article_url)
            article_url_ending = self.utils.get_url_ending(article_url)

            try:
                date_object = datetime.datetime.strptime(raw_date, "%Y-%m-%d")
                image_url_date = date_object.strftime("%Y/%m/")

                post_date_string = formatdate(time.mktime(date_object.timetuple()))
                date_string_no_tz = date_object.strftime("%Y-%m-%d %H:%M:%S")

            except ValueError:
                raise NoDateException()

            fo.write('      <item>\n')
            fo.write('        <title>' + title + '</title>\n')
            fo.write('        <pubDate>' + post_date_string + '</pubDate>\n')
            fo.write('        <wp:post_id>' + post_id + '</wp:post_id>\n')
            fo.write('        <description></description> \n')
            fo.write('        <content:encoded><![CDATA[')

            for image_url in article_dict['images_dictionary']:
                values_dict = article_dict['images_dictionary'][image_url]

                # The hacky url ending is used because of a bug in the wordpress importer
                # when media is imported from a url, any percent encoded characters
                # are replaced with the encoding digits.  for example, any %20's in the
                # url will become 20's in the media's url on the wordpress server
                url_ending = self.utils.get_url_ending(image_url)
                hacky_url_ending = url_ending
                hacky_url_ending = hacky_url_ending.replace("%", "")

                image_caption = values_dict['image_caption'] or ""
                image_width = values_dict['image_width']
                image_height = values_dict['image_height']
                image_id = values_dict['image_id']

                fo.write("[caption id=\"attachment_" +
                         image_id + "\" align=\"alignright\" width=\"" + image_width +
                         "\"]<a href=\"" + upload_url + image_upload_string +
                         image_url_date + hacky_url_ending + "\">"
                         "<img class=\"size-full wp-image-" + image_id + "\" "
                         "src=\"" + upload_url + image_upload_string +
                         image_url_date + hacky_url_ending +
                         "\" alt=\"" + image_caption + "\" width=\"" + image_width +
                         "\" height=\"" + image_height + "\" /></a>" + image_caption +
                         "[/caption]\n")

            fo.write(article_dict['article_body'] + '\n')
            fo.write(article_dict['source_permalink'] + "\n]]></content:encoded>\n")

            fo.write('        <excerpt:encoded><![CDATA[]]></excerpt:encoded>\n')
            fo.write('        <dc:creator><![CDATA[' + author + ']]></dc:creator>\n')
            fo.write('        <wp:post_date>' + date_string_no_tz + '</wp:post_date>\n')
            fo.write('        <wp:post_date_gmt>' + date_string_no_tz + '</wp:post_date_gmt>\n')
            fo.write('        <wp:comment_status>closed</wp:comment_status>\n')
            fo.write('        <wp:ping_status>open</wp:ping_status>\n')
            fo.write('        <wp:post_name>' + url_slug + '</wp:post_name>\n')
            fo.write('        <wp:status>publish</wp:status>\n')
            fo.write('        <wp:post_parent>0</wp:post_parent>\n')
            fo.write('        <wp:menu_order>0</wp:menu_order>\n')
            fo.write('        <wp:post_type>post</wp:post_type>\n')
            fo.write('        <wp:post_password></wp:post_password>\n')
            fo.write('        <wp:is_sticky>0</wp:is_sticky>\n\n')

            for category_name in categories:
                category_nicename = self.utils.get_nicename(category_name)
                fo.write('        <category domain="category" nicename="' + category_nicename + '">'
                         '<![CDATA[' + category_name + ']]></category>\n')

            fo.write('        <wp:postmeta>\n')
            fo.write('            <wp:meta_key><![CDATA[_edit_last]]></wp:meta_key>\n')
            fo.write('            <wp:meta_value><![CDATA[1]]></wp:meta_value>\n')
            fo.write('        </wp:postmeta>\n')

            if subhead is not None:
                fo.write('        <wp:postmeta>\n')
                fo.write('            <wp:meta_key><![CDATA[subhead]]></wp:meta_key>\n')
                fo.write('            <wp:meta_value><![CDATA[' + subhead + ']]></wp:meta_value>\n')
                fo.write('        </wp:postmeta>\n')

            if article_author is not None:
                fo.write('        <wp:postmeta>\n')
                fo.write('            <wp:meta_key><![CDATA[article_author]]></wp:meta_key>\n')
                fo.write('            <wp:meta_value><![CDATA[' + article_author + ']]></wp:meta_value>\n')
                fo.write('        </wp:postmeta>\n')

            if article_author_title is not None:
                fo.write('        <wp:postmeta>\n')
                fo.write('            <wp:meta_key><![CDATA[article_author_title]]></wp:meta_key>\n')
                fo.write('            <wp:meta_value><![CDATA[' + article_author_title + ']]></wp:meta_value>\n')
                fo.write('        </wp:postmeta>\n')

            if article_author_telephone is not None:
                fo.write('        <wp:postmeta>\n')
                fo.write('            <wp:meta_key><![CDATA[article_author_telephone]]></wp:meta_key>\n')
                fo.write('            <wp:meta_value><![CDATA[' + article_author_telephone + ']]></wp:meta_value>\n')
                fo.write('        </wp:postmeta>\n')

            if message_from is not None:
                fo.write('        <wp:postmeta>\n')
                fo.write('            <wp:meta_key><![CDATA[message_from]]></wp:meta_key>\n')
                fo.write('            <wp:meta_value><![CDATA[' + message_from + ']]></wp:meta_value>\n')
                fo.write('        </wp:postmeta>\n')

            if message_to is not None:
                fo.write('        <wp:postmeta>\n')
                fo.write('            <wp:meta_key><![CDATA[message_to]]></wp:meta_key>\n')
                fo.write('            <wp:meta_value><![CDATA[' + message_to + ']]></wp:meta_value>\n')
                fo.write('        </wp:postmeta>\n')

            fo.write('      </item>\n\n\n')

            for image_url in article_dict['images_dictionary']:
                values_dict = article_dict['images_dictionary'][image_url]

                image_caption = values_dict['image_caption'] or ""
                image_id = values_dict['image_id']
                url_ending = self.utils.get_url_ending(image_url)
                hacky_url_ending = url_ending
                hacky_url_ending = hacky_url_ending.replace("%", "")

                fo.write('        <item>\n')
                fo.write('          <title>' + image_id + '</title>\n')
                fo.write('          <link>' + upload_url + image_url_date + article_url_ending +
                         '/attachment/' + image_id + '/</link>\n')
                fo.write('          <pubDate>' + post_date_string + '</pubDate>\n')
                fo.write('          <dc:creator><![CDATA[' + author + ']]></dc:creator>\n')
                fo.write('          <guid isPermaLink="false">' + image_url + '</guid>\n')
                fo.write('          <description/>\n')
                fo.write('          <content:encoded><![CDATA[]]></content:encoded>\n')
                fo.write('          <excerpt:encoded><![CDATA[' + image_caption + ']]></excerpt:encoded>\n')
                fo.write('          <wp:post_id>' + image_id + '</wp:post_id>\n')
                fo.write('          <wp:post_date>' + date_string_no_tz + '</wp:post_date>\n')
                fo.write('          <wp:post_date_gmt>' + date_string_no_tz + '</wp:post_date_gmt>\n')
                fo.write('          <wp:comment_status>closed</wp:comment_status>\n')
                fo.write('          <wp:ping_status>closed</wp:ping_status>\n')
                fo.write('          <wp:post_name></wp:post_name>\n')
                fo.write('          <wp:status>inherit</wp:status>\n')
                fo.write('          <wp:post_parent>' + post_id + '</wp:post_parent>\n')
                fo.write('          <wp:menu_order>0</wp:menu_order>\n')
                fo.write('          <wp:post_type>attachment</wp:post_type>\n')
                fo.write('          <wp:post_password/>\n')
                fo.write('          <wp:is_sticky>0</wp:is_sticky>\n')
                fo.write('          <wp:attachment_url>' + image_url + '</wp:attachment_url>\n')
                fo.write('          <wp:postmeta>\n')
                fo.write('              <wp:meta_key><![CDATA[_wp_attached_file]]></wp:meta_key>\n')
                fo.write('              <wp:meta_value><![CDATA[' + image_url_date +
                         hacky_url_ending + ']]></wp:meta_value>\n')
                fo.write('          </wp:postmeta>\n')
                fo.write('        </item>\n\n\n')

        fo.write('\n  </channel>\n')
        fo.write('</rss>\n\n')
        fo.close()

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
        self.utils = ArticleUtils()
        self.object_index = start_index
        self.date_regex = re.compile(r"[A-Za-z]+\s*\d{1,2}\,\s*\d{4}")
        self.word_regex = re.compile(r"([^\s\n\r\t]+)")
        self.author_regex = re.compile(r"By\s*(.+)")

        self.author_whitelist = {
            'tim stephens':                 'Tim Stephens',
            'jennifer mcnulty':             'Jennifer McNulty',
            'scott rappaport':              'Scott Rappaport',
            'gwen mickelson':               'Gwen Jourdonnais',
            'gwen jourdonnais':             'Gwen Jourdonnais',
            'dan white':                    'Daniel White',
            'daniel white':                 'Daniel White',
            'scott hernandez-jason':        'Scott Hernandez-Jason',
            'peggy townsend':               'Peggy Townsend',
            'public information office':    'Public Information Office'
        }

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
            author_telephone = None

        author_role_tag = body.find("span", {"class": "role"})
        if author_role_tag is not None:
            self.zap_tag_contents(author_role_tag)
            author_role = author_role_tag.get_text()
        else:
            author_role = None

        return author, author_role, author_telephone

    def categorize_author(self, author):
        """
        Checks if the given author is one of the current ucsc news writers.  If they are, author is returned as
        author, and an empty string is return as article_author.  If they are not, Public Information Office is returned
        as author and the given author is returned as article_author
        :param author:
        :return:
        """
        if author.lower() in self.author_whitelist:
            return self.author_whitelist[author.lower()], None
        else:
            return 'Public Information Office', author

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
            message_from = None

        raw_message_to = body.find("span", {"class": "message-to"})
        if raw_message_to is not None:
            message_to = self.gremlin_zapper.zap_string(raw_message_to.get_text())
        else:
            message_to = None

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
            subhead = None

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
                # image_src = image_src.replace('_', '%5F')

                image_id = str(self.get_next_index())

                caption_tag = figure.find("figcaption", {"class": "caption"})
                if caption_tag is not None:
                    raw_caption = caption_tag.get_text()
                    matches = self.word_regex.findall(raw_caption)
                    image_caption = ' '.join(matches)
                    image_caption = self.gremlin_zapper.zap_string(image_caption)
                else:
                    image_caption = ''

                image_width, image_height = self.utils.get_image_dimens(image_src)
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

        images = body.findAll("img")
        if images is not None:
            for image in images:
                image_relative_src = image['src']
                image_src = urljoin(article_url, image_relative_src)
                image['src'] = image_src

        iframes = body.findAll("iframe")
        if iframes is not None:
            for iframe in iframes:
                iframe_relative_src = iframe['src']
                iframe_src = urljoin(article_url, iframe_relative_src)
                iframe['src'] = iframe_src

        links = body.findAll("a")
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

        article_body_no_html = raw_article_body

        if article_body_no_html is not None:
            article_body_no_html = article_body_no_html.get_text()
            article_body_no_html = self.gremlin_zapper.zap_string(article_body_no_html)

        if raw_article_body is not None:
            self.zap_tag_contents(raw_article_body)
            article_body = ''
            for item in raw_article_body.contents:
                article_body += str(item)
        else:
            article_body = ''

        article_body, errors = tidy_fragment(article_body, options={'numeric-entities': 1})

        return article_body, article_body_no_html

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

    def scrape_article(self, article_url, no_html=False):
        """

        :param article_url:
        :return:
        """
        soup = self.get_soup_from_url(article_url)

        categories = self.get_categories(soup)

        body = soup.find("div", {"id": "main"})

        author, article_author_title, article_author_telephone = self.get_author_info(body)

        author, article_author,  = self.categorize_author(author)

        date = self.get_date(body)

        title, subhead = self.get_headers(body)

        # images_dictionary = dict()

        images_dictionary = self.get_images(article_url, body)

        message_from, message_to = self.get_campus_message_info(body)

        slug = self.utils.get_url_slug(article_url)

        source_permalink = "<p><a href=\"" + article_url + "\" title=\"Permalink to " + slug + "\">Source</a></p>"

        file_name = date + '-' + slug + ".md"

        article_body, article_body_no_html = self.get_article_text(body)

        return {
            'file_name': file_name,
            'source_permalink': source_permalink,
            'author': author,
            'article_author': article_author,
            'article_author_title': article_author_title,
            'article_author_telephone': article_author_telephone,
            'categories': categories,
            'message_from': message_from,
            'message_to': message_to,
            'date': date,
            'title': title,
            'subhead': subhead,
            'images_dictionary': images_dictionary,
            'article_body': article_body,
            'article_body_no_html': article_body_no_html,
            'post_id': str(self.get_next_index())
        }

    def scrape_articles(self, article_list, screen=None):
        """
        Scrapes the urls in article_list and writes the resulting articles
        :param article_list: The list of article URLs to scrape
        :param screen: the CommandLineDisplay object to update the progress of the scraper with
        :return:
        """
        num_urls = len(article_list)
        current_url_num = 1
        prog_percent = 0

        unscrapeable_article_dict = dict()

        articles_dictionary = dict()

        for article in article_list:
            if screen is not None:
                screen.report_progress('Scraping Articles', 'Scraping Article', article, prog_percent)
                prog_percent = int(((current_url_num + 0.0) / num_urls) * 100)
                current_url_num += 1

            try:
                article_info = self.scrape_article(article)

                articles_dictionary[article] = article_info

            except Exception as e:
                unscrapeable_article_dict[article] = str(e)
                # screen.end_session()
                # print e
                # exit()

        return articles_dictionary, unscrapeable_article_dict


class NewsSiteScraper(object):
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
        self.writer = ArticleWriter()

    def write_diagnostic_file(self, diagnostic_dictionary):
        """
        Writes a description of why each article that could not be scraped failed to a file
        called diagnostic_info.txt
        :param diagnostic_dictionary: the diagnostic dictionary returned by ArticleScraper.scrape_articles
        :return:
        """
        fo = open('diagnostic_info.txt', "w")

        fo.write('List of articles that could not be scraped and the relevant exceptions:\n\n\n')

        for key, value in diagnostic_dictionary:
            fo.write(key + ':\n')
            fo.write(value + '\n\n')

    def get_articles_dictionary(self, start_month=1, start_year=2002, end_month=None, end_year=None):
        """
        Returns an articles dictionary of all the articles in the given time period
        :param start_month:
        :param start_year:
        :param end_month:
        :param end_year:
        :return:
        """
        self.screen.start_session()

        article_list = self.article_collector.get_articles(self.screen, start_month, start_year, end_month, end_year)

        articles_dictionary, unscrapeable_dict = self.article_scraper.scrape_articles(article_list, screen=self.screen)

        self.screen.end_session()

        return articles_dictionary

    def get_wordpress_import(self, markdown, start_month=1, start_year=2002, end_month=None, end_year=None):
        """
        Runs the news.ucsc.edu article scraper with the given start and end dates
        :param start_month:
        :param start_year:
        :param end_month:
        :param end_year:
        :param markdown
        :return:
        """

        article_list = self.article_collector.get_articles(self.screen, start_month, start_year, end_month, end_year)

        articles_dictionary = self.get_articles_dictionary()

        print 'Writing Articles...'

        self.writer.write_wordpress_import_file(articles_dictionary, markdown)

        print 'Done'
