# TIDA-010054 (TI 10 kW SiC dual active bridge) — sourced fact sheet

Collected 2026-10-21 from official Texas Instruments documents by the AIPE
research step. Every value carries its source key. This sheet informs the AIPE
10 kW DAB benchmark ranges and component shortlist; it is not an AIPE
measurement and the AIPE benchmark operating point (800 V to 400 V, n = 2)
differs from TI's (800 V to 500 V nominal, n = 1.6).

Source keys:

- **DG** = Design guide TIDUES0 Rev F (June 2019, revised April 2026, 81 pp.),
  https://www.ti.com/lit/pdf/tidues0
- **TP** = Tool page, https://www.ti.com/tool/TIDA-010054
- **BOM** = TIDRZW1B, https://www.ti.com/lit/pdf/tidrzw1 ; **SCH** = TIDRZW0C, https://www.ti.com/lit/pdf/tidrzw0
- **RN** = C2000 DigitalPower SDK release notes 5.02.00.00 / 5.02.01.00,
  https://software-dl.ti.com/C2000/c2000_apps_public_sw/c2000ware_sdk/digitalpowersdk/5_02_00_00/release_notes.html

## 1. Electrical specification

| Item | Value | Source |
| --- | --- | --- |
| Input DC voltage | 700–800 V, nominal 800 V (12.5 A) | DG Table 1-1 p.4; Table 2-1 p.23–24 |
| Output DC voltage | 250–500 V (350–500 V with SPS, 250–500 V with EPS); nominal 500 V / 20 A; 26 A max | DG p.1, p.4, Table 2-1 |
| Rated power | 10 kW; with EPS 10 kW down to 350 V, 5 kW at 250 V | DG Table 1-1; p.76 |
| Switching frequency | 100 kHz fixed | DG Table 1-1; §2.3.4.6 p.22 |
| Efficiency | peak 98.8 % at 4 kW, 98.0 % at 10 kW (features page says 98.7 % peak); closed voltage loop, 800 V in, resistive load, power analyser | DG Table 1-1 p.4; §4.5 p.76; §4.2 p.45 |
| Turns ratio | N = 1.6 (24:15) | DG p.17, Tables 2-1, 2-2 p.26; BOM T1 |
| Series inductance | 35 µH design; transformer leakage 34 µH with integrated shim inductor; Lm = 720 µH | DG p.18, p.20, Table 2-1/2-2, §2.3.5.3 |
| Theoretical P_max | 22.85 kW; phase shift 23° (0.4 rad) at 10 kW; design range −0.44 < φ < 0.44 rad | DG p.18–20 |
| DC-link capacitance | output 60 µF, input 30 µF low-ESR film (TDK B32716H8306K000 2× 30 µF/800 V; B32716H1156K000 2× 15 µF/1.1 kV) plus 28× 0.47 µF 2220 ceramics; DC-blocking minimum 7.2 µF | DG §2.3.4.5 p.21; BOM; DG Eq. 20 p.22 |
| Modulation | SPS and EPS implemented and selectable; DPS/TPS mentioned as options only | DG p.1, p.19, p.36–37, p.63 |
| Dead time | 200 ns (high-resolution dead band) | DG Eq. 22 p.24; §4.1.2.4 p.41 |
| ZVS | all lagging-bridge switches and some leading-bridge switches, load/voltage-ratio dependent (Eq. 11–12); inductor sized for ZVS to ½–⅓ load; at 800 V/450 V/6.5 A secondary hard-switches with SPS, both soft-switch with EPS | DG p.15, p.18–19, p.23, Fig. 4-34/4-35 |

## 2. Power semiconductors, gate drive, sensing, supplies

- Primary bridge: 4× Wolfspeed C3M0075120K, 1200 V, 75 mΩ, 30 A, TO-247-4 Kelvin [BOM Q8/Q9/Q12/Q13; DG p.23, p.28].
- Secondary bridge: 4× Wolfspeed C3M0030090K, 900 V, 30 mΩ, 63 A, TO-247-4 [BOM Q6/Q7/Q10/Q11; DG p.28].
- Gate drivers: 8× UCC21710QDWQ1 single-channel isolated, ±10 A, DESAT 6.4 V / 1 µs blanking, Miller clamp, soft turn-off, PWM interlock [DG §3.5 p.35; BOM U29–U41].
- Gate resistors 2 Ω on / 2 Ω off; gate voltage +15 V / −4 V [DG p.27, Fig. 3-13 p.35, §3.4.2 p.34; BOM].
- Current sensing: AMC1302-Q1 + 3 mΩ shunt (primary DC); AMC1306M05 + 1.5 mΩ shunt (secondary DC, SDFM); 2× TMCS1133B1 Hall sensors on transformer currents, 1 MHz BW, over-current trips 45 A (primary) / 70 A (secondary) tripping PWM via GPIO [DG §3.3 p.31–32; BOM].
- Voltage sensing: AMC1311B + divider (800 V → 1.57 V) + OPA2320 on the primary; 2× AMC1336 ΔΣ modulators (500 V → 0.76 V) on the secondary into C2000 SDFM [DG §3.2 p.29–30].
- Bias: 8× UCC14141-Q1 isolated gate-driver supplies (+15 V / −4 V); TLV76050 5 V; 12 V input → TPS2640 eFuse → TLVM13620 5 V → 2× TPS7A2033 3.3 V; ISOW1044 CAN (footprint, not implemented) [DG §3.4–3.6 p.32–35]. Secondary relays 2× Omron G9KB-1A [BOM].

## 3. Controller and firmware

- TMS320F280039C on TMDSCNCD280039C controlCARD (HSEC8-160) [DG p.6, §4.1.1 p.39, Table 4-2 p.47; TP]. Rev D (Feb 2024) moved to this MCU; earlier hardware used TMS320F280049 + UCC21530 (380–500 V, 97.6 % full load).
- PWM: ePWM1/2 primary legs, ePWM3/4 secondary (GPIO0–7); up-down count, TBPRD = 500 at 100 kHz; leg-to-leg 180° via xA/xB swap; secondary phase shift via HRPWM phase (CMPC); direction via DAB_phaseSyncPrimToSecCountDirection [DG §4.1.2.3–4.1.2.4 p.41–43]. Measured phase step 499.8/501.6 ns for 500/502 ns setpoints; software limit 0.13 pu [DG p.52–53, p.62, p.68].
- ADC: SOC from EPWM1; I_DC_PRI C6, V_DC_PRI B11, I_TANK_PRI B1, I_TANK_SEC A6; SDFM D1/D2/D4 [DG §4.1.2.5 p.44].
- Control: ISR1 (loop + PWM update) on EPWM1 TBCTR_U_CMPC; voltage loop DF22 2P2Z (A1 −1.8756666, A2 0.8756666, B0 1.4329852, B1 −2.7994568, B2 1.3664965); current loop PI Kp 0.5, Ki 0.0063030, output ±0.13 pu [DG p.61, p.68]. Loop bandwidth: only SFRA plots, no numeric value published.
- Firmware: DigitalPower SDK solutions/tida_010054/f28003x v3.00.00.00 (SDK 5.02.00.00); DAB solution only on F28003x [RN]. Current SDK 26.01.00.00 (Aug 2026) [TP].
- Newer C2000 devices for digital power: F28P65x (2× C28x 200 MHz + CLA, 36 PWM channels with 150 ps HR, 16-bit ADC), F28003x (120 MHz, 16 ePWM, 8 HR), F280015x (120 MHz lockstep, 14 ePWM, 4 HR); TI lists F29H85, F28E12, F28P65, F28P55, F2800157 for real-time digital power [https://www.ti.com/product-category/microcontrollers-processors/mcus/real-time-digital-power/overview.html].

## 4. Thermal and mechanical

- 4× Ohmite CR201-50VE heat sinks (0.5 K/W), 2 FETs each, CD-02-05-247 pads (0.1 K/W), 2× 12 V fans CFM-6015V-154-362; Rth,JC 1.1 (C3M0075120K) / 0.48 K/W (C3M0030090K); TA = 40 °C design assumption → 50 W/FET (primary), 69 W/FET (secondary) allowable [DG §2.3.5.6 p.27–28; §3.1; BOM].
- Lab use at room ambient only; surfaces > 55 °C; power density > 2 kW/L; transformer Payton 61259, 130×90×52 mm, 5000 VDC dielectric [DG p.4–5; Table 1-1; BOM].
- Isolation statements: TMCS1133 8.1 mm creepage/clearance, 5 kVrms; UCC21710 1.5 kVrms working / 12.8 kVpk surge; AMC1311 7 kVpk; AMC1302 5 kVrms; AMC1306 7 kVpk; AMC1336 8 kVpk; 3× 2200 pF / 3 kV Y-caps [DG §2.2 p.7–8; BOM C59–C61]. Board-level creepage distances: not published.

## 5. Published test results

- Efficiency curves only as plots: SPS at 500/450/400/350 V output over 0–10 kW (Fig. 4-50) and EPS at 500–250 V (Fig. 4-51) [DG p.76–77].
- Calculated losses at 10 kW: SiC conduction 72 W, SiC turn-off 54 W, transformer 50 W, inductor 15 W, driver/shunt 3 W [DG Table 2-3]. No measured loss breakdown is published.

## 6. TI Power Supply Design Seminar library (phase-shift / bidirectional topics)

Source: https://www.ti.com/about-ti/events/power-supply-design-seminar/psds-library.html

1. Phase-shifted full-bridge converter fundamentals (2024), SLUP414, https://www.ti.com/lit/pdf/slup414
2. Designing a high-power bidirectional AC/DC power supply using SiC FETs (2020), SLUP393, https://www.ti.com/lit/slup393
3. Bidirectional DC/DC converter topology comparison and design (2016), SLUP342, https://www.ti.com/lit/slup342
4. Dual half-bridge DC/DC converter with wide-range ZVS and zero circulating current (2010), SLUP259, https://www.ti.com/lit/slup259
5. Designing a phase-shifted ZVT power converter (1993), SLUP101, https://www.ti.com/lit/slup101
6. Design review: 500 W, 40 W/in³ phase-shifted ZVT converter (1993), SLUP102, https://www.ti.com/lit/slup102
7. Fixed-frequency resonant-switched PWM with phase-shifted control (1991), SLUP096, https://www.ti.com/lit/slup096

## Confidence and gaps

- All numbers above were read from the cited TI documents; TIDUES0F contains internal inconsistencies (98.8 % vs 98.7 % peak efficiency, legacy 97.6 % text, legacy UCC21530 loss text).
- Not found in the public documents: numeric loop bandwidths and phase margins, explicit ISR rate, measured loss breakdown, tabulated efficiency points, board-level creepage/clearance, ePWM clock behind TBPRD = 500.
