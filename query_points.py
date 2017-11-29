import pandas as pd
import numpy as np

import disneylandClient
from disneylandClient import (
    Job,
    RequestWithId,
    ListJobsRequest
)
from disney_optimize import ProcessPoints

stub = disneylandClient.new_client()
all_jobs = stub.ListJobs(ListJobsRequest(kind='point', how_many=1000)).jobs
X, y = ProcessPoints(all_jobs)
pd.DataFrame(np.concatenate(
    [np.array(X).T, np.array([y])]).T).to_csv('points.csv')
