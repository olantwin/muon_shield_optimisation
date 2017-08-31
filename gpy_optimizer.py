#!/usr/bin/env python2
import exceptions
import time
import md5
import json
import MySQLdb
import numpy as np
import GPyOpt

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


def continuous_space():
    dZgap = 10
    zGap = dZgap / 2  # halflengh of gap

    space = []
    number = 0
    for _ in range(6):
        space.append({'name': 'var{}'.format(number), 'type': 'continuous', 'domain': (20 + zGap, 300 + zGap)})
        number += 1

    for _ in range(6):
        for __ in range(4):
            space.append({'name': 'var{}'.format(number), 'type': 'continuous', 'domain': (10, 250)})
            number += 1
        for __ in range(2):
            space.append({'name': 'var{}'.format(number), 'type': 'continuous', 'domain': (2, 100)})
            number += 1

    return space

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

    while True:
        try:
            cur.execute(
                '''SELECT params, metric_1 FROM points_results WHERE metric_1 IS NOT NULL AND tag = 'GPyOpt' '''
            )
            data = cur.fetchall()

            X_0 = []
            y_0 = []
            for params, metric in data:
                new_X = parse_params(params)
                if is_inspace(new_X):
                    X_0.append(strip_fixed_params(new_X))
                    y_0.append(float(metric))

            space = continuous_space()
            BO = GPyOpt.methods.BayesianOptimization(f=lambda x: np.sum(x),  
                                            domain = space,                  
                                            acquisition_type = 'EI',              
                                            normalize_Y = True,
                                            initial_design_numdata = 10,
                                            evaluator_type = 'local_penalization',
                                            batch_size = target_points_in_time,
                                            num_cores = 1,
                                            acquisition_jitter = 0,
                                            X=np.array(X_0),
                                            Y=np.array(y_0).reshape(-1, 1)) 
            print "Start"
            BO.run_optimization(1)
            print "End"
            points = list(BO.suggested_sample)
            points = [list(x) for x in points]
            # modify points
            points = [add_fixed_params(p) for p in points]

            for point in points:
                cur.execute(
                        '''INSERT INTO points_results (geo_id, params, optimizer, author, resampled, status, tag) VALUES (%s, %s, 'gp', 'Artem', 37, 'waiting', 'GPyOpt') ''',
                        (create_id(point), str(point)))
            db.commit()
            time.sleep(30 * 60)

        except exceptions.KeyboardInterrupt:
            db.close()
            break


if __name__ == '__main__':
    main()
