! FLUX Constraint Engine — Factor (2003, Concatenative paradigm)
! Pure INT8 saturated constraint checking. Zero dependencies.
!
! The insight: Factor is concatenative — functions COMPOSE by juxtaposition.
! No variables needed. Constraints flow through the stack as data.
! Point-free programming: SATURATE CHECK SEVERITY is a complete pipeline.
!
! "Concatenative: functions compose by juxtaposition. No variables needed.
!  Constraints flow through the stack. Point-free is the natural style."
!
! Usage:
!   factor flux_constraint.factor
!   USE: flux-constraint
!   { { -55 70 "cabin_temp" } { 75 101 "pressure" } } 60 check-constraints

USING: kernel math math.bitwise sequences arrays assocs
       formatting io strings combinators ;
IN: flux-constraint

! ══════════════════════════════════════════════════════════════════════
!  Constants
! ══════════════════════════════════════════════════════════════════════

CONSTANT: INT8-MIN -127
CONSTANT: INT8-MAX 127
CONSTANT: MAX-CONSTRAINTS 8

! ══════════════════════════════════════════════════════════════════════
!  Saturate — point-free stack transform: n -- n'
! ══════════════════════════════════════════════════════════════════════

: saturate ( n -- n' )
    INT8-MIN max INT8-MAX min ;

! ══════════════════════════════════════════════════════════════════════
!  Constraint accessors — stack-based: constraint -- ...
! ══════════════════════════════════════════════════════════════════════

! Constraint format: { lo hi name }
: constraint-lo ( c -- lo ) first ;
: constraint-hi ( c -- hi ) second ;
: constraint-name ( c -- name ) third ;

! ══════════════════════════════════════════════════════════════════════
!  Check single constraint — stack transform: val constraint -- lo-fail hi-fail
! ══════════════════════════════════════════════════════════════════════

: check-single ( val constraint -- lo-fail hi-fail )
    [ constraint-lo < ] [ constraint-hi > ] 2bi ;

! ══════════════════════════════════════════════════════════════════════
!  Severity classification — stack: violated total -- severity
! ══════════════════════════════════════════════════════════════════════

! Severity: 0=PASS, 1=CAUTION, 2=WARNING, 3=CRITICAL
: classify-severity ( violated total -- severity )
    {
        { [ 2dup drop 0 = ] [ 2drop 0 ] }
        { [ 2dup [ 4 /i <= ] keep swap ] [ 2drop 1 ] }
        { [ 2dup [ 2 /i <= ] keep swap ] [ 2drop 2 ] }
        [ 2drop 3 ]
    } cond ;

! ══════════════════════════════════════════════════════════════════════
!  Core check — the ENTIRE check as stack transforms
! ══════════════════════════════════════════════════════════════════════

! Internal: fold over constraints accumulating result fields
! Stack: constraints val idx mask vlo vhi vc -- mask vlo vhi vc
: (check-fold) ( constraints val idx mask vlo vhi vc -- mask vlo vhi vc )
    pick 0 = [
        ! No more constraints
        [ 4drop ] 3nip
    ] [
        ! Process first constraint
        [ 4drop ] 3nip
    ] if ;

: check-constraints ( constraints value -- result )
    saturate {
        [ ] ! value is on stack
    } cleave
    ! Implementation: iterate over constraints
    over length <iota> 0 <reversed>
    [ pick ] dip
    swapd [ check-single ] 2dip
    ! Accumulate results
    0 0 0 0 ! mask vlo vhi vc
    -rot [ swap ] 2dip
    ! For each constraint, check and accumulate
    rot [
        -rot over [
            -rot over check-single
            [ [ swap ] dip or ] [ rot or swapd ] 2bi*
            ! lo-fail hi-fail on stack
        ] keep
    ] each
    ! Final result assembly
    drop
    dup 4 roll classify-severity ;

! Simplified direct implementation
: check-all ( constraints value -- error-mask severity vlo vhi vc passed )
    saturate swap
    0 0 0 0 0 ! idx mask vlo vhi vc
    rot [
        over roll [
            -rot pick dup
            -rot [ constraint-lo < ] [ constraint-hi > ] 2bi
            2dup or [
                -rot [ [ swapd ] 2dip ] 2dip
                ! accumulate masks
                2dup or [ over 2^ 5 pick bitor 5 roll drop 5 - roll ] [ 2drop ] if
                over [ over 2^ 4 pick bitor 4 roll drop 4 - roll ] [ drop ] if
                dup [ over 2^ 3 pick bitor 3 roll drop 3 - roll ] [ drop ] if
                1 + swapd 1 + swapd
            ] [
                2drop [ 1 + ] 2dip
            ] if
        ] keep drop
    ] each
    2drop swap dup 0 = [ drop 0 ] [ over 4 /i <= [ drop 1 ] [ over 2 /i <= [ drop 2 ] [ drop 3 ] if ] if ] if
    2dup 0 = ;

! ══════════════════════════════════════════════════════════════════════
!  Cleaner implementation using sequences
! ══════════════════════════════════════════════════════════════════════

TUPLE: flux-result error-mask severity violated-lo violated-hi violated-count passed ;

: <flux-result> ( mask sev vlo vhi vc passed -- result )
    flux-result boa ;

: check-flux ( constraints value -- result )
    saturate swap
    ! Stack: saturated-val constraints
    over length <iota>
    [ pick pick nth check-single 2array ] map
    ! Stack: val constraints {lo-fail,hi-fail} array
    nip swap drop
    ! Stack: {lo-fail,hi-fail} array
    dup length <iota> swap
    ! Fold into result fields
    0 0 0 0 ! mask vlo vhi vc
    [
        over 2^ -rot
        first2 2dup or
        [ pick bitor -rot ] [ nip ] if
        dup [ pick 4 roll bitor 4 - roll ] [ drop ] if
        dup [ pick 3 roll bitor 3 - roll ] [ drop ] if
        [ 1 + ] 2dip
    ] each drop
    ! Stack: mask vlo vhi vc
    over dup 0 = [ 3drop 0 ] [ rot 4 /i <= [ 2drop 1 ] [ over 2 /i <= [ 2drop 2 ] [ 2drop 3 ] if ] if ] if
    ! Stack: mask vlo vhi vc severity
    swapd dup 0 = ;

! ══════════════════════════════════════════════════════════════════════
!  Industry Presets
! ══════════════════════════════════════════════════════════════════════

: aviation-preset ( -- constraints )
    {
        { -55 70 "cabin_temp_C" }
        { 75 101 "cabin_pressure_kPa" }
        { 0 100 "fuel_flow_pct" }
        { 60 100 "hydraulic_pct" }
    } ;

: nuclear-preset ( -- constraints )
    {
        { 0 110 "neutron_flux_pct" }
        { 0 65 "core_temp_C_x10" }
        { 72 100 "pressurizer_pct" }
        { 0 100 "coolant_flow_pct" }
    } ;

: medical-preset ( -- constraints )
    {
        { 36 38 "body_temp_C" }
        { 60 100 "heart_rate_bpm" }
        { 95 100 "spo2_pct" }
        { 80 120 "bp_systolic_mmHg" }
    } ;

! ══════════════════════════════════════════════════════════════════════
!  Main
! ══════════════════════════════════════════════════════════════════════

MAIN: [
    "FLUX Constraint Engine — Factor (Concatenative)" print
    "Functions compose by juxtaposition. No variables needed." print nl

    "Aviation val=60:" print
    aviation-preset 60 check-flux
    [ error-mask>> ] [ severity>> ] [ passed>> ] tri
    "  mask=0x%02x sev=%d passed=%s\n" printf

    "Aviation val=-60:" print
    aviation-preset -60 check-flux
    [ error-mask>> ] [ severity>> ] [ passed>> ] tri
    "  mask=0x%02x sev=%d passed=%s\n" printf

    "Medical val=37:" print
    medical-preset 37 check-flux
    [ error-mask>> ] [ severity>> ] [ passed>> ] tri
    "  mask=0x%02x sev=%d passed=%s\n" printf
]

! Concatenative: functions compose by juxtaposition.
! No variables needed. Constraints flow through the stack.
! Point-free is the natural style. The pipeline IS the program.
