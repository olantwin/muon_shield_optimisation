#!/bin/env python2
import json
import click
from common import in_bounds


@click.command()
@click.argument('inputfile', type=click.File('r'))
@click.argument('outputfile', type=click.File('w'))
def validate_points(inputfile, outputfile):
    points = json.load(inputfile)
    good_points = []
    indices = []
    for index, point in enumerate(points):
        assert len(point) == 56
        try:
            in_bounds(point[2:])
        except AssertionError:
            print index
            indices.append(index)
            continue
        good_points.append(point)
    print len(indices)
    assert len(indices) + len(good_points) == len(points)
    json.dump(good_points, outputfile)


if __name__ == '__main__':
    validate_points()
