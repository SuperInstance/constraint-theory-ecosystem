"FLUX Constraint Engine — Smalltalk (1972, Pure Object-Oriented)
Pure INT8 saturated constraint checking. Zero dependencies.

The insight: everything is message passing. Constraints are objects that
UNDERSTAND #check:. Violations are objects that KNOW their severity.
The receiver decides — the caller never branches on type.
No if-statements for dispatch. Messages ARE the polymorphism.

Usage:
  | checker result |
  checker := FluxChecker fromPreset: #aviation.
  result := checker check: 60.
  Transcript show: result severity; cr.        ""caution""
  Transcript show: result errorMask hex; cr.   ""16r01""

Batch:
  results := checker checkBatch: #(-60 0 25 70 127).
"

" ══ Constants ════════════════════════════════════════════════════════ "

Object subclass: #FluxConstants
    instanceVariableNames: ''
    classVariableNames: ''
    package: 'Flux-Constraint'.

FluxConstants class >> int8Min [ ^ -127 ]
FluxConstants class >> int8Max [ ^ 127 ]
FluxConstants class >> maxConstraints [ ^ 8 ]

" ══ Severity ════════════════════════════════════════════════════════ "
" Severity knows its own numeric value and label. Objects all the way down. "

Object subclass: #FluxSeverity
    instanceVariableNames: 'value label'
    classVariableNames: ''
    package: 'Flux-Constraint'.

FluxSeverity class >> pass [ ^ self new setValue: 0 label: 'PASS' ]
FluxSeverity class >> caution [ ^ self new setValue: 1 label: 'CAUTION' ]
FluxSeverity class >> warning [ ^ self new setValue: 2 label: 'WARNING' ]
FluxSeverity class >> critical [ ^ self new setValue: 3 label: 'CRITICAL' ]

FluxSeverity >> setValue: aNumber label: aString [
    value := aNumber. label := aString. ^ self
]

FluxSeverity >> value [ ^ value ]
FluxSeverity >> label [ ^ label ]
FluxSeverity >> isPass [ ^ value = 0 ]
FluxSeverity >> printOn: aStream [ aStream nextPutAll: label ]

" ══ Constraint ═════════════════════════════════════════════════════ "
" A Constraint knows its bounds and name. It saturates itself. "

Object subclass: #FluxConstraintDef
    instanceVariableNames: 'lo hi name'
    classVariableNames: ''
    package: 'Flux-Constraint'.

FluxConstraintDef class >> lo: lo hi: hi name: aString [
    ^ self new initializeLo: (self saturate: lo) hi: (self saturate: hi) name: aString
]

FluxConstraintDef class >> saturate: val [
    val < FluxConstants int8Min ifTrue: [ ^ FluxConstants int8Min ].
    val > FluxConstants int8Max ifTrue: [ ^ FluxConstants int8Max ].
    ^ val
]

FluxConstraintDef >> initializeLo: aLo hi: aHi name: aName [
    lo := aLo. hi := aHi. name := aName
]

FluxConstraintDef >> lo [ ^ lo ]
FluxConstraintDef >> hi [ ^ hi ]
FluxConstraintDef >> name [ ^ name ]

" The key method: a Constraint can CHECK a value. Returns a Violation object. "
FluxConstraintDef >> check: aSaturatedValue [
    | loFail hiFail passed |
    loFail := aSaturatedValue < lo.
    hiFail := aSaturatedValue > hi.
    passed := loFail not and: [ hiFail not ].
    ^ FluxViolation name: name lo: lo hi: hi value: aSaturatedValue
                    loFailed: loFail hiFailed: hiFail passed: passed
]

" ══ Violation ══════════════════════════════════════════════════════ "
" The result of checking one constraint. Knows its own truth. "

Object subclass: #FluxViolation
    instanceVariableNames: 'name lo hi value loFailed hiFailed passed'
    classVariableNames: ''
    package: 'Flux-Constraint'.

FluxViolation class >> name: n lo: l hi: h value: v loFailed: lf hiFailed: hf passed: p [
    ^ self new initName: n lo: l hi: h value: v loFailed: lf hiFailed: hf passed: p
]

FluxViolation >> initName: n lo: l hi: h value: v loFailed: lf hiFailed: hf passed: p [
    name := n. lo := l. hi := h. value := v.
    loFailed := lf. hiFailed := hf. passed := p
]

FluxViolation >> passed [ ^ passed ]
FluxViolation >> loFailed [ ^ loFailed ]
FluxViolation >> hiFailed [ ^ hiFailed ]
FluxViolation >> name [ ^ name ]

" ══ FluxResult ═════════════════════════════════════════════════════ "
" Accumulates violations into the FLUX result structure. "

Object subclass: #FluxResult
    instanceVariableNames: 'errorMask severity violatedLo violatedHi violatedCount passed violations'
    classVariableNames: ''
    package: 'Flux-Constraint'.

FluxResult class >> fromViolations: violations [
    ^ self new buildFrom: violations
]

FluxResult >> buildFrom: violations [
    | n vc |
    errorMask := 0. violatedLo := 0. violatedHi := 0. vc := 0.
    violations := violations.
    n := violations size.

    violations withIndexDo: [:v :i |
        v passed ifFalse: [
            errorMask := errorMask bitOr: (1 bitShift: (i - 1)).
            vc := vc + 1.
        ].
        v loFailed ifTrue: [
            violatedLo := violatedLo bitOr: (1 bitShift: (i - 1)).
        ].
        v hiFailed ifTrue: [
            violatedHi := violatedHi bitOr: (1 bitShift: (i - 1)).
        ].
    ].

    violatedCount := vc.
    passed := vc = 0.

    " Severity from ratio "
    vc = 0
        ifTrue: [ severity := FluxSeverity pass ]
        ifFalse: [
            vc <= (n // 4)
                ifTrue: [ severity := FluxSeverity caution ]
                ifFalse: [
                    vc <= (n // 2)
                        ifTrue: [ severity := FluxSeverity warning ]
                        ifFalse: [ severity := FluxSeverity critical ]
                ]
        ]
]

FluxResult >> errorMask [ ^ errorMask ]
FluxResult >> severity [ ^ severity ]
FluxResult >> violatedLo [ ^ violatedLo ]
FluxResult >> violatedHi [ ^ violatedHi ]
FluxResult >> violatedCount [ ^ violatedCount ]
FluxResult >> passed [ ^ passed ]
FluxResult >> violations [ ^ violations ]

FluxResult >> printOn: aStream [
    aStream nextPutAll: 'FluxResult('.
    passed
        ifTrue: [ aStream nextPutAll: 'PASS' ]
        ifFalse: [
            aStream nextPutAll: severity label;
                    nextPutAll: ' mask=0x'; nextPutAll: (errorMask printStringBase: 16);
                    nextPutAll: ' count='; nextPutAll: violatedCount printString
        ].
    aStream nextPut: $)
]

" ══ FluxChecker ════════════════════════════════════════════════════ "
" The main checker. Holds constraints. Knows how to check. "

Object subclass: #FluxChecker
    instanceVariableNames: 'constraints'
    classVariableNames: ''
    package: 'Flux-Constraint'.

FluxChecker class >> new: constraintList [
    (constraintList isEmpty) ifTrue: [ self error: 'Non-empty constraints required' ].
    (constraintList size > FluxConstants maxConstraints)
        ifTrue: [ self error: 'Maximum 8 constraints' ].
    ^ self new setConstraints: constraintList
]

FluxChecker class >> fromPreset: presetName [
    ^ self new: (self preset: presetName)
]

FluxChecker >> setConstraints: aList [ constraints := aList ]

FluxChecker >> check: rawValue [
    | val violations |
    val := FluxConstraintDef saturate: rawValue.
    violations := constraints collect: [:c | c check: val].
    ^ FluxResult fromViolations: violations
]

FluxChecker >> checkBatch: values [
    ^ values collect: [:v | self check: v]
]

" ══ Industry Presets ═══════════════════════════════════════════════ "

FluxChecker class >> preset: name [
    | presets |
    presets := Dictionary newFromPairs: #(
        aviation     ((-55 70 'cabin_temp_C') (75 101 'cabin_pressure_kPa') (0 100 'fuel_flow_pct') (60 100 'hydraulic_pct'))
        automotive   ((-40 60 'battery_temp_C') (0 100 'soc_pct') (0 100 'charge_rate_pct') (20 80 'cabin_temp_C'))
        maritime     ((-2 35 'sea_temp_C') (50 100 'hull_integrity_pct') (0 50 'wave_height_m') (0 80 'wind_speed_kn'))
        medical      ((36 38 'body_temp_C') (60 100 'heart_rate_bpm') (95 100 'spo2_pct') (80 120 'bp_systolic_mmHg'))
        energy       ((49 51 'grid_freq_Hz_x10') (95 105 'voltage_pct') (0 80 'transformer_temp_C') (0 100 'line_load_pct'))
        nuclear      ((0 110 'neutron_flux_pct') (0 65 'core_temp_C_x10') (72 100 'pressurizer_pct') (0 100 'coolant_flow_pct'))
        railway      ((0 100 'speed_pct') (0 100 'brake_pressure_pct') (0 1 'door_interlock') (0 80 'track_temp_C'))
        robotics     ((-100 100 'joint_torque_pct') (0 100 'speed_pct') (0 100 'force_pct') (-127 127 'position_mm'))
        space        ((-40 50 'temp_C') (0 100 'solar_panel_pct') (0 100 'propellant_pct') (0 100 'battery_pct'))
        underwater   ((0 100 'depth_pct') (0 100 'battery_pct') (-5 35 'water_temp_C') (0 100 'thruster_pct'))
    ).
    ^(presets at: name) collect: [:triplet |
        FluxConstraintDef lo: triplet first hi: triplet second name: triplet third
    ]
]

" ══ Example ════════════════════════════════════════════════════════ "

" | checker result |
  checker := FluxChecker fromPreset: #aviation.
  result := checker check: 60.
  Transcript show: result; cr.        ""FluxResult(CAUTION mask=0x1 count=1)""
  result passed ifFalse: [
      Transcript show: 'Violations: ', result violatedCount printString; cr.
  ].
"

" Everything is message passing. Constraints are objects that UNDERSTAND #check:.
  Violations are objects that KNOW their own severity.
  The receiver decides — the caller never branches on type.
  No if-statements for dispatch. Messages ARE the polymorphism. "
