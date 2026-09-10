# 5DR V2 Deterministic Scoring

## Universal raw scale
+2 strong bullish = +1.00 normalized; +1 bullish = +0.50; 0 neutral = 0; -1 bearish = -0.50; -2 strong bearish = -1.00.

## Base directional weights
Price + Volume + Structure 35; PVPO / Derivatives 30; Market Participation 15; Macro + Catalysts 20.

## Regime weights
| Regime | Price | PVPO | Participation | Macro |
|---|---:|---:|---:|---:|
| TREND | 40 | 30 | 15 | 15 |
| RANGE | 30 | 35 | 15 | 20 |
| TRANSITION | 35 | 25 | 15 | 25 |
| EVENT_SHOCK | 30 | 20 | 10 | 40 |

## DES5 interpretation
+60..+100 Strong Bull; +30..+59 Bull; +15..+29 Mild Bull; -14..+14 Range; -29..-15 Mild Bear; -59..-30 Bear; -100..-60 Strong Bear.

## Market Trust weights
Price confirmation 25; PVPO confirmation 25; Participation confirmation 15; Cross-engine consistency 15; Closing confirmation 10; Evidence freshness/completeness 10.

## Provisional probability engine
S = abs(DES5)

Lead = 38 + 0.48*S + 0.08*(MarketTrust - 50)

Base = 55 - 0.45*S - 0.08*(MarketTrust - 50)

Opposite = 100 - Lead - Base; opposite floor 8%; renormalize.

Caps: MT>=80 80%; MT65-79 72%; MT50-64 65%; MT<50 58%; HIGH Event Shock 62%; EXTREME 55% and block directional trade.

## Single tradeability gate
Trade only when data adequate, Market Trust >=50, abs(DES5)>=30, Execution Edge>=65, kill switch inactive, and expected R:R>=2.0.
