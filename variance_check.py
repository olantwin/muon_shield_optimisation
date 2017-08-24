import MySQLdb
import numpy as np

ID = '3bf31f230c11fdd80d428724867f05ef'

def main():
    db = MySQLdb.connect(host='127.0.0.1', user='root', passwd='P@ssw0rd', db='points')
    cur = db.cursor()
    cur.execute('''SELECT params FROM points_results WHERE id = '{}' '''.format(ID))
    params = map(float, cur.fetchall()[0][0][1:-1].split(', '))
    points = []
    for i in range(3):
        random_noise = np.zeros(len(params))
        random_noise[34:] += np.random.uniform(-0.001, 0.001, len(random_noise[34:]))
        points.append(list(np.array(params) + random_noise))

    with open('points.json', 'w') as points_file:
        print 'New points were written.'
        db.commit()
        points_file.write(str(points))
        points_file.close()


if __name__ == '__main__':
    main()
