# E6: chain-level global stitching vs greedy

| video | method | g# | gate | links | TP | FP | confl | chains | max | mean | corrConn | wrongConn |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| identical_balls_tr | greedy | 0 | 149 | 29 | 29 | 0 | 1 | 18 | 7 | 2.56 | 29/45 | 0/40 |
| identical_balls_tr | global | 0 | 149 | 28 | 28 | 0 | 0 | 17 | 7 | 2.65 | 28/45 | 0/40 |
| identical_balls_tr | greedy | 1 | 231 | 38 | 36 | 2 | 3 | 19 | 7 | 2.84 | 36/45 | 2/40 |
| identical_balls_tr | global | 1 | 231 | 35 | 34 | 1 | 0 | 18 | 7 | 2.94 | 34/45 | 1/40 |
| identical_balls_tr | greedy | 2 | 261 | 45 | 38 | 7 | 7 | 21 | 6 | 2.81 | 38/45 | 13/40 |
| identical_balls_tr | global | 2 | 261 | 39 | 35 | 4 | 0 | 18 | 7 | 3.17 | 35/45 | 5/40 |
| identical_balls_tr | greedy | 3 | 352 | 48 | 39 | 9 | 9 | 24 | 6 | 2.62 | 40/45 | 15/40 |
| identical_balls_tr | global | 3 | 352 | 39 | 35 | 4 | 0 | 18 | 7 | 3.17 | 35/45 | 5/40 |
| identical_balls_tr | greedy | 4 | 431 | 53 | 42 | 11 | 12 | 27 | 6 | 2.52 | 43/45 | 17/40 |
| identical_balls_tr | global | 4 | 431 | 43 | 39 | 4 | 0 | 21 | 7 | 3.05 | 39/45 | 5/40 |
| identical_balls_tr | greedy | 5 | 526 | 54 | 43 | 11 | 12 | 27 | 6 | 2.56 | 44/45 | 17/40 |
| identical_balls_tr | global | 5 | 526 | 45 | 39 | 6 | 0 | 21 | 6 | 3.14 | 39/45 | 7/40 |
| youtube_juggling_f | greedy | 0 | 101 | 11 | 11 | 0 | 1 | 8 | 3 | 2.25 | 11/26 | 0/2 |
| youtube_juggling_f | global | 0 | 101 | 10 | 10 | 0 | 0 | 8 | 3 | 2.25 | 10/26 | 0/2 |
| youtube_juggling_f | greedy | 1 | 120 | 15 | 15 | 0 | 1 | 9 | 4 | 2.56 | 15/26 | 0/2 |
| youtube_juggling_f | global | 1 | 120 | 14 | 14 | 0 | 0 | 9 | 4 | 2.56 | 14/26 | 0/2 |
| youtube_juggling_f | greedy | 2 | 147 | 18 | 18 | 0 | 1 | 10 | 4 | 2.7 | 18/26 | 0/2 |
| youtube_juggling_f | global | 2 | 147 | 17 | 17 | 0 | 0 | 10 | 4 | 2.7 | 17/26 | 0/2 |
| youtube_juggling_f | greedy | 3 | 177 | 21 | 21 | 0 | 1 | 12 | 4 | 2.67 | 21/26 | 0/2 |
| youtube_juggling_f | global | 3 | 177 | 20 | 20 | 0 | 0 | 12 | 4 | 2.67 | 20/26 | 0/2 |
| youtube_juggling_f | greedy | 4 | 178 | 23 | 23 | 0 | 1 | 12 | 4 | 2.83 | 23/26 | 0/2 |
| youtube_juggling_f | global | 4 | 178 | 22 | 22 | 0 | 0 | 12 | 4 | 2.83 | 22/26 | 0/2 |
| youtube_juggling_f | greedy | 5 | 222 | 25 | 25 | 0 | 2 | 11 | 7 | 3.09 | 25/26 | 0/2 |
| youtube_juggling_f | global | 5 | 222 | 23 | 23 | 0 | 0 | 11 | 4 | 3.09 | 23/26 | 0/2 |
