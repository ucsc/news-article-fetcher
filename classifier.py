import pprint
import os
import datetime
import re

from scraper import NewsSiteScraper
from utils import CommandLineDisplay

from sklearn.preprocessing import MultiLabelBinarizer


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

    def save_training_set(self, training_dictionary, path='training_articles/'):
        """
        Takes a dictionary of training articles and saves them to the directory
        indicated in the path. Creates the path of it doesn't exist.
        :param path:
        :param training_dictionary:
        :return:
        """
        if os.path.exists(path):
            if not os.path.isdir(path):
                print 'Path is not a directory, unable to save'
                return
        else:
            os.makedirs(path)

        print 'Saving Training Set...'
        for filename, article_dict in training_dictionary:
            categories = article_dict['categories']
            article_body = article_dict['article_body']

            fo = open(filename, "w")

            fo.write('---classification-training-metadata---\n')
            for category in categories:
                fo.write("category: " + category + '\n')

            fo.write('---classification-training-metadata---\n')

            fo.write(article_body + '\n')
            fo.close()
        print 'Done'

    def download_training_set(self):
        """
        Downloads a set of training data consisting of all news.ucsc.edu articles and stores them
        in subfolders of year and month in a directory called training_articles/
        :return:
        """
        base_folder = 'training_articles/'
        articles_dictionary = self.article_scraper.get_articles_dictionary()
        training_dictionary = dict()
        print "Writing Training Articles..."

        if not os.path.exists(base_folder):
            os.makedirs(base_folder)

        for article_url, article_dict in articles_dictionary.iteritems():
            categories = article_dict['categories']
            article_body = article_dict['article_body_no_html']
            file_name = article_dict['file_name']

            training_dictionary[file_name] = {'categories': categories,
                                              'article_body': article_body}
        return training_dictionary

    def read_training_dictionary(self, training_set_path='training_articles/'):
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

    def dictionary_to_xytrain(self, training_dictionary):
        """
        Takes a dictionary of training articles and splits them up into xtrain and ytrain sets. Also returns
        a dictionary of indexes and their corresponding categories.
        :param training_dictionary:
        :return:
        """
        cat_num = 0

        xtrain = []
        categories_list = []
        categories_dict = dict()

        for filename, article_dict in training_dictionary.iteritems():
            categories = article_dict['categories']
            article_body = article_dict['article_body']

            # print article_body
            categories_sub_list = []

            xtrain.append(article_body)

            for category in categories:
                if category not in categories_dict:
                    categories_dict[category] = cat_num
                    cat_num += 1

                categories_sub_list.append(categories_dict[category])

            categories_list.append(categories_sub_list)

        ytrain = MultiLabelBinarizer().fit_transform(categories_list)

        inv_categories_dict = {v: k for k, v in categories_dict.items()}

        return xtrain, ytrain, inv_categories_dict

    def slice_training_set(self, xtrain, ytrain, slice_start, slice_end):
        """
        Takes the x and y training lists, and slices them into two sets (4 total).  The list from the
        start index (inclusive) to the end index (exclusive) forms one of the new sets, and the other elements
        form the other.
        :param xtrain:
        :param ytrain:
        :param slice_start:
        :param slice_end:
        :return:
        """
        inner_xtrain = xtrain[slice_start:slice_end]
        inner_ytrain = ytrain[slice_start:slice_end]

        outer_xtrain = xtrain[:slice_start] + xtrain[slice_end:]
        outer_ytrain = ytrain[:slice_start] + ytrain[slice_end:]

        return inner_xtrain, inner_ytrain, outer_xtrain, outer_ytrain

    def kfold_validation(self, k, training_dictionary):
        """
        performs k fold validation on the given training set and prints the statistics.
        :param k:
        :param training_dictionary:
        :return:
        """
