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
        ---classification-training-metadata---
        category: Category One
        category: Category Two
        category: Category Three
        ---classification-training-metadata---
        ...Article Body...
    """
    def __init__(self):
        self.article_scraper = NewsSiteScraper()
        self.metadata_regex = re.compile(r"^---classification-training-metadata---$")
        self.category_regex = re.compile(r"^category: (.+)$")

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

            fo.write('---classification-training-metadata---\n')
            for category in categories:
                fo.write("category: " + category + '\n')

            fo.write('---classification-training-metadata---\n')

            fo.write(article_body + '\n')

            fo.close()

        print "Done"

    def read_training_set(self, training_set_path='training_articles/'):
        """
        reads all articles in the given directory and returns a dictionary of dictionaries, where each
        key is a training article path, and each value is a dictionary consisting of a list of the
        training article's categories and its text.  If training_set_path is none or the path doesn't exist,
        a training set is downloaded from news.ucsc.edu
        :param training_set_path:
        :return:
        """
        reading_metadata = False
        articles_dictionary = dict()

        """
        Will add functionality to request downloading the news.ucsc.edu training set
        """
        if not os.path.exists(training_set_path):
            print training_set_path + "path does not exist"
            print os.getcwd()
            return

        for root, subdirs, files in os.walk(training_set_path):
            # print('--\nroot = ' + root)

            for filename in files:
                file_path = os.path.join(root, filename)

                # print('\t- file %s (full path: %s)' % (filename, file_path))

                if reading_metadata is True:
                    exit()

                article_dict = dict()
                categories = []

                with open(file_path, 'r') as infile:
                    article_body = ''
                    for line in infile:
                        if self.metadata_regex.match(line) is not None:
                            reading_metadata = not reading_metadata
                        elif reading_metadata:
                            matches = self.category_regex.findall(line)
                            if matches:
                                categories.append(matches[0])
                        else:
                            article_body += line

                    article_dict['categories'] = categories
                    article_dict['article_body'] = article_body

                    articles_dictionary[file_path] = article_dict
        return articles_dictionary

    def kfold_validation(self, k, training_set):
        """
        performs k fold validation on the given training set and prints the statistics.
        :param k:
        :param training_set:
        :return:
        """