#!/usr/bin/env python2
import exceptions
import time
import md5
import json
import MySQLdb
import numpy as np
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



def add_fixed_params(point):
    return fixed[:2] + point[:6] + fixed[2:] + point[6:]


def strip_fixed_params(point):
    return point[2:8] + point[20:]


def compute_fixed_params():
    fixed_params = []
    for i in range(2):
        fixed_params.append((fixed[i], i))
    for i in range(8, 20):
        fixed_params.append((fixed[i - 6], i))

    return fixed_params


def create_id(params):
    params_json = json.dumps(params)
    h = md5.new()
    h.update(params_json)
    fcn_id = h.hexdigest()
    return fcn_id


def compute_space(X_0):
    space = []
    df = np.array(X_0)
    for i in range(0, len(X_0[0])):
        space.append((np.min(df[:, i]), np.max(df[:, i])))

    return space


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


def is_inspace(x):
    fixed_params = compute_fixed_params()
    for param, position in fixed_params:
        if x[position] != param:
            return False
    for param in x:
        if param < 0:
            return False

    return True


def parse_params(params_string):
    return [float(x) for x in params_string.strip('[]').split(',')]


DB_CONF = dict(
    host='2a03:b0c0:1:d0::2c4f:1001',
    user='root',
    passwd='P@ssw0rd',
    db='points_prod')


def main():
    db = MySQLdb.connect(**DB_CONF)
    cur = db.cursor()
    space = discrete_space()

    while True:
        try:
            cur.execute(
                '''SELECT params, metric_2, id FROM points_results WHERE metric_2 IS NOT NULL AND tag = 'discrete' '''
            )
            data = cur.fetchall()

            X_0 = []
            y_0 = []
            ids = []
            for params, metric, id in data:
                new_X = parse_params(params)
                if is_inspace(new_X) and space.__contains__(strip_fixed_params(new_X)):
                    X_0.append(strip_fixed_params(new_X))
                    y_0.append(float(metric))
                    ids.append(id)

            if len(y_0) == 0:
                min_index = -1
            else:
                min_index = ids[np.argmin(y_0)]

            opt_rf = Optimizer(space, RandomForestRegressor(n_estimators=500, max_depth=7, n_jobs=-1))
            opt_gb = Optimizer(space, GradientBoostingQuantileRegressor(base_estimator=GradientBoostingRegressor(n_estimators=100, max_depth=4, loss='quantile')))
            print 'Start to tell points.'
            print len(X_0)
            if len(X_0) != 0:
                opt_rf.tell(X_0, y_0)
                opt_gb.tell(X_0, y_0)

                alpha = 1e-7
                while True:
                    try:
                        opt_gp = Optimizer(space,
                                           GaussianProcessRegressor(
                                               alpha=alpha, normalize_y=True, noise='gaussian'))
                        opt_gp.tell(X_0, y_0)
                        break
                    except BaseException:
                        alpha *= 10
            else:
                opt_gp = Optimizer(space,
                                    GaussianProcessRegressor(
                                           alpha=1e-7, normalize_y=True, noise='gaussian'))

            optimizers = ['rf', 'gb', 'gp']

            fraction = len(optimizers)

            print 'Start to ask for points.'
            batch_size = (target_points_in_time) / fraction * fraction
            points = opt_rf.ask(n_points=batch_size / fraction, strategy='cl_mean') + opt_gb.ask(
                n_points=batch_size / fraction, strategy='cl_mean') + opt_gp.ask(
                    n_points=batch_size / fraction, strategy='cl_mean')

            #params_rect = [70, 170, 205, 205, 280, 245, 305, 240, 40, 40, 150, 150, 2, 2, 80, 80, 150, 150, 2, 2, 35, 35, 35, 35, 10, 10, 35, 35, 35, 35, 10, 10, 35, 35, 35, 35, 10, 10, 35, 35, 35, 35, 10, 10, 35, 35, 35, 35, 10, 10, 35, 35, 35, 35, 10, 10]

            # modify points
            points = [add_fixed_params(p) for p in points]
        
            #points.append(params_rect)

            for i in range(fraction):
                for j in range(batch_size / fraction):
                    index = i * (batch_size / fraction) + j
                    cur.execute(
                        '''INSERT INTO points_results (geo_id, params, optimizer, author, resampled, status, tag, min_id) VALUES (%s, %s, %s, 'Artem', 37, 'waiting', 'discrete', %s) ''',
                        (create_id(points[index]), str(points[index]),
                         optimizers[i], min_index))

            '''
            for i in range(30):
                index = batch_size + i
                cur.execute(
                        "INSERT INTO points_results (geo_id, params, optimizer, author, resampled, status, tag) VALUES (%s, %s, 'random', 'Artem', 37, 'waiting', 'discrete')",
                        (create_id(points[index]), str(points[index])))
            '''
            db.commit()

            time.sleep(5 * 60)

        except exceptions.KeyboardInterrupt:
            db.close()
            break


if __name__ == '__main__':
    main()
