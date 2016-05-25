import pprint
import os
import datetime
import re

from scraper import NewsSiteScraper
from utils import CommandLineDisplay


class ArticleClassifier(object):
    """
    class to classify a set of text documents into categories based on a training set of data.
    A training set of documents can be downloaded from news.ucsc.edu, but any training set of documents
    can be used.  If no directory of training articles is supplied, the classifier will attempt to find a
    training_articles/ directory in the current working directory.  If you would like to supply your own
    training articles, simply include metadata with the categories at the top of each document like this:
        ---
        category: Category One
        category: Category Two
        category: Category Three
        ---
        ...Article Body...
    """
    def __init__(self):
        self.article_scraper = NewsSiteScraper()

    def download_training_set(self):
        """
        Downloads a set of training data consisting of all news.ucsc.edu articles and stores them
        in subfolders of year and month in a directory called training_articles/
        :return:
        """
        base_folder = 'training_articles/'
        articles_dictionary = self.article_scraper.get_articles_dictionary()
        print "Writing Training Articles..."

        if not os.path.exists(base_folder):
            os.makedirs(base_folder)

        for article_url, article_dict in articles_dictionary.iteritems():
            categories = article_dict['categories']
            article_body = article_dict['article_body']
            date = article_dict['date']
            file_name = article_dict['file_name']

            date_object = datetime.datetime.strptime(date, "%Y-%m-%d")

            article_year_folder = date_object.strftime("%Y") + '/'

            article_month_folder = date_object.strftime("%m") + '/'

            if not os.path.exists(base_folder + article_year_folder + article_month_folder):
                os.makedirs(base_folder + article_year_folder + article_month_folder)

            fo = open(base_folder + article_year_folder + article_month_folder + file_name, "w")

            fo.write('---\n')
            for category in categories:
                fo.write("category: " + category + '\n')

            fo.write('---\n')

            fo.write(article_body + '\n')

            fo.close()

        print "Done"

    def read_training_set(self, training_set_path):
        """
        reads all articles in the given directory and returns a dictionary of dictionaries, where each
        key is a training article path, and each value is a dictionary consisting of a list of the
        training article's categories and its text.  If training_set_path is none or the path doesn't exist,
        a training set is downloaded from news.ucsc.edu
        :param training_set_path:
        :return:
        """