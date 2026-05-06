-module(flux_constraint).
-behaviour(gen_server).
%% FLUX Constraint Engine — Erlang/OTP
%% Pure INT8 saturated constraint checking. Actor-model, supervisor-ready.

-export([saturate/1, check/2, check_batch/2, from_preset/1, presets/0]).
-export([start_link/1, init/1, handle_call/3, terminate/2]).
-export([test/0]).

-define(INT8_MIN, -127).
-define(INT8_MAX, 127).

%%% API

saturate(Val) when Val < ?INT8_MIN -> ?INT8_MIN;
saturate(Val) when Val > ?INT8_MAX -> ?INT8_MAX;
saturate(Val) -> Val.

check(Constraints, Value) ->
    Val = saturate(Value),
    {Em, Vlo, Vhi, Vc} = lists:foldl(
        fun({C, I}, {Em0, Vlo0, Vhi0, Vc0}) ->
            Lo = saturate(maps:get(lo, C)),
            Hi = saturate(maps:get(hi, C)),
            LoFail = Val < Lo,
            HiFail = Val > Hi,
            Bit = 1 bsl I,
            Em1 = case LoFail orelse HiFail of true -> Em0 bor Bit; false -> Em0 end,
            Vlo1 = case LoFail of true -> Vlo0 bor Bit; false -> Vlo0 end,
            Vhi1 = case HiFail of true -> Vhi0 bor Bit; false -> Vhi0 end,
            Vc1 = case LoFail orelse HiFail of true -> Vc0 + 1; false -> Vc0 end,
            {Em1, Vlo1, Vhi1, Vc1}
        end,
        {0, 0, 0, 0},
        lists:zip(Constraints, lists:seq(0, length(Constraints) - 1))
    ),
    Nc = length(Constraints),
    Sev = if
        Vc == 0 -> pass;
        Vc =< Nc div 4 -> caution;
        Vc =< Nc div 2 -> warning;
        true -> critical
    end,
    #{error_mask => Em, severity => Sev, violated_lo => Vlo,
      violated_hi => Vhi, violated_count => Vc, passed => Vc == 0}.

check_batch(Constraints, Values) ->
    Results = [check(Constraints, V) || V <- Values],
    Stats = #{
        pass => length([R || R <- Results, maps:get(severity, R) == pass]),
        caution => length([R || R <- Results, maps:get(severity, R) == caution]),
        warning => length([R || R <- Results, maps:get(severity, R) == warning]),
        critical => length([R || R <- Results, maps:get(severity, R) == critical])
    },
    {Results, Stats}.

presets() -> #{
    aviation => [
        #{lo => -55, hi => 70, name => "cabin_temp_C"},
        #{lo => 75, hi => 101, name => "cabin_pressure_kPa"},
        #{lo => 0, hi => 100, name => "fuel_flow_pct"},
        #{lo => 60, hi => 100, name => "hydraulic_pct"}
    ],
    medical => [
        #{lo => 36, hi => 38, name => "body_temp_C"},
        #{lo => 60, hi => 100, name => "heart_rate_bpm"},
        #{lo => 95, hi => 100, name => "spo2_pct"},
        #{lo => 80, hi => 120, name => "bp_systolic_mmHg"}
    ],
    maritime => [
        #{lo => -2, hi => 35, name => "sea_temp_C"},
        #{lo => 50, hi => 100, name => "hull_integrity_pct"},
        #{lo => 0, hi => 50, name => "wave_height_m"},
        #{lo => 0, hi => 80, name => "wind_speed_kn"}
    ],
    automotive => [
        #{lo => -40, hi => 60, name => "battery_temp_C"},
        #{lo => 0, hi => 100, name => "soc_pct"},
        #{lo => 0, hi => 100, name => "charge_rate_pct"},
        #{lo => 20, hi => 80, name => "cabin_temp_C"}
    ],
    energy => [
        #{lo => 49, hi => 51, name => "grid_freq_Hz_x10"},
        #{lo => 95, hi => 105, name => "voltage_pct"},
        #{lo => 0, hi => 80, name => "transformer_temp_C"},
        #{lo => 0, hi => 100, name => "line_load_pct"}
    ]
}.

from_preset(Name) ->
    maps:get(Name, presets(), error).

%%% gen_server (optional, for OTP supervision)

start_link(Constraints) ->
    gen_server:start_link(?MODULE, Constraints, []).

init(Constraints) ->
    {ok, Constraints}.

handle_call({check, Value}, _From, Constraints) ->
    {reply, check(Constraints, Value), Constraints};
handle_call({check_batch, Values}, _From, Constraints) ->
    {reply, check_batch(Constraints, Values), Constraints}.

terminate(_Reason, _State) -> ok.

%%% Self-test
test() ->
    io:format("FLUX Constraint Engine — Erlang~n"),
    io:format("=============================~n"),
    -127 = saturate(-128), 127 = saturate(128),
    io:format("  saturate: OK~n"),
    R1 = check([#{lo => 0, hi => 100}], 50),
    true = maps:get(passed, R1),
    R2 = check([#{lo => 0, hi => 100}], 150),
    false = maps:get(passed, R2),
    io:format("  check: OK~n"),
    R3 = check([#{lo=>0,hi=>10},#{lo=>0,hi=>10},#{lo=>0,hi=>10},#{lo=>0,hi=>10}], 50),
    critical = maps:get(severity, R3),
    4 = maps:get(violated_count, R3),
    io:format("  severity: OK~n"),
    Av = from_preset(aviation),
    4 = length(Av),
    io:format("  presets: OK~n"),
    io:format("  All tests pass~n"),
    ok.
