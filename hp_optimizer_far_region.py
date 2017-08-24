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

target_points_in_time = 200
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
    if len(X_0) == 0:
        db = MySQLdb.connect(host='127.0.0.1', user='root', passwd='P@ssw0rd', db='points')
        cur = db.cursor()
        cur.execute('''SELECT params FROM points_results WHERE metric_1 IS NOT NULL ORDER BY metric_1''')
        data = map(float, cur.fetchall()[0][0][1:-1].split(', '))
        data = data[2:8] + data[20:]
        space = []
        for element in data:
            quant = element / 4
            space.append((quant, 3 * quant))
    else:
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



def main():
    db = MySQLdb.connect(host='127.0.0.1', user='root', passwd='P@ssw0rd', db='points')
    old_number_of_rows = -1
    running_now = 0
    while True:
        try:            
            cur = db.cursor()
            cur.execute('''SELECT params, metric_1 FROM points_results WHERE metric_1 IS NOT NULL AND tag = 'far_region' ''')
            data = cur.fetchall()
            initial_rows_number = len(data)
        
            X_0 = []
            y_0 = []
            for element in data:
                new_X = map(float, element[0][1:-1].split(', '))
                if is_inspace(new_X):
                    X_0.append(new_X[2:8] + new_X[20:])
                    y_0.append(float(element[1]))

            space = compute_space(X_0)
            #opt_gp = Optimizer(space, GaussianProcessRegressor(normalize_y=True))
            opt_rf = Optimizer(space, RandomForestRegressor(n_estimators = 100, max_depth = 10),  acq_optimizer="sampling")
            #opt_gb = Optimizer(space, GradientBoostingQuantileRegressor(base_estimator = GradientBoostingRegressor(n_estimators = 100, max_depth = 4)), acq_optimizer="sampling")

            print 'Start to tell points.'
            if len(X_0) != 0:
                #opt_gp.tell(X_0, y_0)
                opt_rf.tell(X_0, y_0)
                #opt_gb.tell(X_0, y_0)
            optimizers = ['rf']

            fraction = 1

            print 'Start to ask for points.'
            batch_size = (target_points_in_time - running_now) / fraction * fraction
            points = opt_rf.ask(n_points = batch_size / fraction)
            print "Points are ready!"
            # modify points
            for i in range(len(points)):
                points[i] = add_fixed_params(points[i])

            for i in range(fraction):
                for j in range(batch_size / fraction):
                    index = i * (batch_size / fraction) + j
                    cur.execute('''INSERT INTO points_results (geo_id, params, optimizer, author, resampled, tag) VALUES (%s, %s, %s, 'Artem', 37, 'far_region') ''',\
                        (create_id(points[index]), str(points[index]), optimizers[i]))
                    cur.execute('SELECT LAST_INSERT_ID()')
                    points[index].append(int(cur.fetchall()[0][0]))

            
            with open('points_to_run/our_points.json', 'w') as points_file:
                print 'New points were written.'
                db.commit()
                points_file.write(str(points))
                points_file.close()
            
            cur.close()

            while True:
                cur = db.cursor()
                cur.execute('''SELECT params, metric_1 FROM points_results WHERE metric_1 IS NOT NULL AND tag = 'far_region' ''')
                data = cur.fetchall()
                cur.close()
                db.commit()
                if running_now + batch_size + initial_rows_number - len(data) < target_points_in_time * min_fraction:
                    running_now += batch_size + initial_rows_number - len(data)
                    break


        except exceptions.KeyboardInterrupt:
            db.close()
            break
    

if __name__ == '__main__':
    main()
