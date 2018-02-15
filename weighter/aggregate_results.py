import numpy as np
import re
import os
import argparse
from utils import get_xs_path, loss, get_indeces_path


def get_number(filename):
    return re.findall(r'\d+', filename)[0]


def load_previous_cumulative_arrays():
    cum_loss = np.load("/input/cumloss.npy")
    cum_indeces = np.load("/input/cumindeces.npy")
    return cum_loss, cum_indeces


def load_previous_results(tag):
    '''
    This function should load all the previous results from eos and calculate the mean over each muon.
    '''
    prev_results = []
    prev_indeces = []
    files = os.listdir("/output")

    for filename in files:
        if "xs_" + tag in filename:
            number = get_number(filename)
            xs = np.load(get_xs_path(tag, number))
            prev_results.append(loss(np.array(xs)))

            indeces = np.load(get_indeces_path(tag, number))
            prev_indeces.append(indeces)

    return prev_results, prev_indeces


def calculate_cuminfo(muon_loss, muon_indeces, old_cumloss, old_cumindeces):
    '''
    Function accumulates new results.
    '''
    cum_loss = np.zeros(len(old_cumloss))
    cum_indeces = np.zeros(len(old_cumindeces))

    for i in range(len(muon_loss)):
        cum_loss[muon_indeces[i]] += muon_loss[i]
        cum_indeces[muon_indeces[i]] += 1

    return cum_loss, cum_indeces


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--tag',
        default='')
    args = parser.parse_args()

    cum_loss, cum_indeces = load_previous_cumulative_arrays()
    prev_loss, prev_indeces = load_previous_results(args.tag)
    cum_loss, cum_indeces = calculate_cuminfo(prev_loss, prev_indeces, cum_loss, cum_indeces)
    np.save("/output/cumloss.npy", cum_loss)
    np.save("/output/cumindeces.npy", cum_indeces)


if __name__ == "__main__":
    main()
