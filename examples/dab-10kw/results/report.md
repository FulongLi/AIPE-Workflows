# Simulation-driven dual-active-bridge converter design — engineering review package

Run `wf-dab-10kw-first` · workflow `aipe.workflow.converter-dab` · status **completed** · created 2026-10-21T05:15:09Z · specification hash `d38c34a8afa2a50c`

## 1. Requirements and specification

| Quantity | Value |
| --- | --- |
| input_voltage_V | 800 |
| nominal_power_W | 10000 |
| output_voltage_V | 400 |
| power_flow | bidirectional |
| switching_frequency_Hz | 100000 |

### Constraints, ranges and assumptions (with basis)

| Id | Description | Basis |
| --- | --- | --- |
| input-voltage-range | Operating input DC voltage 700 V to 800 V (nominal 800 V); 800 V also the design point for device stress. | source: TIDUES0 Table 1-1 (700-800 V); adopted as AIPE preliminary range |
| output-voltage-range | Operating output DC voltage 350 V to 450 V around the 400 V nominal; wider range requires EPS/DPS modulation study. | assumption (AIPE preliminary range; TI covers 250-500 V with EPS) |
| rated-power-envelope | 10 kW continuous at nominal voltages in both power-flow directions; derated power at the range corners to be established by simulation. | assumption |
| efficiency-target | Full-load efficiency target >= 97.5 % and peak >= 98.5 % at nominal voltages. | assumption informed by source: TIDUES0 Table 1-1 (98.0 % full load, 98.8 % peak measured by TI) |
| device-voltage-derating | Semiconductor DC-bus voltage utilisation <= 70 % of VDS rating at the maximum bus voltage (1200 V class on the 800 V bus, >= 650 V class on the 400 V bus with overshoot margin). | assumption (common industrial derating practice; not a standard citation) |
| junction-temperature-limit | Design maximum junction temperature 125 degC at 40 degC ambient and rated power; absolute maximum per datasheet (150-175 degC) never reached under fault-free operation. | assumption |
| isolation | Transformer and all primary-to-secondary barriers rated for reinforced isolation of an 800 V DC system; transformer dielectric test >= 5 kV DC as in the reference design; creepage/clearance per IEC 60664-1 to be verified in the PCB stage. | assumption; source: TIDUES0 BOM (Payton transformer 5000 VDC) |
| magnetic-saturation-margin | Peak flux density <= 70 % of the core material's saturation flux density at 100 degC under worst-case volt-seconds. | assumption |
| switching-frequency | Fixed 100 kHz switching frequency for the SPS baseline. | task specification; source: TIDUES0 Table 1-1 |
| zvs-at-rated-load | All eight switches must satisfy the ZVS current condition at the nominal operating point; light-load ZVS loss is reported, not required for the SPS baseline. | assumption |

## 2. Environment

Platform: Windows 10 (AMD64); Python 3.10.11

| Tool | Found | Version | Qualified | Path |
| --- | --- | --- | --- | --- |
| elmer | True | 9.0 | not tested | `D:\Cursor Workspace\AIPE-Full-Ecosystem-Integration\tools\ElmerFEM-nogui-nompi-Windows-AMD64\bin\ElmerSolver.exe` |
| freecad | True | 1.1.4 | not tested | `C:\Users\Zhongnan Qian\AppData\Local\Programs\FreeCAD 1.1\bin\freecadcmd.exe` |
| git | True | 2.53.0.windows.2 | not tested | `C:\Program Files\Git\mingw64\bin\git.EXE` |
| gmsh | True | 4.15.2 | not tested | `C:\Users\Zhongnan Qian\AppData\Local\Programs\Python\Python310\lib\site-packages\gmsh.py` |
| kicad-cli | True | 10.0.6 | not tested | `C:\Users\Zhongnan Qian\AppData\Local\Programs\KiCad\10.0\bin\kicad-cli.exe` |
| ltspice | False |  | not tested | `` |
| ngspice | True | 47 | not tested | `D:\Cursor Workspace\AIPE-Full-Ecosystem-Integration\tools\Spice64\bin\ngspice_con.exe` |
| node | True | 24.14.0 | not tested | `C:\Program Files\nodejs\node.EXE` |
| openfoam | False |  | not tested | `` |
| python | True | 3.10.11 | not tested | `C:\Users\Zhongnan Qian\AppData\Local\Programs\Python\Python310\python.exe` |
| xyce | False |  | not tested | `` |

## 3. Task execution

| Task | Gate | Status | Tool | Message |
| --- | --- | --- | --- | --- |
| analytic-sps | analytical | **reused** | aipe.design-agent.dab-sps 0.1.0 |  |
| cad-heatsink |  | **reused** | tool.freecad 1.1.4 |  |
| cad-transformer |  | **completed** | tool.freecad 1.1.4 |  |
| circuit-sim-level1 | circuit_simulation | **reused** | tool.ngspice 47 |  |
| circuit-sim-level1-convergence | circuit_simulation | **reused** | tool.ngspice 47 |  |
| circuit-sim-level2 | circuit_simulation | **reused** | tool.ngspice 47 |  |
| control-baseline |  | **reused** | aipe.simulation-skills.control 0.2.0 |  |
| fem-heatsink |  | **reused** | tool.elmer 9.0 |  |
| fem-transformer-window |  | **reused** | tool.elmer 9.0 |  |
| magnetics-transformer-design |  | **reused** | aipe.magnetics-database.waveform-informed-design 0.2.0 |  |
| requirements | software | **reused** | aipe.core.validate 0.1.0 |  |
| semiconductor-screening |  | **reused** | aipe.semiconductor-database.dab-screening 3.1.0 |  |
| thermal-cooling-design |  | **reused** | aipe.design-agent.thermal 1.0.0 |  |

### analytic-sps

| Output | Value |
| --- | --- |
| evidence_id | evidence.analytic-sps-a25b59 |
| i_L_at_centre_origin_A | 14.2857 |
| i_L_peak_A | 14.2857 |
| i_L_rms_A | 13.6775 |
| i_dc1_A | 12.5 |
| i_dc2_A | 25 |
| l_total_H | 3.5e-05 |
| n_ratio | 2 |
| phi_deg | 22.5 |
| phi_rad | 0.392699 |
| power_W | 10000 |

Verification metrics:

- power_deviation_from_request_W: 0
- power_equals_waveform_integral: True

Model: `sps-lossless-ideal-transformer` v0.1.0 — validity: |phi| <= pi/2, stiff DC ports, L_m >> L; magnetising current and losses not modelled

### cad-heatsink

| Output | Value |
| --- | --- |
| body_count | 19 |
| bridge | secondary |
| candidate_id | A-001 |
| check_status | review |
| device_part_number | C3M0025065K |
| mass_kg | 0.290308 |
| sink_mass_analytical_kg | 0.278254 |
| sink_mass_cad_kg | 0.274753 |
| sink_mass_cad_vs_analytical_relative | -0.0125814 |
| volume_m3 | 0.000106085 |

Verification metrics:

- build_ok: True
- check_status: review
- no_hard_failures: True
- sink_mass_cad_vs_analytical_relative: -0.01258

Model: `aipe-cad-plate-fin-heatsink` v0.1.0 — validity: illustrative parametric geometry of the Stage A candidate with two TO-247 devices on isolation pads; no DFM or thermal claim

### cad-transformer

| Output | Value |
| --- | --- |
| barrier_m | 0.0002 |
| body_count | 16 |
| check_status | review |
| core | core.tdk-e70-33-32 |
| core_name | E 70/33/32 |
| magnetics_copper_mass_kg | 0.182137 |
| magnetics_mass_kg | 0.696137 |
| margin_m | 0 |
| mass_kg | 0.863696 |
| volume_m3 | 0.000194594 |

Verification metrics:

- build_ok: True
- check_status: review
- clearance_pairs: {'fail': 0, 'no_bodies': 0, 'pass': 2, 'review': 1}
- interference_count: 0
- no_hard_failures: True

Model: `aipe-cad-parametric-transformer` v0.1.0 — validity: illustrative parametric geometry: homogenised concentric windings, plain pin terminals, no DFM, thermal or EM claim; clearance checks use straight/one-bend air paths with caller-supplied required values

### circuit-sim-level1

| Output | Value |
| --- | --- |
| circuit_spec_sha256 | ccc3d1bb0892c00a82933f42afc5079252cbb0cf69e04cdd73edcbb981ee074f |
| dataset | runs\wf-dab-10kw-first\tasks\circuit-sim-level1\ngspice\waveforms.h5 |
| dataset_sha256 | f1d558d08cd7691785ab0131f0743710ad28cbf6c6a8f7cb4f0e6deb549d4873 |
| efficiency | 0.999482 |
| energy_unaccounted_W | -0.659528 |
| flux_linkage_pp_Vs | 0.0040004 |
| i_L_peak_A | 14.3152 |
| i_L_rms_A | 13.6779 |
| i_dc1_A | 12.5025 |
| i_dc2_A | 24.992 |
| i_m_peak_A | 2.00096 |
| i_s_peak_A | 32.6287 |
| i_s_rms_A | 27.9289 |
| level | 1 |
| loss_W | 5.17639 |
| measured_phase_shift_deg | 22.5 |
| p_in_W | 10002 |
| p_out_W | 9996.81 |
| run_dir | runs\wf-dab-10kw-first\tasks\circuit-sim-level1\ngspice |
| summary_path | runs\wf-dab-10kw-first\tasks\circuit-sim-level1\ngspice\summary.json |
| valid | True |

| Switch | I rms (A) | I avg (A) | I turn-off mean |A| (A) | I peak fwd (A) | I peak rev (A) | V_ds max (V) | ZVS current condition | conduction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S1 | 9.669 | 6.248 | 14.256 | 14.310 | -14.258 | 800.0 | True | 0.500 |
| S2 | 9.675 | 6.254 | 14.261 | 14.315 | -14.252 | 800.0 | True | 0.500 |
| S3 | 9.675 | 6.254 | 14.261 | 14.315 | -14.252 | 800.0 | True | 0.500 |
| S4 | 9.669 | 6.248 | 14.256 | 14.310 | -14.258 | 800.0 | True | 0.500 |
| S5 | 19.742 | -12.489 | 32.516 | 32.620 | -32.615 | 400.0 | True | 0.500 |
| S6 | 19.755 | -12.503 | 32.502 | 32.606 | -32.629 | 400.0 | True | 0.500 |
| S7 | 19.755 | -12.503 | 32.502 | 32.606 | -32.629 | 400.0 | True | 0.500 |
| S8 | 19.742 | -12.489 | 32.516 | 32.620 | -32.615 | 400.0 | True | 0.500 |

Comparison with analytical SPS reference (tolerance 1.0%): **pass**

| Quantity | Expected | Simulated | Relative error |
| --- | --- | --- | --- |
| ports.port1.current_avg.value | 12.5 | 12.5025 | 1.99e-04 |
| ports.port2.current_avg.value | 25 | 24.992 | 3.19e-04 |
| ports.port2.power_avg.value | 10000 | 9996.81 | 3.19e-04 |
| series_path.i_L_peak_abs.value | 14.2857 | 14.3152 | 2.06e-03 |
| series_path.i_L_rms.value | 13.6775 | 13.6779 | 2.81e-05 |

Verification metrics:

- comparison_vs_analytic_pass: True
- energy_balance_relative_unaccounted: -6.594e-05
- half_wave_antisymmetry_error_i_L: 0.0003793
- n_solver_warnings: 1
- periodic_steady_state: True
- periodicity_error: 1.753e-06
- volt_second_relative_imbalance: 0.005

Model: `aipe-dab-ngspice-level1` v0.2.0 — validity: ideal switches with resistive on-state, E/F ideal transformer with linear magnetising inductance, stiff or RC ports

### circuit-sim-level1-convergence

| Output | Value |
| --- | --- |
| circuit_spec_sha256 | b674ba5816da314bb3b055852c434556ef51790bd4c33a01e0079e6188927015 |
| dataset | runs\wf-dab-10kw-first\tasks\circuit-sim-level1-convergence\ngspice\waveforms.h5 |
| dataset_sha256 | f53fecd72c9883877131445eb887ebc3f94d9ce6227324dd667eea4d60443a1e |
| efficiency | 0.999483 |
| energy_unaccounted_W | -0.663222 |
| flux_linkage_pp_Vs | 0.0040004 |
| i_L_peak_A | 14.3154 |
| i_L_rms_A | 13.6771 |
| i_dc1_A | 12.5026 |
| i_dc2_A | 24.9923 |
| i_m_peak_A | 2.00097 |
| i_s_peak_A | 32.6291 |
| i_s_rms_A | 27.9272 |
| level | 1 |
| loss_W | 5.17203 |
| measured_phase_shift_deg | 22.5 |
| p_in_W | 10002.1 |
| p_out_W | 9996.92 |
| run_dir | runs\wf-dab-10kw-first\tasks\circuit-sim-level1-convergence\ngspice |
| summary_path | runs\wf-dab-10kw-first\tasks\circuit-sim-level1-convergence\ngspice\summary.json |
| valid | True |

| Switch | I rms (A) | I avg (A) | I turn-off mean |A| (A) | I peak fwd (A) | I peak rev (A) | V_ds max (V) | ZVS current condition | conduction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S1 | 9.669 | 6.249 | 14.256 | 14.310 | -14.258 | 800.0 | True | 0.499 |
| S2 | 9.674 | 6.254 | 14.262 | 14.315 | -14.252 | 800.0 | True | 0.499 |
| S3 | 9.674 | 6.254 | 14.262 | 14.315 | -14.252 | 800.0 | True | 0.499 |
| S4 | 9.669 | 6.249 | 14.256 | 14.310 | -14.258 | 800.0 | True | 0.499 |
| S5 | 19.741 | -12.490 | 32.517 | 32.621 | -32.614 | 400.0 | True | 0.499 |
| S6 | 19.754 | -12.502 | 32.502 | 32.606 | -32.629 | 400.0 | True | 0.499 |
| S7 | 19.754 | -12.502 | 32.502 | 32.606 | -32.629 | 400.0 | True | 0.499 |
| S8 | 19.741 | -12.490 | 32.517 | 32.621 | -32.614 | 400.0 | True | 0.499 |

Comparison with analytical SPS reference (tolerance 1.0%): **pass**

| Quantity | Expected | Simulated | Relative error |
| --- | --- | --- | --- |
| ports.port1.current_avg.value | 12.5 | 12.5026 | 2.09e-04 |
| ports.port2.current_avg.value | 25 | 24.9923 | 3.08e-04 |
| ports.port2.power_avg.value | 10000 | 9996.92 | 3.08e-04 |
| series_path.i_L_peak_abs.value | 14.2857 | 14.3154 | 2.08e-03 |
| series_path.i_L_rms.value | 13.6775 | 13.6771 | 3.16e-05 |

Verification metrics:

- comparison_vs_analytic_pass: True
- energy_balance_relative_unaccounted: -6.631e-05
- half_wave_antisymmetry_error_i_L: 0.0004084
- n_solver_warnings: 1
- periodic_steady_state: True
- periodicity_error: 1.879e-06
- volt_second_relative_imbalance: 0.00125

Model: `aipe-dab-ngspice-level1` v0.2.0 — validity: ideal switches with resistive on-state, E/F ideal transformer with linear magnetising inductance, stiff or RC ports

### circuit-sim-level2

| Output | Value |
| --- | --- |
| circuit_spec_sha256 | 57052e6938b4a5d09ee66e9a3645903914e0fd9da458edde3cee7c8b874fc49e |
| dataset | runs\wf-dab-10kw-first\tasks\circuit-sim-level2\ngspice\waveforms.h5 |
| dataset_sha256 | 322284cb3d6b7de79238ac02182e9c7540f1bf01c4eea2f4ddedc0cdf3c072cc |
| efficiency | 0.991091 |
| energy_unaccounted_W | 4.54552 |
| flux_linkage_pp_Vs | 0.00395157 |
| i_L_peak_A | 14.3438 |
| i_L_rms_A | 13.2997 |
| i_dc1_A | 12.1269 |
| i_dc2_A | 24.5048 |
| i_m_peak_A | 2.02675 |
| i_s_peak_A | 31.2139 |
| i_s_rms_A | 27.1086 |
| level | 2 |
| loss_W | 131.658 |
| measured_phase_shift_deg | 22.2084 |
| p_in_W | 9694.2 |
| p_out_W | 9607.83 |
| run_dir | runs\wf-dab-10kw-first\tasks\circuit-sim-level2\ngspice |
| summary_path | runs\wf-dab-10kw-first\tasks\circuit-sim-level2\ngspice\summary.json |
| valid | True |

| Switch | I rms (A) | I avg (A) | I turn-off mean |A| (A) | I peak fwd (A) | I peak rev (A) | V_ds max (V) | ZVS current condition | conduction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S1 | 9.373 | 6.047 | 14.154 | 14.283 | -14.909 | 809.3 | True | 0.500 |
| S2 | 9.413 | 6.079 | 14.214 | 14.343 | -14.703 | 810.1 | True | 0.500 |
| S3 | 9.413 | 6.079 | 14.214 | 14.343 | -14.703 | 810.1 | True | 0.500 |
| S4 | 9.373 | 6.047 | 14.154 | 14.283 | -14.909 | 809.3 | True | 0.500 |
| S5 | 19.188 | -12.215 | 30.508 | 30.644 | -33.791 | 412.3 | True | 0.501 |
| S6 | 19.137 | -12.177 | 30.593 | 30.730 | -33.704 | 412.3 | True | 0.501 |
| S7 | 19.137 | -12.177 | 30.593 | 30.730 | -33.704 | 412.3 | True | 0.501 |
| S8 | 19.188 | -12.215 | 30.508 | 30.644 | -33.791 | 412.3 | True | 0.501 |

Comparison with analytical SPS reference (tolerance 10.0%): **pass**

| Quantity | Expected | Simulated | Relative error |
| --- | --- | --- | --- |
| ports.port1.current_avg.value | 12.5 | 12.1269 | 2.98e-02 |
| ports.port2.current_avg.value | 25 | 24.5048 | 1.98e-02 |
| ports.port2.power_avg.value | 10000 | 9607.83 | 3.92e-02 |
| series_path.i_L_peak_abs.value | 14.2857 | 14.3438 | 4.07e-03 |
| series_path.i_L_rms.value | 13.6775 | 13.2997 | 2.76e-02 |

Verification metrics:

- comparison_vs_analytic_pass: True
- energy_balance_relative_unaccounted: 0.0004689
- half_wave_antisymmetry_error_i_L: 0.004383
- n_solver_warnings: 1
- periodic_steady_state: True
- periodicity_error: 0.0001726
- volt_second_relative_imbalance: 0.004939

Model: `aipe-dab-ngspice-level2` v0.2.0 — validity: behavioural switches, dead time, linear Coss, DC-link ESR/ESL; no manufacturer device physics

### control-baseline

| Output | Value |
| --- | --- |
| current_loop_crossover_Hz | 2000 |
| current_loop_gain_margin_dB | 9.98221 |
| current_loop_phase_margin_deg | 93.6483 |
| design_sha256 | 93b5629562950a14f6772664b0dec300642b76a5a22c589a881cf10131d83321 |
| plant_verification_all_valid | True |
| plant_verification_max_abs_rel_err_p2 | 0.000683626 |
| summary_path | runs\wf-dab-10kw-first\tasks\control-baseline\control\summary.json |
| voltage_loop_crossover_Hz | 300 |
| voltage_loop_gain_margin_dB | 28.3876 |
| voltage_loop_phase_margin_deg | 60 |
| worst_phase_margin_deg | 55.3609 |

Verification metrics:

- design_valid: True
- min_phase_margin_deg: 40
- phase_margins_ok: True
- plant_verification_max_abs_rel_err_p2: 0.0006836
- plant_verification_ok: True
- plant_verification_rows: 3
- scenarios_as_expected: True

Model: `dab-sps-cycle-averaged-plant-with-discrete-controllers` v0.2.0 — validity: cycle-averaged lossless plant with one computation and one measurement sample of delay; no switching dynamics, sensor, ADC or firmware model

### fem-heatsink

| Output | Value |
| --- | --- |
| Q_convective_W | 34.8925 |
| R_th_analytical_candidate_K_per_W | 0.51813 |
| R_th_fem_vs_analytical_relative | 0.0855028 |
| R_th_footprint_mean_K_per_W | 0.543593 |
| R_th_hotspot_K_per_W | 0.562432 |
| T_ambient_K | 313.15 |
| T_max_K | 332.775 |
| T_rise_hotspot_K | 19.6246 |
| candidate_id | A-001 |
| convective_area_m2 | 0.0726742 |
| device_power_W | 17.4462 |
| geometry_note | Stage A knee candidate A-001 (Al-6063-T5, forced cooling); two TO-247 footprints at the model's fixed positions; film coefficient is the Stage A correlation value, not a CFD result |
| geometry_source | Stage A knee candidate A-001 (Al-6063-T5, forced cooling) |
| h_W_per_m2_K | 31.1347 |
| summary_path | runs\wf-dab-10kw-first\tasks\fem-heatsink\fem\summary.json |

Verification metrics:

- R_th_fem_vs_analytical_relative: 0.0855
- checks_passed: True
- convergence: [{'elements': 37805, 'h_m': 0.003, 'level': 0, 'nodes': 12454, 'value': 332.7092423142}, {'elements': 84666, 'h_m': 0.002, 'level': 1, 'nodes': 26820, 'value': 332.774631855}]
- energy_balance_ok: True
- status: executed

Model: `fieldsim-heatsink-3d-conduction` v0.1.0 — validity: 3-D steady conduction in a plate-fin sink with a uniform convective film coefficient supplied as input (from the Stage A correlation); no CFD, no TIM, no package spreading; two footprints only

### fem-transformer-window

| Output | Value |
| --- | --- |
| F_R_litz_proximity_estimate | 1.29026 |
| I1_A | 14.3152 |
| L_leakage_primary_H_1d_estimate | 1.55058e-06 |
| L_leakage_primary_H_fem | 1.48312e-06 |
| L_leakage_primary_H_magnetics_design | 1.55058e-06 |
| L_magnetising_primary_H_fem | 0.00518033 |
| L_magnetising_primary_H_reluctance_estimate | 0.00417668 |
| geometry_note | core window from catalogue record core.tdk-e70-33-32 (E 70/33/32): centre leg 22.0 mm, window 13.0 x 43.8 mm, depth 32.0 mm; homogenised rectangular winding blocks (no individual turns); 2-D planar approximation of the E-core window |
| geometry_source | core window from catalogue record core.tdk-e70-33-32 (E 70/33/32): centre leg 22.0 mm, window 13.0 x 43.8 mm, depth 32.0 mm |
| interleaved | True |
| leakage_fem_vs_1d_relative | -0.0435076 |
| leakage_fem_vs_magnetics_relative | -0.0435076 |
| max_B_window_T | 0.00446701 |
| summary_path | runs\wf-dab-10kw-first\tasks\fem-transformer-window\fem\summary.json |

Verification metrics:

- checks_passed: True
- finest_level_relative_change: None
- leakage_fem_vs_magnetics_relative: -0.04351
- mesh_levels: 2
- status: executed

Model: `fieldsim-transformer-window-2d` v0.1.0 — validity: 2-D planar window magnetostatics with homogenised winding blocks on the selected core's window and the magnetics parametric layout (package default window when the record is unavailable); no 3-D end effects, no core loss; proximity factor is a strand-level estimate

### magnetics-transformer-design

| Output | Value |
| --- | --- |
| copper_loss_W | 15.9079 |
| core_loss_W | 19.1377 |
| external_inductance_required_H | 3.34494e-05 |
| flux_density_peak_T | 0.146428 |
| hot_spot_temperature_rise_K | 63.0839 |
| leakage_inductance_H | 1.55058e-06 |
| magnetising_inductance_H | 0.00391342 |
| measurement_requests_count | 10 |
| result_path | runs\wf-dab-10kw-first\tasks\magnetics-transformer-design\magnetics-design-result.json |
| selected_core | core.tdk-e70-33-32 |
| total_loss_W | 35.0457 |
| turns_primary | 20 |
| turns_ratio_actual | 2 |
| turns_secondary | 10 |

Verification metrics:

- core_state_export_valid: True
- evaluated_candidates: 35
- external_inductance_consistent: True
- feasible_candidates: 12

Model: `aipe-magnetics-waveform-informed-transformer` v0.2.0 — validity: analytical: exact harmonics, per-layer Dowell, iGSE on the actual flux, 1-D leakage, lumped/network thermal; no FEA, no insulation design

### requirements

| Output | Value |
| --- | --- |
| operating_point_id | operating-point.nominal |
| state_id | aipe.workflow.dab-10kw-benchmark |

Verification metrics:

- core_schema_validation: {'errors': [], 'passed': True}

### semiconductor-screening

| Output | Value |
| --- | --- |
| dataset_sha256 | 322284cb3d6b7de79238ac02182e9c7540f1bf01c4eea2f4ddedc0cdf3c072cc |
| junction_temperature_K | 398.15 |
| preferred_integration | discrete |
| primary_device_id | wolfspeed_c4ms047120k |
| primary_excluded_count | 8 |
| primary_loss_W | 9.04185 |
| primary_part_number | C4MS047120K |
| primary_rth_jc_K_per_W | 0.634779 |
| primary_tj_max_rating_K | 448.15 |
| primary_worst_case_switch | S3 |
| screening_path | D:\Cursor Workspace\AIPE-Full-Ecosystem-Integration\runs\wf-dab-10kw-first\tasks\semiconductor-screening\screening.json |
| secondary_device_id | wolfspeed_c3m0025065k |
| secondary_excluded_count | 2 |
| secondary_loss_W | 17.4462 |
| secondary_part_number | C3M0025065K |
| secondary_rth_jc_K_per_W | 0.45758 |
| secondary_tj_max_rating_K | 448.15 |
| secondary_worst_case_switch | S8 |
| semiconductor_loss_total_W_at_tj | 105.952 |

Verification metrics:

- loss_evaluation_complete: True
- loss_evaluations: ['primary', 'secondary']
- primary_candidates: 11
- secondary_candidates: 17
- selection_complete: True

Model: `aipe-devices-dab-screening` v3.1.0 — validity: manufacturer PLECS loss tensors (tier A) and datasheet points scaled linearly in V and I (tier B); no Coss/Eoss data, ZVS by current condition only; no measured evidence

### thermal-cooling-design

| Output | Value |
| --- | --- |
| best_option | liquid-cold-plate-Al-100x100-16-minichannels-water-2lpm |
| devices_per_sink | 4 |
| t_ambient_C | 40 |
| tj_max_best_option_C | 63.0403 |
| worst_bridge | secondary |

Verification metrics:

- best_option_within_absolute_limit: True
- best_option_within_design_limit: True
- knee_feasible: True
- stage_a_candidates: 8
- stage_a_feasible: 6

Model: `pea-thermal-cooling-comparison-and-stage-a` v1.0.0 — validity: analytical correlations (Elenbaas/Bar-Cohen natural convection, Teertstra-Yovanovich-Culham channels, Lee spreading, Shah-London/Gnielinski cold plate) with the validity notes recorded per evaluation; no CFD/FEM/measurement

## 4. Figures

![cad-heatsink](figures/cad-heatsink-dab_heatsink.png)

`figures/cad-heatsink-dab_heatsink.png` (sha256 638ccd4051d4a371, task cad-heatsink)

![cad-transformer](figures/cad-transformer-dab_transformer.png)

`figures/cad-transformer-dab_transformer.png` (sha256 a36eb7da6f56feb0, task cad-transformer)

![circuit-sim-level1](figures/circuit-sim-level1-figure-overview.png)

`figures/circuit-sim-level1-figure-overview.png` (sha256 7aed577559386272, task circuit-sim-level1)

![circuit-sim-level1](figures/circuit-sim-level1-figure-switches.png)

`figures/circuit-sim-level1-figure-switches.png` (sha256 c40513926d406a9c, task circuit-sim-level1)

![circuit-sim-level1-convergence](figures/circuit-sim-level1-convergence-figure-overview.png)

`figures/circuit-sim-level1-convergence-figure-overview.png` (sha256 e5bf9f12325cd34c, task circuit-sim-level1-convergence)

![circuit-sim-level1-convergence](figures/circuit-sim-level1-convergence-figure-switches.png)

`figures/circuit-sim-level1-convergence-figure-switches.png` (sha256 34377433f3fb4ead, task circuit-sim-level1-convergence)

![circuit-sim-level2](figures/circuit-sim-level2-figure-overview.png)

`figures/circuit-sim-level2-figure-overview.png` (sha256 dc05c435363313c9, task circuit-sim-level2)

![circuit-sim-level2](figures/circuit-sim-level2-figure-switches.png)

`figures/circuit-sim-level2-figure-switches.png` (sha256 b9d100df363729b6, task circuit-sim-level2)

![control-baseline](figures/control-baseline-closed_loop_fault.png)

`figures/control-baseline-closed_loop_fault.png` (sha256 1e62b4e3cb9fed5d, task control-baseline)

![control-baseline](figures/control-baseline-closed_loop_input_sag.png)

`figures/control-baseline-closed_loop_input_sag.png` (sha256 3232ec408efb6b90, task control-baseline)

![control-baseline](figures/control-baseline-closed_loop_nominal.png)

`figures/control-baseline-closed_loop_nominal.png` (sha256 41cb0c0ec72f9a67, task control-baseline)

![control-baseline](figures/control-baseline-gate_pattern.png)

`figures/control-baseline-gate_pattern.png` (sha256 17d22617554af4c9, task control-baseline)

![fem-heatsink](figures/fem-heatsink-base_bottom_temperature.png)

`figures/fem-heatsink-base_bottom_temperature.png` (sha256 2be8ed8a8cf645dc, task fem-heatsink)

![fem-heatsink](figures/fem-heatsink-base_bottom_temperature.png)

`figures/fem-heatsink-base_bottom_temperature.png` (sha256 f1bcab4734fcdb44, task fem-heatsink)

![fem-transformer-window](figures/fem-transformer-window-convergence_L_leakage.png)

`figures/fem-transformer-window-convergence_L_leakage.png` (sha256 8f0e303f65f166c9, task fem-transformer-window)

![fem-transformer-window](figures/fem-transformer-window-B_leakage.png)

`figures/fem-transformer-window-B_leakage.png` (sha256 a61f69cb7fee61b8, task fem-transformer-window)

![fem-transformer-window](figures/fem-transformer-window-B_leakage.png)

`figures/fem-transformer-window-B_leakage.png` (sha256 16bab315ab1d44a1, task fem-transformer-window)

![fem-transformer-window](figures/fem-transformer-window-B_magnetising.png)

`figures/fem-transformer-window-B_magnetising.png` (sha256 429170597619478d, task fem-transformer-window)

## 5. Verification gates

| Gate | Status | Checks |
| --- | --- | --- |
| analytical | **pass** | analytic-sps:reused, control-baseline:reused, magnetics-transformer-design:reused, semiconductor-screening:reused, thermal-cooling-design:reused  |
| software | **pass** | requirements:reused  |
| circuit_simulation | **pass** | circuit-sim-level1:reused, circuit-sim-level1-convergence:reused, circuit-sim-level2:reused  |
| field_simulation | **pass** | fem-heatsink:reused, fem-transformer-window:reused  |
| cad_pcb | **pass** | cad-heatsink:reused, cad-transformer:completed  |
| engineering_review | **not_run** | — no record: requires human review / laboratory measurement / hardware qualification outside this workflow |
| experimental | **not_run** | — no record: requires human review / laboratory measurement / hardware qualification outside this workflow |
| hardware_qualification | **not_run** | — no record: requires human review / laboratory measurement / hardware qualification outside this workflow |

Passing an earlier gate does not imply a later one has passed. Experimental measurement and hardware qualification are outside this software workflow.

## 7. Engineering State

Final state id `aipe.workflow.dab-10kw-benchmark`, validation status **simulated**, simulation status **completed**, architecture stage **candidate**; 14 evidence records, 13 state versions (all preserved under `state/`).

- Limitation: Initial state: requested ratings and documented assumptions only; no component, loss, simulation or measurement claimed.

## 8. Reproduction

```
aipe-workflows doctor --qualify
aipe-workflows run <specification.yaml> --run-dir <run-dir>
aipe-workflows verify wf-dab-10kw-first
aipe-workflows report wf-dab-10kw-first
```
