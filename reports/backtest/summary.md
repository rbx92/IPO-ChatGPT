# Pullback rule backtest

Official NSE/BSE daily closes, 2024-07-08 to 2026-11-09. 212 IPOs with usable history. Returns are close to close, before costs and taxes.

A signal fires on the first close at least X% below the highest close so far, within the day limit after listing. After a signal, the stock must make a new high before it can signal again. Returns are measured from the signal day's close. 250 trading days is about a year.

Past results do not guarantee future returns.


## Stocks your rule watches (QIB>=50x, listing gain>=25%): 139 IPOs

| Strategy | Signals | After 20 days: median / % higher | After 60 days: median / % higher | After 120 days: median / % higher | After 250 days: median / % higher | Further fall in next 60 days (median) |
|---|---|---|---|---|---|---|
| Buy at first-day close (comparison) | 139 | -5.1% / 43% (n=138) | -9.5% / 41% (n=110) | -17.4% / 35% (n=94) | -20.1% / 41% (n=79) | -16.2% |
| YOUR RULE: 15% fall, 100 days, above first-day close, cap 30% | 65 | -6.9% / 35% (n=57) | -11.6% / 35% (n=52) | -17.1% / 31% (n=48) | -19.3% / 36% (n=39) | -17.0% |
| Same, 20% fall | 45 | -8.8% / 38% (n=39) | -11.7% / 30% (n=37) | -21.2% / 25% (n=36) | -33.4% / 29% (n=28) | -17.4% |
| Same, 25% fall | 30 | -6.0% / 26% (n=27) | -4.5% / 42% (n=26) | -16.0% / 20% (n=25) | -35.8% / 20% (n=20) | -17.7% |
| 15% fall, no first-day-close floor | 154 | -6.8% / 35% (n=137) | -11.7% / 30% (n=117) | -21.3% / 25% (n=105) | -25.2% / 34% (n=86) | -17.7% |
| 15% fall, no 30% cap | 65 | -6.9% / 35% (n=57) | -11.6% / 35% (n=52) | -17.1% / 31% (n=48) | -19.3% / 36% (n=39) | -17.0% |
| 15% fall, 60 days only | 48 | -7.5% / 33% (n=43) | -10.6% / 33% (n=39) | -21.1% / 25% (n=36) | -29.9% / 28% (n=29) | -16.7% |

## Stocks your rule watches (QIB>=50x, listing gain>=25%) - SME: 101 IPOs

| Strategy | Signals | After 20 days: median / % higher | After 60 days: median / % higher | After 120 days: median / % higher | After 250 days: median / % higher | Further fall in next 60 days (median) |
|---|---|---|---|---|---|---|
| Buy at first-day close (comparison) | 101 | -5.1% / 46% (n=101) | -9.8% / 41% (n=88) | -19.9% / 35% (n=77) | -23.9% / 38% (n=66) | -17.4% |
| YOUR RULE: 15% fall, 100 days, above first-day close, cap 30% | 52 | -6.2% / 35% (n=48) | -11.0% / 37% (n=46) | -21.1% / 31% (n=42) | -19.3% / 34% (n=35) | -18.0% |
| Same, 20% fall | 37 | -6.1% / 38% (n=34) | -11.7% / 30% (n=33) | -21.9% / 25% (n=32) | -31.2% / 28% (n=25) | -20.4% |
| Same, 25% fall | 26 | -5.9% / 29% (n=24) | -3.2% / 46% (n=24) | -16.0% / 17% (n=23) | -33.3% / 21% (n=19) | -17.7% |
| 15% fall, no first-day-close floor | 117 | -7.6% / 34% (n=108) | -12.0% / 31% (n=100) | -22.8% / 24% (n=90) | -25.8% / 32% (n=75) | -19.8% |
| 15% fall, no 30% cap | 52 | -6.2% / 35% (n=48) | -11.0% / 37% (n=46) | -21.1% / 31% (n=42) | -19.3% / 34% (n=35) | -18.0% |
| 15% fall, 60 days only | 39 | -6.9% / 32% (n=37) | -10.0% / 36% (n=36) | -21.3% / 27% (n=33) | -22.7% / 30% (n=27) | -17.5% |

## Stocks your rule watches (QIB>=50x, listing gain>=25%) - Mainboard: 38 IPOs

| Strategy | Signals | After 20 days: median / % higher | After 60 days: median / % higher | After 120 days: median / % higher | After 250 days: median / % higher | Further fall in next 60 days (median) |
|---|---|---|---|---|---|---|
| Buy at first-day close (comparison) | 38 | -5.0% / 38% (n=37) | -3.5% / 41% (n=22) | -10.0% / 35% (n=17) | +3.5% / 54% (n=13) | -13.4% |
| YOUR RULE: 15% fall, 100 days, above first-day close, cap 30% | 13 | -7.5% / 33% (n=9) | -16.4% / 17% (n=6) | -2.7% / 33% (n=6) | -13.4% / 50% (n=4) | -14.2% |
| Same, 20% fall | 8 | -9.8% / 40% (n=5) | -12.8% / 25% (n=4) | -6.2% / 25% (n=4) | -36.2% / 33% (n=3) | -12.8% |
| Same, 25% fall | 4 | -10.9% / 0% (n=3) | -5.6% / 0% (n=2) | -6.9% / 50% (n=2) | -38.2% / 0% (n=1) | -17.0% |
| 15% fall, no first-day-close floor | 37 | -5.9% / 38% (n=29) | -11.3% / 24% (n=17) | -4.9% / 27% (n=15) | -20.1% / 45% (n=11) | -11.5% |
| 15% fall, no 30% cap | 13 | -7.5% / 33% (n=9) | -16.4% / 17% (n=6) | -2.7% / 33% (n=6) | -13.4% / 50% (n=4) | -14.2% |
| 15% fall, 60 days only | 9 | -8.7% / 33% (n=6) | -15.8% / 0% (n=3) | -4.9% / 0% (n=3) | -42.9% / 0% (n=2) | -14.2% |

## All dashboard IPOs (QIB>=10x, listing gain>=15%): 212 IPOs

| Strategy | Signals | After 20 days: median / % higher | After 60 days: median / % higher | After 120 days: median / % higher | After 250 days: median / % higher | Further fall in next 60 days (median) |
|---|---|---|---|---|---|---|
| Buy at first-day close (comparison) | 212 | -4.3% / 45% (n=211) | -6.5% / 41% (n=170) | -12.0% / 36% (n=148) | -19.8% / 44% (n=119) | -15.7% |
| YOUR RULE: 15% fall, 100 days, above first-day close, cap 30% | 105 | -5.7% / 38% (n=90) | -9.4% / 35% (n=79) | -12.5% / 34% (n=73) | -12.5% / 43% (n=58) | -17.0% |
| Same, 20% fall | 70 | -2.7% / 42% (n=59) | -8.8% / 33% (n=55) | -14.9% / 30% (n=53) | -16.1% / 37% (n=43) | -15.0% |
| Same, 25% fall | 42 | -7.1% / 24% (n=34) | -5.9% / 39% (n=33) | -13.9% / 19% (n=32) | -30.8% / 27% (n=26) | -16.5% |
| 15% fall, no first-day-close floor | 235 | -5.7% / 38% (n=209) | -9.8% / 32% (n=179) | -14.5% / 31% (n=165) | -17.3% / 38% (n=129) | -16.7% |
| 15% fall, no 30% cap | 105 | -5.7% / 38% (n=90) | -9.4% / 35% (n=79) | -12.5% / 34% (n=73) | -12.5% / 43% (n=58) | -17.0% |
| 15% fall, 60 days only | 76 | -5.6% / 38% (n=68) | -9.0% / 34% (n=59) | -12.7% / 30% (n=54) | -17.3% / 37% (n=41) | -16.7% |

## All dashboard IPOs (QIB>=10x, listing gain>=15%) - SME: 156 IPOs

| Strategy | Signals | After 20 days: median / % higher | After 60 days: median / % higher | After 120 days: median / % higher | After 250 days: median / % higher | Further fall in next 60 days (median) |
|---|---|---|---|---|---|---|
| Buy at first-day close (comparison) | 156 | -5.0% / 44% (n=156) | -7.9% / 42% (n=139) | -13.9% / 38% (n=125) | -19.9% / 44% (n=102) | -17.9% |
| YOUR RULE: 15% fall, 100 days, above first-day close, cap 30% | 82 | -5.6% / 37% (n=78) | -9.0% / 37% (n=73) | -13.0% / 34% (n=67) | -12.5% / 43% (n=54) | -19.3% |
| Same, 20% fall | 56 | -2.4% / 43% (n=53) | -8.7% / 33% (n=51) | -16.3% / 31% (n=49) | -15.5% / 38% (n=40) | -18.6% |
| Same, 25% fall | 34 | -6.1% / 26% (n=31) | -5.9% / 42% (n=31) | -13.9% / 17% (n=30) | -28.3% / 28% (n=25) | -17.7% |
| 15% fall, no first-day-close floor | 180 | -5.6% / 37% (n=169) | -9.0% / 34% (n=157) | -14.5% / 32% (n=145) | -17.1% / 38% (n=114) | -18.4% |
| 15% fall, no 30% cap | 82 | -5.6% / 37% (n=78) | -9.0% / 37% (n=73) | -13.0% / 34% (n=67) | -12.5% / 43% (n=54) | -19.3% |
| 15% fall, 60 days only | 62 | -5.6% / 37% (n=60) | -8.6% / 36% (n=56) | -13.0% / 31% (n=51) | -16.8% / 38% (n=39) | -18.7% |

## All dashboard IPOs (QIB>=10x, listing gain>=15%) - Mainboard: 56 IPOs

| Strategy | Signals | After 20 days: median / % higher | After 60 days: median / % higher | After 120 days: median / % higher | After 250 days: median / % higher | Further fall in next 60 days (median) |
|---|---|---|---|---|---|---|
| Buy at first-day close (comparison) | 56 | -0.4% / 49% (n=55) | -4.3% / 39% (n=31) | -11.2% / 30% (n=23) | -11.1% / 41% (n=17) | -9.9% |
| YOUR RULE: 15% fall, 100 days, above first-day close, cap 30% | 23 | -5.8% / 42% (n=12) | -16.4% / 17% (n=6) | -2.7% / 33% (n=6) | -13.4% / 50% (n=4) | -7.9% |
| Same, 20% fall | 14 | -10.3% / 33% (n=6) | -12.8% / 25% (n=4) | -6.2% / 25% (n=4) | -36.2% / 33% (n=3) | -9.1% |
| Same, 25% fall | 8 | -10.9% / 0% (n=3) | -5.6% / 0% (n=2) | -6.9% / 50% (n=2) | -38.2% / 0% (n=1) | -7.8% |
| 15% fall, no first-day-close floor | 55 | -5.8% / 40% (n=40) | -11.9% / 18% (n=22) | -13.9% / 25% (n=20) | -20.1% / 40% (n=15) | -11.5% |
| 15% fall, no 30% cap | 23 | -5.8% / 42% (n=12) | -16.4% / 17% (n=6) | -2.7% / 33% (n=6) | -13.4% / 50% (n=4) | -7.9% |
| 15% fall, 60 days only | 14 | -1.0% / 50% (n=8) | -15.8% / 0% (n=3) | -4.9% / 0% (n=3) | -42.9% / 0% (n=2) | -10.0% |
