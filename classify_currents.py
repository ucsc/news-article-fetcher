import pprint
import os
import datetime
import re
import numpy as np
from time import time
import pprint
from classifier import ArticleClassifier
from utils import GremlinZapper, ArticleUtils
from sklearn.externals import joblib

from HTMLParser import HTMLParser

np.set_printoptions(threshold=np.nan)


class MLStripper(HTMLParser):
    def error(self, message):
        pass

    def __init__(self):
        self.reset()
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return ''.join(self.fed)


def read_currents_test_data(test_set_path='test_articles/'):
    """

    :param test_set_path:
    :return:
    """
    metadata_regex = re.compile(r"^---$")
    gzapper = GremlinZapper()

    reading_metadata = 0
    currents_articles_dictionary = dict()

    if not os.path.exists(test_set_path):
        print test_set_path + "path does not exist"
        print os.getcwd()
        return

    for root, subdirs, files in os.walk(test_set_path):
        for filename in files:
            file_path = os.path.join(root, filename)

            if reading_metadata is True:
                exit()

            article_dict = dict()
            metadata_string = ''

            with open(file_path, 'r') as infile:
                reading_metadata = 0
                article_body = ''
                for line in infile:
                    if metadata_regex.match(line) is not None:
                        reading_metadata += 1
                    elif reading_metadata == 1:
                        metadata_string += line
                    else:
                        article_body += line

                article_dict['metadata'] = metadata_string
                article_dict['article_body'] = article_body
                article_body_no_html = strip_tags(article_body)
                article_body_no_html = gzapper.zap_string(article_body_no_html)
                article_dict['article_body_no_html'] = article_body_no_html

                currents_articles_dictionary[filename] = article_dict

    return currents_articles_dictionary


def setup_and_save_classifier():
    print "Setting up classifier"
    if os.path.exists('joblib/'):
        if not os.path.isdir('joblib/'):
            print 'Path is not a directory, unable to save'
            exit()
    else:
        os.makedirs('joblib/')
        "Creating directory joblib/ to store classifier"

    cls = ArticleClassifier()
    training_dictionary = cls.read_training_dictionary()
    xtrain, ytrain, inv_categories_dict = cls.dictionary_to_xytrain(training_dictionary)
    cls.fit(xtrain, ytrain)

    print "saving classifier"
    joblib.dump(cls, 'joblib/news-classifier.pkl')
    joblib.dump(inv_categories_dict, 'joblib/inv_categories_dict.pkl')
    return cls, inv_categories_dict


def load_classifier():
    t0 = time()
    print "Loading Classifier into memory"
    classifier = joblib.load('joblib/news-classifier.pkl')
    inv_categories_dict = joblib.load('joblib/inv_categories_dict.pkl')
    load_time = time() - t0
    print("load time: %0.3fs" % load_time)
    return classifier, inv_categories_dict


def classify_articles_from_dictionary(test_articles_dictionary):
    """
    classifies the article_body keys of each article dictionary in the test set and adds
    a category key and a list of categories to the subdictionary
    :param test_articles_dictionary:
    :param xtrain:
    :param ytrain:
    :return:
    """
    cls = None
    inv_categories_dict = None

    if not os.path.exists('joblib/'):
        cls, inv_categories_dict = setup_and_save_classifier()

    if cls is None or inv_categories_dict is None:
        cls, inv_categories_dict = load_classifier()

    xtest, filenames = cls.dictionary_to_xtest(test_articles_dictionary)

    predicted = cls.predict(xtest)

    for article_index in xrange(len(predicted)):
        predicted_categories_list = predicted[article_index]
        predicted_categories_labels = []
        for index in xrange(len(inv_categories_dict.keys())):
            if predicted_categories_list[index] > 0:
                predicted_categories_labels.append(inv_categories_dict[index])
        test_articles_dictionary[filenames[article_index]]['categories'] = predicted_categories_labels

    return test_articles_dictionary


def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()

if os.path.exists('categorized_articles/'):
    if not os.path.isdir('categorized_articles/'):
        print 'Path is not a directory, unable to save'
        exit()
else:
    os.makedirs('categorized_articles/')

cls = ArticleClassifier()
utils = ArticleUtils()

test_dictionary = read_currents_test_data()

results_dict = classify_articles_from_dictionary(test_dictionary)

if os.path.exists('categorized_articles/'):
    if not os.path.isdir('categorized_articles/'):
        print 'Path is not a directory, unable to save'
        exit()
else:
    os.makedirs('categorized_articles/')

for filename, article_dict in results_dict.iteritems():
    categories = article_dict['categories']
    fo = open('categorized_articles/' + filename, "w")
    fo.write('---\n')
    fo.write(article_dict['metadata'])

    fo.write("categories:\n")
    for category_name in categories:
        category_nicename = utils.get_nicename(category_name)
        fo.write("  - name: " + category_name + "\n")
        fo.write("    nicename: " + category_nicename + "\n")

    fo.write('---\n')
    fo.write(article_dict['article_body'])
    fo.close()

