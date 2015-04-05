# -*- coding: utf-8 -*-

"""
Miscellaneous Helpers and Utils
===============================

"""

from __future__ import division

import sys
import csv
from datetime import datetime
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy import optimize
from IPython.display import clear_output
from sklearn.metrics import mean_squared_error


### Developer-specific configurations

#: Path to the CSV file containing all answers.
DATA_ANSWERS_PATH = '../data/answers_all.csv'

#: Path to the CSV file containing users (see :func:`generate_users`).
DATA_USERS_PATH = '../data/users.csv'


### Other configurations

#: Columns currently not used in models. They are ignored in
#: the :func:`prepare_data` so that the memory requirements are lower.
IGNORED_COLUMNS = [
    'place_map', 'language', 'options'
]

#: Columns renamed in models.
RENAMED_COLUMNS = {
    'user': 'user_id',
    'place_asked': 'place_id',
}

#: Names of columns in generated CSV containing users.
USERS_COLUMNS = [
    'user_id', 'first_answer_id', 'first_answer_inserted'
]


#: DateTime format of the field `inserted`.
DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'


def echo(msg, clear=True):
    """Prints the passed message. If the parameter `clear` is set to
    :obj:`True`, IPython's console output is cleared beforhand.

    :param msg: Message to write to standard output.
    :type msg: string
    :param clear: Clear the output beforhand (works only for IPython'
        console output).
    :type clear: bool
    """
    if clear:
        clear_output()
    print msg
    sys.stdout.flush()


def load_data(path=DATA_ANSWERS_PATH, users_path=DATA_USERS_PATH,
              limit=10000, offset=0):
    """Loads CSV file into :class:`pandas.DataFrame`.

    :param path: Path to the CSV file with the answers of users.
    :type path: str
    :param limit: Limit the number of loaded rows.
    :type limit: int
    :param offset: Number of loaded rows.
    :type offset: int
    :param users_path: Path to the CSV file containing all users.
        This is neccessary so that first answers of users are truly first.
        The CSV file is used for filtering the answers correctly.
    :type users_path: string
    """
    if users_path is None:
        data = pd.read_csv(path)[offset:offset+limit]
        return prepare_data(data)

    users = pd.read_csv(users_path)
    new_users = users[users['first_answer_id'] > offset]

    data = prepare_data(pd.read_csv(path)[offset:])
    return data[data['user_id'].isin(new_users['user_id'])][:limit]


def generate_users(data, users_path=DATA_USERS_PATH):
    """Exports users from given data into CSV file.

    :param data: Data to export users from.
    :type data: :class:`pandas.DataFram`
    :param users_path: Where to save the exported users.
    :type users_path: string
    """
    users = {}
    for index, row in data.iterrows():
        if row.user_id not in users:
            users[row.user_id] = (row.id, row.inserted)

    with open(users_path, 'w') as out:
        csv_out = csv.writer(out)
        csv_out.writerow(USERS_COLUMNS)
        for user_id, (answer_id, answer_inserted) in users.items():
            csv_out.writerow((user_id, answer_id, answer_inserted))


def prepare_data(data):
    """Prepares data for models (e.g. adds *is_correct* column).

    :param data: The object containing data.
    :type data: :class:`pandas.DataFrame`.
    """
    data.rename(columns=RENAMED_COLUMNS, inplace=True)
    data['is_correct'] = (data['place_id'] ==
                          data['place_answered']).astype(int)
    return data[[column for column in data.columns
                 if column not in IGNORED_COLUMNS]].copy()


def first_answers(data):
    """Modifies the given data object so that only the first answers of
    students are contained in the data.

    :param data: The object containing data.
    :type data: :class:`pandas.DataFrame`.
    """
    data = data.sort(
        ['user_id', 'place_id', 'inserted']
    ).groupby(
        ['user_id', 'place_id']
    ).first()
    return data.reset_index()


def last_answers(data):
    """Modifies the given data object so that only the last answers of
    students are contained in the data.

    :param data: The object containing data.
    :type data: :class:`pandas.DataFrame`.
    """
    data = data.sort(
        ['user_id', 'place_id', 'inserted']
    ).groupby(
        ['user_id', 'place_id']
    ).last()
    return data.reset_index()


def unknown_answers(data):
    """Modifies the given data set so that only the answers the user
    didn't answer correctly at first are contained in the data.

    :param data: The object containing data.
    :type data: :class:`pandas.DataFrame`.
    """
    def tuplify_user_place(serie):
        return (serie['user_id'], serie['place_id'])

    first = first_answers(data)
    unknowns = first[first['is_correct'] == 0]

    all_user_place = data.apply(tuplify_user_place, axis=1)
    unk_user_place = unknowns.apply(tuplify_user_place, axis=1)

    mask = all_user_place.isin(unk_user_place)
    return data[mask].reset_index(drop=True)


def add_spacing(data):
    """Appends the given data set with spacing information of earch item.

    :param data: The object containing data.
    :type data: :class:`pandas.DataFrame`.
    """
    answers = {}
    data['spacing'] = np.inf

    def set_spacing(row):
        index = (row.user_id, row.place_id)
        if index in answers:
            data.loc[row.name, 'spacing'] = \
                time_diff(row.inserted, answers[index])
        answers[index] = row.inserted

    data.sort(['inserted']).apply(set_spacing, axis=1)
    return data


def split_data(data, ratio=0.7):
    """Splits data into test set and training set.

    :param data: The object containing data.
    :type data: :class:`pandas.DataFrame`.
    :param ratio: What portion of data to include in the training set
        and the test set. :obj:`0.5` means that the data will be
        distributed equaly.
    :type ratio: float
    """
    threshold = int(len(data) * ratio)
    return data[:threshold], data[threshold:]


def shuffle_data(data):
    """Shuffles the rows in the data set.

    :param data: The object containing data.
    :type data: :class:`pandas.DataFrame`.
    """
    items = np.random.permutation(data.index)
    return data.reindex(items)


def random_data(data, limit=1000):
    """Randomly selects rows from given data set.

    :param data: The object containing data.
    :type data: :class:`pandas.DataFrame`.
    """
    items = np.random.permutation(data.index)[:limit]
    return data.ix[items]


def add_ones(data):
    """Appends the data set with a column containing *ones*.

    :param data: The object containing data.
    :type data: :class:`pandas.DataFrame`.
    """
    columns = list(data.columns)
    data['ones'] = np.ones(len(data))
    data = data[['ones'] + columns]
    return data


def rmse(y_true, y_pred):
    """Calculates Root Mean Squered Error for given vectors.

    :param y_true: Vector containing *true* values.
    :type y_true: list, :class:`numpy.array` or :class:`pandas.Series`
    :param y_pred: Vector containing *predicted* values.
    :type y_true: list, :class:`numpy.array` or :class:`pandas.Series`
    """
    return np.sqrt(mean_squared_error(y_true, y_pred))


def sigmoid(x):
    """Implementation of the sigmoid (logistic) function.

    :param x: Function parameter.
    :type x: int or float
    """
    return 1 / (1 + np.exp(-x))


def cost(theta, data, y):
    """Vectorized implementation of the cost function for logistic
    regression.

    :param theta: Vector with parameters of the hyphotesis function.
    :type theta: list, :class:`numpy.array` or :class:`pandas.Series`
    :param data: Data object containing a set of training examples.
    :type data: :class:`pandas.DataFrame` or :class:`numpy.matrix`
    :param y: The array containing classifications of training examples.
    :type y: list, :class:`numpy.array` or :class:`pandas.Series`
    """
    hyph = sigmoid(np.dot(data, theta))
    calc = (-1 * y) * np.log(hyph) - (1 - y) * np.log(1 - hyph)
    return sum(calc) / len(y)


def grad(theta, data, y):
    """Vectorized implementation of the algorithm that evaluates
    gradient for given parameters.

    :param theta: Vector with parameters of the hyphotesis function.
    :type theta: list, :class:`numpy.array` or :class:`pandas.Series`
    :param data: Data object containing a set of training examples.
    :type data: :class:`pandas.DataFrame` or :class:`numpy.matrix`
    :param y: The array containing classifications of training examples.
    :type y: list, :class:`numpy.array` or :class:`pandas.Series`
    """
    hyph = sigmoid(np.dot(data, theta))
    return np.dot(hyph - y, data) / y.size


def find_theta(theta, data, y, maxiter=1000):
    """Runs BFGS algoritm that minimizes cost function and returns
    minimized theta.

    :param theta: Vector with parameters of the hyphotesis function.
    :type theta: list, :class:`numpy.array` or :class:`pandas.Series`
    :param data: Data object containing a set of training examples.
    :type data: :class:`pandas.DataFrame` or :class:`numpy.matrix`
    :param y: The array containing classifications of training examples.
    :type y: list, :class:`numpy.array` or :class:`pandas.Series`
    :param maxiter: Maximum number of iterations to perform.
    :type maxiter: int
    """
    return optimize.fmin_bfgs(
        cost, theta, fprime=grad, args=(data, y), maxiter=maxiter
    )


def memory_strength(practices, spacing_rate=0.2, decay_rate=0.18):
    """Calculates memory strength based on given vector of practices.
    Each element *t_i* in the vector indicates how long ago the *i*-th
    practice occured.

    :param practices: Vector containing all prior practices.
        Each practice is represented as the number of seconds that
        passed since the student answered the question.
    :type practices: list, :class:`numpy.array` or :class:`pandas.Series`
    :param spacing_rate: The significance of the spacing effect. Lower
        values make the effect less significant. If the spacing rate
        is set to zero, the model is unaware of the spacing effect.
    :type spacing_rate: float
    :param decay_rate: The significance of the forgetting effect. Higher
        values of decay rate make the students forget the item faster
        and vice versa.
    :type decay_rate: float
    """
    decays = []
    strengths = [-np.inf]

    get_decay = lambda s: spacing_rate * np.exp(s) + decay_rate

    for i in range(len(practices)):
        decays.append(get_decay(strengths[i]))
        rates = practices[:i+1] ** -np.array(decays)
        strengths.append(np.log(sum(rates)))

    return strengths[-1]


def retrieval_prob(strength, tau=-0.704, s=0.255):
    """Returns the probability of item retrieval based on the *strength*
    of the memory.

    :param strength: Strength of the memory.
    :type strength: float
    """
    val = (tau - strength) / s
    return 1 / (1 + np.exp(val))


def automaticity_level(t):
    """Calculates the level of automaticity (the effort the user had to
    make to retrieve the item from memory) based on response time. The values
    of parameters are based on some statistical experiments.

    :param t: Response time in seconds.
    :type t: float or int
    """
    result = ((4.07446031e-03 * t) -
              (1.18475468e+00 * t ** (1 / 2)) -
              (1.01545130e-05 * t ** (3 / 2)) +
              (4.68002306e+00 * t ** (1 / 3)))
    return max(result - 12.23, 0)


def merge_dicts(*dicts):
    """Merges multiple *dicts* into one.

    :param *dicts: Dictionaries given as positional arguments.
    """
    items = []
    for d in dicts:
        items.extend(d.items())
    merged = {}
    for key, value in items:
        merged[key] = value
    return merged


def time_diff(datetime1, datetime2):
    """Returns difference between the arguments `datetime1` and
    `datetime2` in seconds.

    :type datetime1: string or datetime
    :type datetime2: string or datetime
    """
    if isinstance(datetime1, basestring):
        datetime1 = to_datetime(datetime1)
    if isinstance(datetime2, basestring):
        datetime2 = to_datetime(datetime2)
    return (datetime1 - datetime2).total_seconds()


def to_datetime(date_str):
    """Deserializes given datetime.

    :param date_str: DateTime given as string.
    :type date_str: str
    """
    return datetime.strptime(date_str, DATETIME_FORMAT)


def reverse_enumerate(values):
    """Enumerate over an iterable in reverse order while
    retaining proper indexes.

    :param values: List of objects.
    :type values: iterable
    """
    count = len(values)
    for value in values:
        count -= 1
        yield count, value


class cached_property(object):
    """A decorator that converts a method into a property. The
    function wrapped is called the first time to retrieve the result
    and then that calculated result is used the next time you access
    the value::

        class Person(object):

            @cached_property
            def stats(self):
                # calculate something important here
                return Stats(self.domain)

    The class has to have a `__dict__` in order for this property to
    work.
    """

    def __init__(self, func, name=None, doc=None):
        self.__name__ = name or func.__name__
        self.__module__ = func.__module__
        self.__doc__ = doc or func.__doc__
        self.func = func

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        value = obj.__dict__.get(self.__name__)
        if value is None:
            value = self.func(obj)
            obj.__dict__[self.__name__] = value
        return value


class keydefaultdict(defaultdict):
    """Defaultdict that takes inserted key as an argument.

    Example::

        d = keydefaultdict(C)
        d[x]  # returns C(x)

    """

    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError(key)
        else:
            args = key if isinstance(key, tuple) else (key,)
            ret = self[key] = self.default_factory(*args)
            return ret
