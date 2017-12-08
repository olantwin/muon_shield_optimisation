#!/usr/bin/env python2
import click
from disney_common import ParseParams
from common import generate_geo


@click.command()
@click.argument('geofile')
@click.argument('unparsed_params')
def make_vector(geofile, unparsed_params):
    params = ParseParams(unparsed_params)
    print geofile, params
    generate_geo(geofile, params)


if __name__ == '__main__':
    make_vector()
