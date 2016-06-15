import os
import re
import numpy as np
from time import time
from scraper import NewsSiteScraper
from prettytable import PrettyTable
from random import randint
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.multiclass import OneVsRestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC


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

        self.vectorizer = TfidfVectorizer(ngram_range=(1, 5))
        self.clf = OneVsRestClassifier(LinearSVC())

    @staticmethod
    def save_training_set(training_dictionary, path='training_articles/'):
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
        for filename, article_dict in training_dictionary.iteritems():
            categories = article_dict['categories']
            article_body = article_dict['article_body'] or ''

            fo = open(path + filename, "w")

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

        num_no_categories = 0

        for root, subdirs, files in os.walk(training_set_path):

            for filename in files:
                file_path = os.path.join(root, filename)
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
                                if matches[0] != 'Regular News' \
                                        and matches[0] != 'Secondary Story' \
                                        and matches[0] != 'Home Page':
                                    categories.append(matches[0])
                        else:
                            article_body += line

                    article_dict['categories'] = categories
                    article_dict['article_body'] = article_body

                    if len(article_dict['categories']) > 0:
                        articles_dictionary[file_path] = article_dict
                    else:
                        num_no_categories += 1
        print "Number of articles with no categories (removed): " + str(num_no_categories)
        return articles_dictionary

    def dictionary_to_xytrain(self, training_dictionary, randomize=False):
        """
        Takes a dictionary of training articles and splits them up into xtrain and ytrain sets. Also returns
        a dictionary of indexes and their corresponding categories.
        Parameters
        ----------
        training_dictionary
        randomize

        Returns
        -------

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

        if randomize:
            xtrain, ytrain = self.shuffle_xtrain_ytrain(xtrain, categories_list)

        else:
            ytrain = categories_list

        ytrain = MultiLabelBinarizer().fit_transform(ytrain)

        inv_categories_dict = {v: k for k, v in categories_dict.items()}

        return xtrain, ytrain, inv_categories_dict

    @staticmethod
    def dictionary_to_xtest(test_dictionary):
        """
        Takes a dictionary of articles and returns a list of article bodies and
        a corresponding list of filenames, so they can be used to access the original dictionaries
        :param test_dictionary:
        :return:
        """
        xtest = []
        filenames = []

        for filename, article_dict in test_dictionary.iteritems():
            article_body = article_dict['article_body_no_html']

            xtest.append(article_body)
            filenames.append(filename)

        return xtest, filenames

    @staticmethod
    def slice_training_set(xtrain, ytrain, slice_start, slice_end):
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
        outer_ytrain = np.concatenate((ytrain[:slice_start], ytrain[slice_end:]))

        return inner_xtrain, inner_ytrain, outer_xtrain, outer_ytrain

    @staticmethod
    def shuffle_xtrain_ytrain(xtrain, ytrain):
        """
        Shuffles Xtrain and Ytrain randomly and returns the scrambled versions
        Parameters
        :param xtrain:
        :param ytrain:
        :return:
        """
        new_xtrain = []
        new_ytrain = []

        while len(xtrain) > 0:
            next_index = randint(0, len(xtrain) - 1)
            new_xtrain.append(xtrain.pop(next_index))
            new_ytrain.append(ytrain.pop(next_index))

        return new_xtrain, new_ytrain

    @staticmethod
    def multilabel_confusion_matrix(y_true, y_pred, cutoff, class_labels=None):
        """
        Prints a confusion matrix consisting of True positives, False Positives, False Negatives, and
        True negatives for each class
        :param y_true:
        :param y_pred:
        :param cutoff:
        :param class_labels:
        :return:
        """

        # Initialize the confusion matrix

        confusion_matrix = []

        totals = [0, 0, 0, 0]

        for index in xrange(len(y_true[0])):
            confusion_matrix.append([0, 0, 0, 0])

        for article_index in xrange(len(y_true)):
            predicted_categories_list = y_pred[article_index]
            for index in xrange(len(predicted_categories_list)):
                if predicted_categories_list[index] >= cutoff:
                    if y_true[article_index][index] == 1:
                        # print "true positive"
                        confusion_matrix[index][0] += 1
                        totals[0] += 1
                    else:
                        # print "false positive"
                        confusion_matrix[index][1] += 1
                        totals[1] += 1
                else:
                    if y_true[article_index][index] == 1:
                        # print "false negative"
                        confusion_matrix[index][2] += 1
                        totals[2] += 1
                    else:
                        # print "true negative"
                        confusion_matrix[index][3] += 1
                        totals[3] += 1

        table = PrettyTable(['Labels', 'True Positives',
                             'False Positives', 'False Negatives',
                             'True Negatives', 'Precision',
                             'Recall', 'F1'
                             ])

        total_precision = 0
        precision_samples = 0
        total_recall = 0
        recall_samples = 0

        for index in xrange(len(confusion_matrix)):

            # Precision = True Positives / True Positives + False Positives
            # Recall    = True Positives / True Positives + False Negatives

            if confusion_matrix[index][1] == 0:
                precision = 1
            else:
                precision = (confusion_matrix[index][0] + 0.0) / \
                            (confusion_matrix[index][0] + confusion_matrix[index][1])

            total_precision += precision
            precision_samples += 1

            if confusion_matrix[index][2] == 0:
                recall = 1
            else:
                recall = (confusion_matrix[index][0] + 0.0) / \
                         (confusion_matrix[index][0] + confusion_matrix[index][2])
            total_recall += recall
            recall_samples += 1

            if precision + recall == 0:
                f1_score = 0
            else:
                f1_score = 2 * ((precision * recall) / (precision + recall + 0.0))

            if class_labels is None:
                table.add_row([index, ] + confusion_matrix[index] + [precision, recall])
            else:
                table.add_row([class_labels[index], ] + confusion_matrix[index] + [precision, recall, f1_score])

        macro_avg_precision = (total_precision + 0.0) / precision_samples
        macro_avg_recall = (total_recall + 0.0) / recall_samples
        macro_avg_f1 = 2 * ((macro_avg_precision * macro_avg_recall) / (macro_avg_precision + macro_avg_recall + 0.0))

        table.add_row(['Macro Averaged Totals', ] + [str(i) for i in totals] +
                      [str(macro_avg_precision), str(macro_avg_recall), str(macro_avg_f1)])

        micro_avg_precision = (totals[0] + 0.0) / (totals[0] + totals[1])
        micro_avg_recall = (totals[0] + 0.0) / (totals[0] + totals[2])
        micro_avg_f1 = 2 * ((micro_avg_precision * micro_avg_recall) / (micro_avg_precision + micro_avg_recall + 0.0))

        table.add_row(['Micro Averaged Totals', ] + [str(i) for i in totals] +
                      [str(micro_avg_precision), str(micro_avg_recall), str(micro_avg_f1)])

        print table

    def kfold_validation(self, k, xtrain, ytrain, inv_categories_dict):
        """

        :param k:
        :param xtrain:
        :param ytrain:
        :param inv_categories_dict:
        :return:
        """
        slice_size = len(xtrain) / k

        labels = []

        # create a list of labels
        for index in xrange(len(inv_categories_dict.keys())):
            labels.append(inv_categories_dict[index])

        print 'Starting {}-fold Cross Validation.'.format(k)
        print 'Total sample size: {}. Slice Size: {}'.format(len(xtrain), slice_size)

        for x in xrange(0, k):
            slice_start = x * slice_size
            slice_end = (x + 1) * slice_size
            print 'Run {} of {}-fold Cross Validation'.format(x + 1, k)

            inner_xtrain, inner_ytrain, outer_xtrain, outer_ytrain = \
                self.slice_training_set(xtrain, ytrain, slice_start, slice_end)

            self.fit(outer_xtrain, outer_ytrain)
            predicted = self.predict(inner_xtrain)
            print self.multilabel_confusion_matrix(inner_ytrain, predicted, 1, labels)

        print '{}-fold Cross Validation Complete.'.format(k)

    def fit(self, xtrain, ytrain):
        """

        :param xtrain:
        :param ytrain:
        :return:
        """
        x_train = self.vectorizer.fit_transform(xtrain)
        print 'training classifier...'
        t0 = time()
        self.clf.fit(x_train, ytrain)
        train_time = time() - t0
        print("train time: %0.3fs" % train_time)

    def predict(self, xtest):
        """

        :param xtest:
        :return:
        """
        x_test = self.vectorizer.transform(xtest)
        print 'predicting categories...'
        t0 = time()
        predicted = self.clf.predict(x_test)
        predict_time = time() - t0
        print("prediction time: %0.3fs" % predict_time)
        return predicted
