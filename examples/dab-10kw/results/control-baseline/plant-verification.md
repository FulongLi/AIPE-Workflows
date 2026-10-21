| phi (deg) | P plant (W) | P2 ngspice (W) | err P2 (%) | P1 ngspice (W) | err P1 (%) | i_L RMS plant (A) | i_L RMS ngspice (A) | err (%) | phi measured (deg) | status |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 10 | 4797.2 | 4796.0 | -0.025 | 4797.1 | -0.001 | 6.231 | 6.233 | +0.033 | 10.000 | steady_state |
| 22.5 | 10000.0 | 9995.5 | -0.045 | 10001.0 | +0.010 | 13.678 | 13.680 | +0.018 | 22.500 | steady_state |
| 35 | 14321.0 | 14311.2 | -0.068 | 14323.8 | +0.020 | 20.732 | 20.734 | +0.009 | 35.000 | steady_state |

ngspice 47 on Windows 10 AMD64; cycles = 12, t_max = T/200; ngspice Level 1: ideal switches with Ron = 1 mOhm, antiparallel diodes, r_series_p = 20 mOhm, L_m = 1 mH, stiff voltage-source ports; the control plant is lossless.
