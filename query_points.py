#!/usr/bin/env python3
import json
import pandas as pd
import numpy as np

from disneylandClient import ListJobsRequest, new_client
from disney_optimize import ProcessPoints

stub = new_client()
all_jobs = stub.ListJobs(ListJobsRequest(kind='point', how_many=100000)).jobs
X, y = ProcessPoints(all_jobs, tag='all')
ids = [job.id for job in all_jobs]
metadata = pd.DataFrame.from_dict(
    data=[
        json.loads(
            point.metadata)['user'] for point in all_jobs]).drop(
                'params',
    axis=1)
data = pd.DataFrame(
    data=np.concatenate(
        [np.array(X).T, np.array([y]), np.array([ids])]).T,
    columns=list(range(1, 57)) + ['loss', 'job_id'])
df = pd.concat([data, metadata], axis=1).set_index(['job_id']).sort_index()
df.to_csv('points.csv')
print(df)
