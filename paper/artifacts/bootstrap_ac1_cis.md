# Bootstrap 95% Confidence Intervals on AC@1

Percentile bootstrap, n_resamples=10,000, confidence_level=0.95, random_state=42. Each cell aggregates 125 per-case binary AC@1 (hit/miss) values from the existing evaluation harness (`results/week2_<method>_validation[_<system>].csv`).

## (a) Markdown tables

### RE1-OB (Table 1a)

| Method | AC@1 (point) | 95% CI low | 95% CI high |
|--------|-------------:|-----------:|------------:|
| DejaVu | 0.696 | 0.616 | 0.776 |
| MR | 0.632 | 0.544 | 0.712 |
| CR | 0.624 | 0.536 | 0.704 |
| Micro | 0.624 | 0.536 | 0.704 |
| BARO | 0.536 | 0.448 | 0.624 |
| FODA-FCP | 0.400 | 0.320 | 0.488 |
| yRCA | 0.328 | 0.248 | 0.408 |

### RE1-SS (Table 1b)

| Method | AC@1 (point) | 95% CI low | 95% CI high |
|--------|-------------:|-----------:|------------:|
| DejaVu | 0.848 | 0.784 | 0.904 |
| CR | 0.656 | 0.568 | 0.736 |
| MR | 0.656 | 0.576 | 0.736 |
| Micro | 0.648 | 0.560 | 0.728 |
| BARO | 0.584 | 0.496 | 0.672 |
| yRCA | 0.256 | 0.176 | 0.336 |
| FODA-FCP | 0.160 | 0.096 | 0.232 |

### RE1-TT (Table 1c)

| Method | AC@1 (point) | 95% CI low | 95% CI high |
|--------|-------------:|-----------:|------------:|
| DejaVu | 0.744 | 0.664 | 0.816 |
| MR | 0.480 | 0.392 | 0.568 |
| CR | 0.472 | 0.384 | 0.560 |
| Micro | 0.456 | 0.368 | 0.544 |
| BARO | 0.392 | 0.304 | 0.480 |
| yRCA | 0.104 | 0.056 | 0.160 |
| FODA-FCP | 0.008 | 0.000 | 0.024 |

## (b) LaTeX-ready fragments (Tables 1a-c)

Each AC@1 cell is rendered as `point [low, high]`. Drop-in replacement for the current AC@1 column.

% Table 1a -- RE1-OB
\begin{tabular}{lc}
\toprule
Method & AC@1 (95\% CI) \\
\midrule
DejaVu & 0.696 [0.616, 0.776] \\
MR & 0.632 [0.544, 0.712] \\
CR & 0.624 [0.536, 0.704] \\
Micro & 0.624 [0.536, 0.704] \\
BARO & 0.536 [0.448, 0.624] \\
FODA-FCP & 0.400 [0.320, 0.488] \\
yRCA & 0.328 [0.248, 0.408] \\
\bottomrule
\end{tabular}

% Table 1b -- RE1-SS
\begin{tabular}{lc}
\toprule
Method & AC@1 (95\% CI) \\
\midrule
DejaVu & 0.848 [0.784, 0.904] \\
CR & 0.656 [0.568, 0.736] \\
MR & 0.656 [0.576, 0.736] \\
Micro & 0.648 [0.560, 0.728] \\
BARO & 0.584 [0.496, 0.672] \\
yRCA & 0.256 [0.176, 0.336] \\
FODA-FCP & 0.160 [0.096, 0.232] \\
\bottomrule
\end{tabular}

% Table 1c -- RE1-TT
\begin{tabular}{lc}
\toprule
Method & AC@1 (95\% CI) \\
\midrule
DejaVu & 0.744 [0.664, 0.816] \\
MR & 0.480 [0.392, 0.568] \\
CR & 0.472 [0.384, 0.560] \\
Micro & 0.456 [0.368, 0.544] \\
BARO & 0.392 [0.304, 0.480] \\
yRCA & 0.104 [0.056, 0.160] \\
FODA-FCP & 0.008 [0.000, 0.024] \\
\bottomrule
\end{tabular}

## Non-overlapping CI pairs (distinguishable at 95%)

- [RE1-OB] DejaVu (0.696 [0.616, 0.776]) > FODA-FCP (0.400 [0.320, 0.488]) - CIs do not overlap
- [RE1-OB] DejaVu (0.696 [0.616, 0.776]) > yRCA (0.328 [0.248, 0.408]) - CIs do not overlap
- [RE1-OB] MR (0.632 [0.544, 0.712]) > FODA-FCP (0.400 [0.320, 0.488]) - CIs do not overlap
- [RE1-OB] MR (0.632 [0.544, 0.712]) > yRCA (0.328 [0.248, 0.408]) - CIs do not overlap
- [RE1-OB] CR (0.624 [0.536, 0.704]) > FODA-FCP (0.400 [0.320, 0.488]) - CIs do not overlap
- [RE1-OB] CR (0.624 [0.536, 0.704]) > yRCA (0.328 [0.248, 0.408]) - CIs do not overlap
- [RE1-OB] Micro (0.624 [0.536, 0.704]) > FODA-FCP (0.400 [0.320, 0.488]) - CIs do not overlap
- [RE1-OB] Micro (0.624 [0.536, 0.704]) > yRCA (0.328 [0.248, 0.408]) - CIs do not overlap
- [RE1-OB] BARO (0.536 [0.448, 0.624]) > yRCA (0.328 [0.248, 0.408]) - CIs do not overlap
- [RE1-SS] DejaVu (0.848 [0.784, 0.904]) > CR (0.656 [0.568, 0.736]) - CIs do not overlap
- [RE1-SS] DejaVu (0.848 [0.784, 0.904]) > MR (0.656 [0.576, 0.736]) - CIs do not overlap
- [RE1-SS] DejaVu (0.848 [0.784, 0.904]) > Micro (0.648 [0.560, 0.728]) - CIs do not overlap
- [RE1-SS] DejaVu (0.848 [0.784, 0.904]) > BARO (0.584 [0.496, 0.672]) - CIs do not overlap
- [RE1-SS] DejaVu (0.848 [0.784, 0.904]) > yRCA (0.256 [0.176, 0.336]) - CIs do not overlap
- [RE1-SS] DejaVu (0.848 [0.784, 0.904]) > FODA-FCP (0.160 [0.096, 0.232]) - CIs do not overlap
- [RE1-SS] CR (0.656 [0.568, 0.736]) > yRCA (0.256 [0.176, 0.336]) - CIs do not overlap
- [RE1-SS] CR (0.656 [0.568, 0.736]) > FODA-FCP (0.160 [0.096, 0.232]) - CIs do not overlap
- [RE1-SS] MR (0.656 [0.576, 0.736]) > yRCA (0.256 [0.176, 0.336]) - CIs do not overlap
- [RE1-SS] MR (0.656 [0.576, 0.736]) > FODA-FCP (0.160 [0.096, 0.232]) - CIs do not overlap
- [RE1-SS] Micro (0.648 [0.560, 0.728]) > yRCA (0.256 [0.176, 0.336]) - CIs do not overlap
- [RE1-SS] Micro (0.648 [0.560, 0.728]) > FODA-FCP (0.160 [0.096, 0.232]) - CIs do not overlap
- [RE1-SS] BARO (0.584 [0.496, 0.672]) > yRCA (0.256 [0.176, 0.336]) - CIs do not overlap
- [RE1-SS] BARO (0.584 [0.496, 0.672]) > FODA-FCP (0.160 [0.096, 0.232]) - CIs do not overlap
- [RE1-TT] DejaVu (0.744 [0.664, 0.816]) > MR (0.480 [0.392, 0.568]) - CIs do not overlap
- [RE1-TT] DejaVu (0.744 [0.664, 0.816]) > CR (0.472 [0.384, 0.560]) - CIs do not overlap
- [RE1-TT] DejaVu (0.744 [0.664, 0.816]) > Micro (0.456 [0.368, 0.544]) - CIs do not overlap
- [RE1-TT] DejaVu (0.744 [0.664, 0.816]) > BARO (0.392 [0.304, 0.480]) - CIs do not overlap
- [RE1-TT] DejaVu (0.744 [0.664, 0.816]) > yRCA (0.104 [0.056, 0.160]) - CIs do not overlap
- [RE1-TT] DejaVu (0.744 [0.664, 0.816]) > FODA-FCP (0.008 [0.000, 0.024]) - CIs do not overlap
- [RE1-TT] MR (0.480 [0.392, 0.568]) > yRCA (0.104 [0.056, 0.160]) - CIs do not overlap
- [RE1-TT] MR (0.480 [0.392, 0.568]) > FODA-FCP (0.008 [0.000, 0.024]) - CIs do not overlap
- [RE1-TT] CR (0.472 [0.384, 0.560]) > yRCA (0.104 [0.056, 0.160]) - CIs do not overlap
- [RE1-TT] CR (0.472 [0.384, 0.560]) > FODA-FCP (0.008 [0.000, 0.024]) - CIs do not overlap
- [RE1-TT] Micro (0.456 [0.368, 0.544]) > yRCA (0.104 [0.056, 0.160]) - CIs do not overlap
- [RE1-TT] Micro (0.456 [0.368, 0.544]) > FODA-FCP (0.008 [0.000, 0.024]) - CIs do not overlap
- [RE1-TT] BARO (0.392 [0.304, 0.480]) > yRCA (0.104 [0.056, 0.160]) - CIs do not overlap
- [RE1-TT] BARO (0.392 [0.304, 0.480]) > FODA-FCP (0.008 [0.000, 0.024]) - CIs do not overlap
- [RE1-TT] yRCA (0.104 [0.056, 0.160]) > FODA-FCP (0.008 [0.000, 0.024]) - CIs do not overlap

