#!/usr/bin/env python2
import MySQLdb
from skopt import Optimizer
import numpy as np
import exceptions
import time
from skopt.learning import GaussianProcessRegressor
from skopt.learning import RandomForestRegressor
from skopt.learning import GradientBoostingQuantileRegressor
import md5
import json
from sklearn.ensemble import GradientBoostingRegressor

target_points_in_time = 100
min_fraction = 3./4
fixed = [70.0, 170.0, 40.0, 40.0, 150.0,150.0,2.0,2.0,80.0,80.0,150.0,150.0,2.0,2.0]

def add_fixed_params(point):
    return fixed[:2] + point[:6] + fixed[2:] + point[6:]


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

def is_inspace(x):
    fixed_params = compute_fixed_params()
    for param in fixed_params:
        if x[param[1]] != param[0]:
            return False
    for param in x:
        if param < 0:
            return False

    return True

def compute_space_low(X_0):
    low = [70.0, 170.0, 205.0, 205.0, 280.0, 245.0, 305.0, 240.0, 40.0, 40.0, 150.0, 150.0, 2.0, 2.0, 80.0, 80.0, 150.0, 150.0, 2.0, 2.0, 35.0, 35.0, 35.0, 35.0, 10.0, 10.0, 35.0, 35.0, 35.0, 35.0, 10.0, 10.0, 35.0, 35.0, 35.0, 35.0, 10.0, 10.0, 35.0, 35.0, 35.0, 35.0, 10.0, 10.0, 35.0, 35.0, 35.0, 35.0, 10.0, 10.0, 35.0, 35.0, 35.0, 35.0, 10.0, 10.0]
    hi = [70.0, 170.0, 208.39184522611606, 207.53816071811292, 281.8910656618243, 249.34702114707295, 304.403439538938, 245.90575227555678, 40.0, 40.0, 150.0, 150.0, 2.0, 2.0, 80.0, 80.0, 150.0, 150.0, 2.0, 2.0, 85.841851066965, 64.31496565785005, 27.802219875792293, 119.25247386380309, 8.108811398186436, 4.402705185702148, 67.14942990400131, 37.8996033216964, 117.62678379584712, 203.5633809445522, 14.506304034900413, 2.45195898281762, 7.221614450090608, 28.24581154011487, 34.28950718125761, 10.34685839306723, 74.0331130750956, 11.842670584084932, 0.9074198672528166, 23.3694606234195, 105.12739503273659, 3.317494355267905, 6.2994064239524885, 6.515045579521841, 11.707623167975962, 29.93041656517568, 230.9257892268813, 33.73211925562083, 7.732577775355542, 13.787181359953731, 31.648063489301446, 87.89784531395614, 187.02921494326026, 311.093876810969, 2.8251248638768125, 52.399472683397704]
    space = []
    for i in range(2, 8):
        space.append((min(low[i], hi[i]), max(low[i], hi[i])))
    for i in range(20, 56):
        space.append((min(low[i], hi[i]), max(low[i], hi[i])))

    return space

DB_CONF = dict(
    host='2a03:b0c0:1:d0::2c4f:1001',
    user='root',
    passwd='P@ssw0rd',
    db='points_prod'
)

def main():
    db = MySQLdb.connect(**DB_CONF)
    cur = db.cursor()


    while True:
        try:   
            cur.execute('''SELECT params, metric_1 FROM points_results WHERE metric_1 IS NOT NULL''')
            data = cur.fetchall()
        
            X_0 = []
            y_0 = []
            for element in data:
                new_X = map(float, element[0][1:-1].split(', '))
                if is_inspace(new_X):
                    X_0.append(new_X[2:8] + new_X[20:])
                    y_0.append(float(element[1]))

            space = compute_space(X_0)
            opt_rf = Optimizer(space, RandomForestRegressor(n_estimators = 100, max_depth = 10, n_jobs=-1),  acq_optimizer="sampling")
            opt_gb = Optimizer(space, GradientBoostingQuantileRegressor(base_estimator = GradientBoostingRegressor(n_estimators = 100, max_depth = 4, loss='quantile')), acq_optimizer="sampling")

            print 'Start to tell points.'
            opt_rf.tell(X_0, y_0)
            opt_gb.tell(X_0, y_0)

            alpha = 1e-7
            while True:
                try:
                    opt_gp = Optimizer(space, GaussianProcessRegressor(alpha=alpha, normalize_y=True))
                    opt_gb.tell(X_0, y_0)
                    break
                except:
                    alpha *= 10

            optimizers = ['rf', 'gb', 'gp']

            fraction = len(optimizers)

            print 'Start to ask for points.'
            batch_size = (target_points_in_time) / fraction * fraction
            points = opt_rf.ask(n_points = batch_size / fraction) + opt_gb.ask(n_points = batch_size / fraction) + opt_gp.ask(n_points = batch_size / fraction)

            for i in range(30):
                point = []
                for element in space:
                    point.append(np.random.uniform(element[0], element[1]))
                points.append(point)
            
            # modify points
            for i in range(len(points)):
                points[i] = add_fixed_params(points[i])

            for i in range(fraction):
                for j in range(batch_size / fraction):
                    index = i * (batch_size / fraction) + j
                    cur.execute('''INSERT INTO points_results (geo_id, params, optimizer, author, resampled, status) VALUES (%s, %s, %s, 'Artem', 37, 'waiting') ''',\
                        (create_id(points[index]), str(points[index]), optimizers[i]))
            db.commit()

            time.sleep(30 * 60)

        except exceptions.KeyboardInterrupt:
            db.close()
            break
    

if __name__ == '__main__':
    main()
