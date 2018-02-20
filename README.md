## Examples:

[`disney_oneshot.py`](disney_oneshot.py) is a convenient script to calculate
single points:

```bash
$ ./disney_oneshot.py --help usage: disney_oneshot.py [-h] [-p POINT] [--seed
SEED] [--sampling SAMPLING]

Start optimizer.

optional arguments:
  -h, --help            show this help message and exit
  -p POINT, --point POINT
  --seed SEED           Random seed of simulation
  --sampling SAMPLING   Muon sample to use
```

Note that `sampling` defaults to 37 (i.e. resampled) and `seed` defaults to 1.

If point is not specified it calculates a random point within the search space.

Currently the script outputs a summary of loss, weight and saves the point and
meta-data to the database for further analysis.

### To run the new baseline shield configuration on the full muon sample

```bash
$ ./disney_oneshot.py -p "[70.0, 170.0, 208.0, 207.0, 281.0, 248.0, 305.0,
242.0, 40.0, 40.0, 150.0, 150.0, 2.0, 2.0, 80.0, 80.0, 150.0, 150.0, 2.0, 2.0,
72.0, 51.0, 29.0, 46.0, 10.0, 7.0, 54.0, 38.0, 46.0, 192.0, 14.0, 9.0, 10.0,
31.0, 35.0, 31.0, 51.0, 11.0, 3.0, 32.0, 54.0, 24.0, 8.0, 8.0, 22.0, 32.0,
209.0, 35.0, 8.0, 13.0, 33.0, 77.0, 85.0, 241.0, 9.0, 26.0]" --seed 2
--sampling 1
```

### To run the new baseline shield configuration on the re-weighted muon sample

```bash
$ ./disney_oneshot.py -p "[70.0, 170.0, 208.0, 207.0, 281.0, 248.0, 305.0, 242.0,
40.0, 40.0, 150.0, 150.0, 2.0, 2.0, 80.0, 80.0, 150.0, 150.0, 2.0, 2.0, 72.0,
51.0, 29.0, 46.0, 10.0, 7.0, 54.0, 38.0, 46.0, 192.0, 14.0, 9.0, 10.0, 31.0,
35.0, 31.0, 51.0, 11.0, 3.0, 32.0, 54.0, 24.0, 8.0, 8.0, 22.0, 32.0, 209.0,
35.0, 8.0, 13.0, 33.0, 77.0, 85.0, 241.0, 9.0, 26.0]" --seed 2 --sampling 37
```

### To run on a custom shield configuration

```bash
./disney_oneshot.py -p "<params in format [a,b,...z]>" --sampling 1 --seed 3 
```
