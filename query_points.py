#!/usr/bin/env python3
import json
import pandas as pd
import numpy as np

from disneylandClient import ListJobsRequest, new_client
from disney_optimize import ProcessPoints, FilterPoints
from config import IMAGE_TAG

stub = new_client()
all_points = stub.ListJobs(ListJobsRequest(kind='point', how_many=0)).jobs
points = FilterPoints(all_points, seed='all', sampling='all')
X, y = ProcessPoints(points)
ids = [job.id for job in points]
metadata = pd.DataFrame.from_dict(
    data=[json.loads(point.metadata)['user'] for point in points]).drop(
        'params', axis=1)
data = pd.DataFrame(
    data=np.concatenate([np.array(X).T, np.array([y]), np.array([ids])]).T,
    columns=list(range(1, 57)) + ['loss', 'job_id'])
df = pd.concat([data, metadata], axis=1).set_index(['job_id']).sort_index()
df.to_csv(f'points_{IMAGE_TAG}.csv')
print(df)
