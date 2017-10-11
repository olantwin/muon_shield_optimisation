#!/usr/bin/env python2
import exceptions
import time
import md5
import json
import argparse
import MySQLdb
import numpy as np
import argparse
from sklearn.ensemble import GradientBoostingRegressor
from skopt import Optimizer
from skopt.learning import GaussianProcessRegressor
from skopt.learning import RandomForestRegressor
from skopt.learning import GradientBoostingQuantileRegressor
from skopt.space.space import Integer, Space

target_points_in_time = 10
fixed = [
    70.0, 170.0, 40.0, 40.0, 150.0, 150.0, 2.0, 2.0, 80.0, 80.0, 150.0, 150.0,
    2.0, 2.0
]


class Dummy_Optimizer(object):

    def __init__(self, dimensions):
        self.space = Space(dimensions)

    def tell(self, x, y, fit=True):
        pass

    def ask(self, n_points=None, strategy='cl_min'):
        return self.space.rvs(n_samples=n_points)


def add_fixed_params(point):
    return fixed[:2] + point[:6] + fixed[2:] + point[6:]


def strip_fixed_params(point):
    return point[2:8] + point[20:]


def create_id(params):
    params_json = json.dumps(params)
    h = md5.new()
    h.update(params_json)
    fcn_id = h.hexdigest()
    return fcn_id


def discrete_space():
    dZgap = 10
    zGap = dZgap / 2  # halflengh of gap
    return Space(6 * [
        Integer(170 + zGap, 300 + zGap)  # magnet lengths
    ] + 6 * (
        2 * [
            Integer(10, 100)  # dXIn, dXOut
        ] + 2 * [
            Integer(20, 200)  # dYIn, dYOut
        ] + 2 * [
            Integer(2, 70)  # gapIn, gapOut
        ]))


def process_points(data, space):
    X_0 = []
    y_0 = []
    ids = []
    for params, metric, _id in data:
        new_X = parse_params(params)
        if space.__contains__(strip_fixed_params(new_X)):
            X_0.append(strip_fixed_params(new_X))
            y_0.append(float(metric))
            ids.append(_id)

    return X_0, y_0, ids

def parse_params(params_string):
    return [float(x) for x in params_string.strip('[]').split(',')]


DB_CONF = dict(
    host='2a03:b0c0:1:d0::2c4f:1001',
    user='root',
    passwd='P@ssw0rd',
    db='points_prod')


def main():
    parser = argparse.ArgumentParser(description='Start optimizer.')
    parser.add_argument('-opt', help='Write an optimizer.')

    db = MySQLdb.connect(**DB_CONF)
    cur = db.cursor()
    space = discrete_space()

    clf_type = parser.parse_args().opt
    tag = "discrete2_{opt}".format(opt=clf_type)

    if clf_type == 'rf':
        clf = Optimizer(
            space,
            RandomForestRegressor(n_estimators=500, max_depth=7, n_jobs=-1)
        )
    elif clf_type == 'gb':
        clf = Optimizer(
            space,
            GradientBoostingQuantileRegressor(
                base_estimator=GradientBoostingRegressor(
                    n_estimators=100,
                    max_depth=4,
                    loss='quantile'
                )
            )
        )
    elif clf_type == 'gp':
        clf = Optimizer(
            space,
            GaussianProcessRegressor(
                alpha=1e-7,
                normalize_y=True,
                noise='gaussian'
            )
        )
    elif clf_type == 'random':
        clf = Dummy_Optimizer(space)

    while True:
        try:
            cur.execute(
                '''SELECT params, metric_2, id '''
                '''FROM points_results '''
                '''WHERE metric_2 IS NOT NULL '''
                '''AND tag = '{}' '''.format(tag)
            )
            data = cur.fetchall()
            X_0, y_0, ids = process_points(data, space)

            if len(y_0) == 0:
                min_index = -1
            else:
                min_index = ids[np.argmin(y_0)]

            if len(X_0) != 0:
                clf.tell(X_0, y_0)

            print 'Start to ask for points.'
            points = clf.ask(
                n_points=target_points_in_time,
                strategy='cl_mean'
            )

            points = [add_fixed_params(p) for p in points]

            for j in range(target_points_in_time):
                cur.execute(
                    '''INSERT INTO points_results '''
                    '''(geo_id, params, optimizer, author, '''
                    '''resampled, status, tag, min_id) '''
                    '''VALUES (%s, %s, %s, 'Artem', 37, 'waiting', %s, %s) ''',
                    (create_id(points[j]), str(points[j]),
                     clf_type, tag, min_index)
                )

            db.commit()

            time.sleep(10 * 60)

        except exceptions.KeyboardInterrupt:
            db.close()
            break


if __name__ == '__main__':
    main()
