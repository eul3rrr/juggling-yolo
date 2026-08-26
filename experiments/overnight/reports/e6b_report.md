# E6b: widened candidate universe (gap<=30), ballistic scoring

## identical_balls_trick_000_018

| gap bucket | rank-1 sources | accepted under calib gate |
|---|---|---|
| <= 2 | 15 | 0 |
| <= 4 | 13 | 5 |
| <= 6 | 10 | 4 |
| <= 10 | 9 | 2 |
| <= 15 | 7 | 5 |
| <= 20 | 6 | 4 |
| <= 30 | 8 | 7 |

labeled-pair rank changes vs shipped universe: worse=19 same=65 better=1
stolen rank-1 examples: [{"pair": [2, 6], "label": "wrong", "old": 1, "new": 2, "thief_gap": 20, "thief_err": 354.6, "own_err": 419.1}, {"pair": [15, 17], "label": "wrong", "old": 1, "new": 2, "thief_gap": 19, "thief_err": 499.3, "own_err": 305.4}, {"pair": [17, 22], "label": "correct", "old": 1, "new": 3, "thief_gap": 19, "thief_err": 108.4, "own_err": 229.0}, {"pair": [20, 22], "label": "wrong", "old": 1, "new": 4, "thief_gap": 18, "thief_err": 96.8, "own_err": 253.7}, {"pair": [21, 22], "label": "correct", "old": 1, "new": 2, "thief_gap": 14, "thief_err": 16.5, "own_err": 97.9}, {"pair": [36, 41], "label": "wrong", "old": 1, "new": 2, "thief_gap": 11, "thief_err": 53.5, "own_err": 253.6}, {"pair": [50, 55], "label": "correct", "old": 1, "new": 2, "thief_gap": 28, "thief_err": 93.7, "own_err": 95.0}, {"pair": [52, 53], "label": "wrong", "old": 1, "new": 3, "thief_gap": 11, "thief_err": 151.5, "own_err": 361.3}, {"pair": [54, 57], "label": "correct", "old": 1, "new": 2, "thief_gap": 19, "thief_err": 112.7, "own_err": 157.5}, {"pair": [72, 74], "label": "wrong", "old": 1, "new": 2, "thief_gap": 21, "thief_err": 173.4, "own_err": 259.1}]

global assignment over wide pool: links=30 conflicts=0 labeled-tp=11 labeled-fp=0 new-beyond-shipped=19

## youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090

| gap bucket | rank-1 sources | accepted under calib gate |
|---|---|---|
| <= 2 | 6 | 0 |
| <= 4 | 5 | 0 |
| <= 6 | 9 | 0 |
| <= 10 | 5 | 1 |
| <= 15 | 5 | 0 |
| <= 20 | 1 | 0 |
| <= 30 | 2 | 2 |

labeled-pair rank changes vs shipped universe: worse=2 same=26 better=0
stolen rank-1 examples: [{"pair": [10, 11], "label": "wrong", "old": 1, "new": 3, "thief_gap": 13, "thief_err": 222.2, "own_err": 256.6}, {"pair": [18, 30], "label": "correct", "old": 1, "new": 2, "thief_gap": 29, "thief_err": 78.4, "own_err": 92.0}]

global assignment over wide pool: links=10 conflicts=0 labeled-tp=1 labeled-fp=0 new-beyond-shipped=9

TOTALS across videos:
  rank1/accepted per bucket: acc_10=3, acc_15=5, acc_2=0, acc_20=4, acc_30=9, acc_4=5, acc_6=4, conflicts=0, links=40, new_links=28, rank1_10=14, rank1_15=12, rank1_2=21, rank1_20=7, rank1_30=10, rank1_4=18, rank1_6=19
