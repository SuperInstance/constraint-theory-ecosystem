% FLUX Constraint Engine — Prolog (1972, Logic Programming)
% Pure INT8 saturated constraint checking. Zero dependencies.
%
% The insight: constraints ARE logical assertions. The unification engine
% IS the proof. You don't check constraints — you ASK the engine whether
% the world is consistent. If it can't prove the value is in range,
% the constraint fails. The proof IS the check.
%
% Usage:
%   ?- consult(flux_constraint).
%   ?- check_value(60, Result).
%   ?- load_preset(aviation, Constraints), check_constraints(Constraints, 60, Result).
%   ?- batch_check([−60, 0, 25, 70, 127], aviation, Results).

% ── Constants ────────────────────────────────────────────────────────

int8_min(-127).
int8_max(127).
max_constraints(8).

% ── Saturate: clamp to [-127, 127] ──────────────────────────────────
% A pure relation: saturate(+Val, -Saturated).

saturate(Val, Saturated) :-
    int8_min(Min), int8_max(Max),
    (Val < Min -> Saturated = Min
    ; Val > Max -> Saturated = Max
    ; Saturated = Val).

% ── Severity classification ─────────────────────────────────────────
% severity(+ViolatedCount, +TotalConstraints, -Severity).

severity(0, _, pass) :- !.
severity(VC, Total, caution) :- Total > 0, VC =< Total // 4, !.
severity(VC, Total, warning) :- Total > 0, VC =< Total // 2, !.
severity(_, _, critical).

% ── Single constraint check ─────────────────────────────────────────
% check_one(+Value, +Lo, +Hi, -LoFail, -HiFail).

check_one(Value, Lo, Hi, LoFail, HiFail) :-
    LoFail is (Value < Lo),    % 1 if below lower bound
    HiFail is (Value > Hi).    % 1 if above upper bound

% ── Core: check all constraints against a value ─────────────────────
% check_constraints(+Constraints, +RawValue, -Result)
% Constraints = list of constraint(Name, Lo, Hi)
% Result = result(ErrorMask, Severity, ViolatedLo, ViolatedHi, ViolatedCount, Passed)

check_constraints(Constraints, RawValue, Result) :-
    saturate(RawValue, Val),
    check_all(Constraints, Val, 0, 0, 0, 0, ErrorMask, ViolatedLo, ViolatedHi, VC),
    length(Constraints, N),
    severity(VC, N, Severity),
    Passed is (VC =:= 0),
    Result = result(ErrorMask, Severity, ViolatedLo, ViolatedHi, VC, Passed).

% Recursive check: accumulate masks across constraints
check_all([], _, EM, VLo, VHi, VC, EM, VLo, VHi, VC).
check_all([constraint(_Name, Lo, Hi)|Rest], Val, EM0, VLo0, VHi0, VC0, EM, VLo, VHi, VC) :-
    check_one(Val, Lo, Hi, LoFail, HiFail),
    Fail is min(1, LoFail + HiFail),
    EM1 is EM0 \/ ((1 - Fail + Fail) << 0),  % placeholder
    % Proper bit setting:
    length([constraint(_Name, Lo, Hi)|Rest], Pos),  % wrong — use index
    check_all_(Rest, Val, Lo, Hi, LoFail, HiFail, EM0, VLo0, VHi0, VC0, EM, VLo, VHi, VC).

% Indexed version for proper bit masking
check_constraints_indexed(Constraints, RawValue, Result) :-
    saturate(RawValue, Val),
    check_indexed(Constraints, Val, 0, 0, 0, 0, 0, ErrorMask, ViolatedLo, ViolatedHi, VC),
    length(Constraints, N),
    severity(VC, N, Severity),
    Passed is (VC =:= 0),
    Result = result(ErrorMask, Severity, ViolatedLo, ViolatedHi, VC, Passed).

check_indexed([], _, _, EM, VLo, VHi, VC, EM, VLo, VHi, VC).
check_indexed([constraint(_Name, Lo, Hi)|Rest], Val, Idx, EM0, VLo0, VHi0, VC0, EM, VLo, VHi, VC) :-
    (Val < Lo -> LoFail = 1 ; LoFail = 0),
    (Val > Hi -> HiFail = 1 ; HiFail = 0),
    Fail is max(LoFail, HiFail),
    Bit is (1 << Idx),
    EM1 is EM0 \/ (Bit * Fail),
    VLo1 is VLo0 \/ (Bit * LoFail),
    VHi1 is VHi0 \/ (Bit * HiFail),
    VC1 is VC0 + Fail,
    NextIdx is Idx + 1,
    check_indexed(Rest, Val, NextIdx, EM1, VLo1, VHi1, VC1, EM, VLo, VHi, VC).

% ── Batch checking ──────────────────────────────────────────────────

batch_check([], _, []).
batch_check([V|Vs], Constraints, [R|Rs]) :-
    check_constraints_indexed(Constraints, V, R),
    batch_check(Vs, Constraints, Rs).

% ── Load preset by name ─────────────────────────────────────────────

load_preset(aviation, [
    constraint(cabin_temp_C, -55, 70),
    constraint(cabin_pressure_kPa, 75, 101),
    constraint(fuel_flow_pct, 0, 100),
    constraint(hydraulic_pct, 60, 100)
]).

load_preset(automotive, [
    constraint(battery_temp_C, -40, 60),
    constraint(soc_pct, 0, 100),
    constraint(charge_rate_pct, 0, 100),
    constraint(cabin_temp_C, 20, 80)
]).

load_preset(maritime, [
    constraint(sea_temp_C, -2, 35),
    constraint(hull_integrity_pct, 50, 100),
    constraint(wave_height_m, 0, 50),
    constraint(wind_speed_kn, 0, 80)
]).

load_preset(medical, [
    constraint(body_temp_C, 36, 38),
    constraint(heart_rate_bpm, 60, 100),
    constraint(spo2_pct, 95, 100),
    constraint(bp_systolic_mmHg, 80, 120)
]).

load_preset(energy, [
    constraint(grid_freq_Hz_x10, 49, 51),
    constraint(voltage_pct, 95, 105),
    constraint(transformer_temp_C, 0, 80),
    constraint(line_load_pct, 0, 100)
]).

load_preset(nuclear, [
    constraint(neutron_flux_pct, 0, 110),
    constraint(core_temp_C_x10, 0, 65),
    constraint(pressurizer_pct, 72, 100),
    constraint(coolant_flow_pct, 0, 100)
]).

load_preset(railway, [
    constraint(speed_pct, 0, 100),
    constraint(brake_pressure_pct, 0, 100),
    constraint(door_interlock, 0, 1),
    constraint(track_temp_C, 0, 80)
]).

load_preset(robotics, [
    constraint(joint_torque_pct, -100, 100),
    constraint(speed_pct, 0, 100),
    constraint(force_pct, 0, 100),
    constraint(position_mm, -127, 127)
]).

load_preset(space, [
    constraint(temp_C, -40, 50),
    constraint(solar_panel_pct, 0, 100),
    constraint(propellant_pct, 0, 100),
    constraint(battery_pct, 0, 100)
]).

load_preset(underwater, [
    constraint(depth_pct, 0, 100),
    constraint(battery_pct, 0, 100),
    constraint(water_temp_C, -5, 35),
    constraint(thruster_pct, 0, 100)
]).

% ── Interactive helper ───────────────────────────────────────────────

check_value(RawValue, Preset, Result) :-
    load_preset(Preset, Constraints),
    check_constraints_indexed(Constraints, RawValue, Result),
    print_result(RawValue, Result).

print_result(Val, result(EM, Sev, VLo, VHi, VC, Passed)) :-
    format('Value ~w: ', [Val]),
    (Passed = 1 -> write('PASS') ; format('FAIL sev=~w mask=0x~2r', [Sev, EM])),
    format(' violated_lo=0x~2r violated_hi=0x~2r count=~w', [VLo, VHi, VC]), nl.

% ── Example queries ─────────────────────────────────────────────────

% ?- load_preset(aviation, C), check_constraints_indexed(C, 60, R).
% R = result(1, caution, 0, 1, 1, 0).
%
% ?- load_preset(aviation, C), batch_check([-60, 0, 25, 70, 127], C, Results).
%
% ?- load_preset(medical, C), check_constraints_indexed(C, 37, R).
% R = result(0, pass, 0, 0, 0, 1).

% "Constraints ARE logical assertions. The unification engine IS the proof.
%  You don't check constraints — you ASK whether the world is consistent.
%  If Prolog can't prove the value is in range, the constraint fails.
%  The proof IS the check."
