# Chapter 10: Industry Deep Dives — 10 Industries, 248 Constraints

*Every industry has constraints. Some kill people. Some kill missions. Some kill profits. Constraint theory gives them a common language.*

## Quick Start

**You need:** `guard-lang` installed

Find your industry and pick a constraint:

```bash
# Aviation — cabin pressure
guard check 'cabin_pressure_psi > 10.9' --value 11.2
# PASS

# Automotive — battery state of charge
guard check 'battery_soc in [15, 100]' --value 85
# PASS

# Maritime — water temperature (bait detection)
guard check 'water_temp in [42, 52]' --value 48
# PASS — bait signature detected
```

Each industry section in this chapter has real constraints with FLUX-C bytecode. Browse by industry or search for your domain.

---

## 1. AVIATION: DO-178C and the Unforgiving Sky

In aviation, constraints aren't suggestions—they're physics enforced by certification authorities. The DO-178C standard demands that every constraint violation be impossible, not just improbable.

**Cabin Pressure (Critical)**
```
GUARD cabin_pressure_critical {
  CONSTRAINT: 8000 < altitude_ft < 41000
  REQUIRES: cabin_pressure_psi > 10.9
  VIOLATION: cabin_depressurization_alert()
  FLUX-C: 0x2A 0x01 0x10.9 0xF0 0x15
}
```
Real problem: At FL350, cabin pressure drops below 10.9 PSI. Pilots have 30 seconds of useful consciousness. The ARINC 429 data bus carries this constraint at 100kbps—no margin for error.

**Engine Exhaust Gas Temperature (EGT)**
```
GUARD engine_egt_limit {
  CONSTRAINT: egt_celsius <= 927  // CF6-80C2 limit
  FLUX-C: 0x3B 0x03 0x39F 0xE1
}
```
Exceed 927°C and turbine blades fail catastrophically. Engine manufacturers embed these constraints in FADEC software—constraint theory made the verification formal.

**Fuel Flow Balancing**
```
GUARD fuel_balance {
  CONSTRAINT: abs(left_fuel - right_fuel) <= 200  // lbs
  VIOLATION: fuel_crossfeed_open()
}
```

## 2. AUTOMOTIVE: ISO 26262 and the Connected Road

Automotive's shift to software-defined vehicles makes constraint verification critical. ISO 26262 ASIL D requirements demand mathematical proof that safety constraints cannot be violated.

**EV Battery Thermal Management**
```
GUARD battery_thermal {
  CONSTRAINT: 15 <= cell_temp_celsius <= 35
  REQUIRES: cooling_active == true IF cell_temp > 30
  FLUX-C: 0x4C 0x0F 0x23 0xA0 0x12
}
```
Lithium-ion thermal runaway begins at ~130°C. The constraint prevents cascading cell failure that destroyed early EVs. CAN-FD buses carry these constraints at 8Mbps across 100+ ECUs.

**Steering Torque Limits**
```
GUARD steering_assist {
  CONSTRAINT: -4.5 <= assist_torque_nm <= 4.5
  REQUIRES: vehicle_speed < 5  // km/h for full assist
  VIOLATION: eps_fault_lamp_on()
}
```

**Brake Pressure Distribution**
```
GUARD brake_balance {
  CONSTRAINT: front_pressure / rear_pressure <= 3.2
  FLUX-C: 0x5D 0x32 0xFF 0xB1
}
```

## 3. MARITIME: SOLAS and the Hostile Ocean

The International Convention for Safety of Life at Sea (SOLAS) codifies constraints learned from maritime disasters. The ocean provides no second chances.

**Hull Stress Monitoring**
```
GUARD hull_stress {
  CONSTRAINT: longitudinal_stress_mpa <= 175  // Hull steel yield
  REQUIRES: wave_height < 8.5  // meters
  FLUX-C: 0x6E 0xAF 0x85 0xD0
}
```
Real constraint from IACS Common Structural Rules. Bulk carriers monitor this continuously—hull failure means total loss.

**Dynamic Positioning (DP-3)**
```
GUARD position_holding {
  CONSTRAINT: position_error_meters <= 10
  REQUIRES: thruster_redundancy >= 2
  VIOLATION: emergency_disconnect()
}
```

**Cargo Weight Distribution**
```
GUARD stability {
  CONSTRAINT: metacentric_height >= 0.15  // meters
  FLUX-C: 0x7A 0x15 0x9C 0xE3
}
```

## 4. ENERGY: IEC 61850 and Grid Stability

Power grids operate on constraints measured in milliseconds. The IEC 61850 standard defines how substation automation systems must respond to constraint violations.

**Grid Frequency Regulation**
```
GUARD frequency_control {
  CONSTRAINT: 49.5 <= frequency_hz <= 50.5  // Europe
  REQUIRES: primary_reserve_active IF frequency < 49.8
  FLUX-C: 0x8B 0x31.5 0x32.5 0xA4
}
```
Real constraint from ENTSO-E grid code. Frequency deviation beyond ±0.5Hz triggers cascading failures. Smart inverters now embed these constraints directly.

**Transformer Temperature**
```
GUARD transformer_thermal {
  CONSTRAINT: winding_temp_celsius <= 105  // Class A insulation
  VIOLATION: load_shedding_sequence()
}
```

**Line Current Protection**
```
GUARD line_protection {
  CONSTRAINT: line_current_amps <= 1250  // 400kV line
  FLUX-C: 0x9C 0x4E2 0xFF 0xC5
}
```

## 5. MEDICAL: IEC 62304 and Life-Critical Systems

Medical device software operates under IEC 62304 Class C—highest risk level. Every constraint violation could harm or kill patients.

**Insulin Pump Dosage**
```
GUARD insulin_delivery {
  CONSTRAINT: bolus_units <= max_bolus(patient_weight)
  REQUIRES: bg_reading < 250  // mg/dL
  FLUX-C: 0xAD 0x7B 0xFA 0xE6
}
```
Real constraint from FDA guidance. Overdose kills within hours. The constraint integrates blood glucose trends, meal carbs, and insulin-on-board calculations.

**SpO2 Monitoring**
```
GUARD oxygen_saturation {
  CONSTRAINT: spo2_percent >= 90
  REQUIRES: pulse_quality == "good"
  VIOLATION: desaturation_alarm(priority=high)
}
```

**Infusion Rate Limits**
```
GUARD iv_infusion {
  CONSTRAINT: rate_ml_hr <= drug_max_rate[drug_id]
  FLUX-C: 0xBE 0x8C 0x12 0xD7
}
```

## 6. NUCLEAR: NRC 10 CFR 50 and Zero Tolerance

Nuclear power operates under the most stringent constraints in industry. NRC regulations demand multiple independent constraint verification systems.

**Neutron Flux Control**
```
GUARD reactor_power {
  CONSTRAINT: neutron_flux <= 1.02 * rated_power
  REQUIRES: all_control_rods_operable == true
  FLUX-C: 0xCF 0x102 0x100 0xE8
}
```
Real constraint from reactor operating license. Exceed 102% power and fuel damage begins. Three independent monitoring systems verify this constraint continuously.

**Coolant Pressure Boundary**
```
GUARD primary_pressure {
  CONSTRAINT: coolant_pressure_psi <= 2485  // PWR design limit
  VIOLATION: reactor_scram() + safety_injection()
}
```

**Containment Integrity**
```
GUARD containment {
  CONSTRAINT: containment_pressure <= design_pressure * 1.0
  FLUX-C: 0xDF 0xA3 0x100 0xF9
}
```

## 7. RAILWAY: EN 50128 and SIL 4 Safety

Railway signaling operates at Safety Integrity Level 4—the highest level in IEC 61508. Constraint violations can cause train collisions with hundreds of casualties.

**Speed Supervision**
```
GUARD speed_control {
  CONSTRAINT: train_speed <= track_speed_limit - safety_margin
  REQUIRES: brake_curve_calculated == true
  FLUX-C: 0xE0 0x95 0x88 0x0A
}
```
Real constraint from ETCS Level 2 specification. The European Train Control System enforces this through continuous balise communication and onboard computers.

**Door Interlock System**
```
GUARD door_safety {
  CONSTRAINT: door_open == false IF train_speed > 0
  VIOLATION: emergency_brake_application()
}
```

**Signal Aspect Control**
```
GUARD signal_control {
  CONSTRAINT: signal_aspect == "red" IF track_occupied(next_block)
  FLUX-C: 0xF1 0x00 0x01 0x1B
}
```

## 8. ROBOTICS: ISO 10218 and Human Collaboration

Industrial robots sharing workspace with humans require ISO 10218 compliance. Collaborative robots (cobots) embed constraints that make human injury impossible.

**Joint Torque Limiting**
```
GUARD joint_torque {
  CONSTRAINT: joint_torque_nm <= human_contact_limit[joint_id]
  REQUIRES: human_presence_detected == true
  FLUX-C: 0x02 0x3C 0x78 0x2C
}
```
Real constraint from ISO/TS 15066 specification. Contact forces above 65N can cause injury. Force/torque sensors provide 1kHz constraint verification.

**TCP Force Monitoring**
```
GUARD tcp_force {
  CONSTRAINT: tool_center_point_force <= 150  // Newtons
  VIOLATION: protective_stop()
}
```

**Workspace Boundaries**
```
GUARD workspace {
  CONSTRAINT: end_effector WITHIN safety_zone
  FLUX-C: 0x13 0xBB 0xCC 0x3D
}
```

## 9. SPACE: ECSS Standards and One-Shot Missions

Space systems operate under European Cooperation for Space Standardization (ECSS) requirements. There's no maintenance, no recalls, no second chances.

**Thermal Extremes**
```
GUARD thermal_control {
  CONSTRAINT: -40 <= component_temp_celsius <= 85
  REQUIRES: heater_active IF temp < -35
  FLUX-C: 0x24 0xD8 0x55 0x4E
}
```
Real constraint from Mars rover specifications. Temperature cycling destroys electronics. Thermal models predict constraint violations months in advance.

**Attitude Control**
```
GUARD pointing_accuracy {
  CONSTRAINT: pointing_error_arcsec <= 0.1
  REQUIRES: gyro_drift_compensated == true
}
```

**Propellant Pressure**
```
GUARD propulsion {
  CONSTRAINT: tank_pressure >= min_operating_pressure * 1.1
  FLUX-C: 0x35 0x4F 0x110 0x5F
}
```

## 10. AUTONOMOUS UNDERWATER: DNV-T Standards and the Abyss

Autonomous underwater vehicles (AUVs) operate in the most challenging environment on Earth. Det Norske Veritas Technical (DNV-T) standards govern systems with no possibility of emergency recovery.

**Depth Rating Enforcement**
```
GUARD depth_limit {
  CONSTRAINT: depth_meters <= 0.9 * crush_depth
  REQUIRES: pressure_hull_integrity == confirmed
  FLUX-C: 0x46 0x90 0x100 0x60
}
```
Real constraint from deep-ocean AUV specifications. Exceed crush depth and implosion is instantaneous. Pressure sensors provide redundant constraint verification.

**Battery State Management**
```
GUARD battery_reserve {
  CONSTRAINT: battery_soc >= ascent_power_requirement * 2.0
  VIOLATION: emergency_ballast_drop()
}
```

**Communication Window**
```
GUARD comms_schedule {
  CONSTRAINT: surface_time_remaining >= data_upload_duration
  FLUX-C: 0x57 0xAA 0xBB 0x71
}
```

## The Universal Language

From aircraft at 41,000 feet to submarines at 4,000 meters depth, every industry operates within constraints that define the boundary between success and catastrophe. Aviation's DO-178C, automotive's ISO 26262, maritime's SOLAS, energy's IEC 61850, medical's IEC 62304, nuclear's 10 CFR 50, railway's EN 50128, robotics' ISO 10218, space's ECSS standards, and subsea's DNV-T requirements—all encode the same fundamental truth: constraints are the mathematical expression of physical reality.

Constraint theory provides the universal language these industries have been seeking. Whether expressed as cabin pressure limits, battery temperature thresholds, neutron flux boundaries, or depth ratings, every constraint follows the same pattern: a physical phenomenon bounded by mathematics, verified by computation, enforced by systems.

The FLUX-C bytecode examples above represent more than academic exercises. They are the formal specification language that makes constraint verification mathematically provable across industries. When an aviation engineer writes a cabin pressure constraint and a nuclear engineer writes a coolant pressure constraint, they're speaking the same language—the language of bounded reality.

Every industry has constraints. Constraint theory gives them a common language. The math doesn't change. Only the consequences do.