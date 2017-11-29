#!/bin/env python3
import pandas as pd
import numpy as np

from disneylandClient import (
    ListJobsRequest,
    new_client
)
from disney_optimize import ProcessPoints

stub = new_client()
all_jobs = stub.ListJobs(ListJobsRequest(kind='point', how_many=1000)).jobs
X, y = ProcessPoints(all_jobs)
df = pd.DataFrame(np.concatenate(
    [np.array(X).T, np.array([y])]).T)
df.to_csv('points.csv')
print(df)
