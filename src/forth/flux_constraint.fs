\ FLUX Constraint Engine — Forth
\ Pure INT8 saturated constraint checking. Zero dependencies.
\ Stack-based constraint verification for embedded and retro systems.
\
\ Usage:
\   60 CHECK-ALL .SEVERITY .ERROR-MASK
\   AVIATION-PRESET LOAD-PRESET
\   -60 CHECK-ALL .SEVERITY

DECIMAL

\ ── Constants ───────────────────────────────────────────────────────

-127 CONSTANT INT8-MIN
 127 CONSTANT INT8-MAX
   8 CONSTANT MAX-CONSTRAINTS
   0 CONSTANT SEV-PASS
   1 CONSTANT SEV-CAUTION
   2 CONSTANT SEV-WARNING
   3 CONSTANT SEV-CRITICAL

\ ── Constraint storage (8 slots x 3 cells: lo hi name-addr) ─────────

CREATE CONSTRAINTS  MAX-CONSTRAINTS 3 CELLS * ALLOT
VARIABLE #CONSTRAINTS   0 #CONSTRAINTS !

\ ── Result variables ────────────────────────────────────────────────

VARIABLE ERROR-MASK     0 ERROR-MASK !
VARIABLE VIOLATED-LO    0 VIOLATED-LO !
VARIABLE VIOLATED-HI    0 VIOLATED-HI !
VARIABLE VIOLATED-COUNT 0 VIOLATED-COUNT !
VARIABLE SEVERITY       0 SEVERITY !
VARIABLE PASSED         1 PASSED !

\ ── SATURATE ( val -- saturated ) ──────────────────────────────────
\ Clamp to INT8 range [-127, 127]

: SATURATE ( n -- n' )
    DUP INT8-MIN < IF DROP INT8-MIN ELSE
    DUP INT8-MAX > IF DROP INT8-MAX THEN THEN ;

\ ── CLEAR-RESULTS ───────────────────────────────────────────────────

: CLEAR-RESULTS ( -- )
    0 ERROR-MASK !
    0 VIOLATED-LO !
    0 VIOLATED-HI !
    0 VIOLATED-COUNT !
    0 SEVERITY !
    1 PASSED ! ;

\ ── ADD-CONSTRAINT ( lo hi -- ) ────────────────────────────────────
\ Add a constraint to the current set (max 8)

: ADD-CONSTRAINT ( lo hi -- )
    #CONSTRAINTS @ MAX-CONSTRAINTS >= ABORT" Max 8 constraints"
    #CONSTRAINTS @ 3 CELLS * CONSTRAINTS +   ( lo hi addr )
    >R
    R@ !          ( lo -- store hi )
    R@ CELL+ !    ( -- store lo )
    R> 2 CELLS + 0 SWAP !  ( -- zero name slot )
    1 #CONSTRAINTS +! ;

\ ── CLEAR-CONSTRAINTS ───────────────────────────────────────────────

: CLEAR-CONSTRAINTS ( -- )
    0 #CONSTRAINTS ! ;

\ ── CHECK-CONSTRAINT ( value index -- lo_fail hi_fail ) ────────────
\ Check value against constraint at index. Returns flags on stack.

: CHECK-CONSTRAINT ( val idx -- lo_fail hi_fail )
    3 CELLS * CONSTRAINTS +   ( val caddr )
    DUP CELL+ @               ( val caddr lo ) 
    ROT                       ( caddr lo val )
    OVER > >R                 ( caddr lo -- lo_fail on rstack )
    @                         ( lo -- hi )
    R>                        ( hi lo_fail )
    SWAP                      ( lo_fail hi )
    OVER <                    ( lo_fail hi hi_fail )
    SWAP ;                    ( hi lo_fail -- lo_fail hi_fail ) 

\ ── CHECK-ALL ( value -- ) ─────────────────────────────────────────
\ Check value against ALL loaded constraints. Fills result variables.

: CHECK-ALL ( value -- )
    CLEAR-RESULTS
    SATURATE                      ( saturated_val )
    #CONSTRAINTS @ 0 DO           ( val )
        DUP I CHECK-CONSTRAINT    ( val lo_fail hi_fail )
        OVER OR OVER OR           ( val lo_fail|hi_fail lo_fail|hi_fail )
        0= IF                     ( val lo_fail hi_fail -- all passed? )
            2DROP                 ( val -- no violation )
        ELSE
            \ Update error mask
            1 I LSHIFT ERROR-MASK @ OR ERROR-MASK !
            \ Track lo/hi violations
            OVER IF 1 I LSHIFT VIOLATED-LO @ OR VIOLATED-LO ! THEN
            DUP  IF 1 I LSHIFT VIOLATED-HI @ OR VIOLATED-HI ! THEN
            \ Increment violated count
            1 VIOLATED-COUNT +!
            2DROP                 ( val -- )
        THEN
    LOOP
    DROP                          ( -- done with value )
    \ Classify severity
    VIOLATED-COUNT @ 0= IF
        SEV-PASS SEVERITY !
        1 PASSED !
    ELSE
        0 PASSED !
        #CONSTRAINTS @ 4 /       ( nc/4 threshold )
        VIOLATED-COUNT @ OVER <= IF
            SEV-CAUTION SEVERITY !
        ELSE
            #CONSTRAINTS @ 2 /   ( nc/2 threshold )
            VIOLATED-COUNT @ OVER <= IF
                SEV-WARNING SEVERITY !
            ELSE
                SEV-CRITICAL SEVERITY !
            THEN
        THEN
    THEN ;

\ ── Display helpers ─────────────────────────────────────────────────

: .SEVERITY ( -- )
    SEVERITY @ CASE
        0 OF ." PASS" ENDOF
        1 OF ." CAUTION" ENDOF
        2 OF ." WARNING" ENDOF
        3 OF ." CRITICAL" ENDOF
        ." UNKNOWN" ENDCASE ;

: .ERROR-MASK ( -- )
    ." 0x" ERROR-MASK @ 0 <# # # #> TYPE SPACE ;

: .RESULT ( -- )
    .SEVERITY .ERROR-MASK
    PASSED @ IF ." PASS" ELSE ." FAIL" THEN CR ;

\ ── Industry Presets ────────────────────────────────────────────────

: AVIATION-PRESET ( -- )
    CLEAR-CONSTRAINTS
    -55  70 ADD-CONSTRAINT   \ cabin_temp_C
     75 101 ADD-CONSTRAINT   \ cabin_pressure_kPa
      0 100 ADD-CONSTRAINT   \ fuel_flow_pct
     60 100 ADD-CONSTRAINT ; \ hydraulic_pct

: AUTOMOTIVE-PRESET ( -- )
    CLEAR-CONSTRAINTS
    -40  60 ADD-CONSTRAINT   \ battery_temp_C
      0 100 ADD-CONSTRAINT   \ soc_pct
      0 100 ADD-CONSTRAINT   \ charge_rate_pct
     20  80 ADD-CONSTRAINT ; \ cabin_temp_C

: MARITIME-PRESET ( -- )
    CLEAR-CONSTRAINTS
     -2  35 ADD-CONSTRAINT   \ sea_temp_C
     50 100 ADD-CONSTRAINT   \ hull_integrity_pct
      0  50 ADD-CONSTRAINT   \ wave_height_m
      0  80 ADD-CONSTRAINT ; \ wind_speed_kn

: MEDICAL-PRESET ( -- )
    CLEAR-CONSTRAINTS
     36  38 ADD-CONSTRAINT   \ body_temp_C
     60 100 ADD-CONSTRAINT   \ heart_rate_bpm
     95 100 ADD-CONSTRAINT   \ spo2_pct
     80 120 ADD-CONSTRAINT ; \ bp_systolic_mmHg

: ENERGY-PRESET ( -- )
    CLEAR-CONSTRAINTS
     49  51 ADD-CONSTRAINT   \ grid_freq_Hz_x10
     95 105 ADD-CONSTRAINT   \ voltage_pct
      0  80 ADD-CONSTRAINT   \ transformer_temp_C
      0 100 ADD-CONSTRAINT ; \ line_load_pct

: NUCLEAR-PRESET ( -- )
    CLEAR-CONSTRAINTS
      0 110 ADD-CONSTRAINT   \ neutron_flux_pct
      0  65 ADD-CONSTRAINT   \ core_temp_C_x10
     72 100 ADD-CONSTRAINT   \ pressurizer_pct
      0 100 ADD-CONSTRAINT ; \ coolant_flow_pct

: RAILWAY-PRESET ( -- )
    CLEAR-CONSTRAINTS
      0 100 ADD-CONSTRAINT   \ speed_pct
      0 100 ADD-CONSTRAINT   \ brake_pressure_pct
      0   1 ADD-CONSTRAINT   \ door_interlock
      0  80 ADD-CONSTRAINT ; \ track_temp_C

: ROBOTICS-PRESET ( -- )
    CLEAR-CONSTRAINTS
   -100 100 ADD-CONSTRAINT   \ joint_torque_pct
      0 100 ADD-CONSTRAINT   \ speed_pct
      0 100 ADD-CONSTRAINT   \ force_pct
   -127 127 ADD-CONSTRAINT ; \ position_mm

: SPACE-PRESET ( -- )
    CLEAR-CONSTRAINTS
    -40  50 ADD-CONSTRAINT   \ temp_C
      0 100 ADD-CONSTRAINT   \ solar_panel_pct
      0 100 ADD-CONSTRAINT   \ propellant_pct
      0 100 ADD-CONSTRAINT ; \ battery_pct

: UNDERWATER-PRESET ( -- )
    CLEAR-CONSTRAINTS
      0 100 ADD-CONSTRAINT   \ depth_pct
      0 100 ADD-CONSTRAINT   \ battery_pct
     -5  35 ADD-CONSTRAINT   \ water_temp_C
      0 100 ADD-CONSTRAINT ; \ thruster_pct

\ ── Demo ────────────────────────────────────────────────────────────

: DEMO ( -- )
    CR ." ╔══════════════════════════════════════════╗" CR
      ." ║  FLUX Constraint Engine — Forth          ║" CR
      ." ╚══════════════════════════════════════════╝" CR CR

    AVIATION-PRESET
    ." Aviation preset: " #CONSTRAINTS @ . ." constraints" CR CR

    ." Examples:" CR
    -60 CHECK-ALL   ."   val=-60: " .RESULT
      0 CHECK-ALL   ."   val=  0: " .RESULT
     25 CHECK-ALL   ."   val= 25: " .RESULT
     70 CHECK-ALL   ."   val= 70: " .RESULT
     90 CHECK-ALL   ."   val= 90: " .RESULT
    127 CHECK-ALL   ."   val=127: " .RESULT

    CR ." All 10 presets: aviation automotive maritime medical" CR
    ."   energy nuclear railway robotics space underwater" CR ;

DEMO
