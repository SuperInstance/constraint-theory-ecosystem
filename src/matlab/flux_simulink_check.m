% FLUX Constraint Engine — MATLAB/Simulink Integration
% INT8 saturated constraint checking for Simulink models.
%
% The insight: MATLAB/Simulink dominates safety-critical model-based design
% (DO-178C, ISO 26262, IEC 61508). Constraint checking belongs IN the model,
% not bolted on afterward. This integrates FLUX as a MATLAB function block
% that can be dropped into any Simulink model.
%
% Architecture:
%   Simulink Model → MATLAB Function Block → flux_simulink_check()
%     → saturate → check → severity → output port → alarm/flag/log
%
% "Simulink is where safety engineers LIVE. FLUX belongs inside the model,
%  not in a separate codebase that nobody reads."
%
% Usage:
%   1. Add flux_simulink_check.m to MATLAB path
%   2. In Simulink: Add MATLAB Function block
%   3. Paste call: [mask, sev, pass] = flux_simulink_check(value, lo_vec, hi_vec)
%   4. Connect severity output to alarm subsystem
%
% Tested with: MATLAB R2023b, GNU Octave 8.x
% Zero dependencies. Works in both MATLAB and Octave.

% ═══════════════════════════════════════════════════════════════════════
% CORE: flux_simulink_check
% ═══════════════════════════════════════════════════════════════════════

function [error_mask, severity, passed, violated_lo, violated_hi, violated_count] = ...
    flux_simulink_check(value, lo_vec, hi_vec)
%FLUX_SIMULINK_CHECK Check value against INT8 saturated constraints
%   Simulink-compatible function block.
%
%   Inputs:
%     value   - scalar sensor value (int)
%     lo_vec  - 1×N vector of lower bounds
%     hi_vec  - 1×N vector of upper bounds
%
%   Outputs:
%     error_mask     - uint8 bitmask of violations
%     severity       - 0=PASS, 1=CAUTION, 2=WARNING, 3=CRITICAL
%     passed         - boolean (true if all pass)
%     violated_lo    - uint8 bitmask of lo violations
%     violated_hi    - uint8 bitmask of hi violations
%     violated_count - number of violations

    INT8_MIN = -127;
    INT8_MAX = 127;

    % Saturate the input value
    val = max(INT8_MIN, min(INT8_MAX, round(value)));

    nc = length(lo_vec);
    error_mask = uint8(0);
    violated_lo = uint8(0);
    violated_hi = uint8(0);
    violated_count = 0;

    for i = 1:nc
        lo_sat = max(INT8_MIN, min(INT8_MAX, round(lo_vec(i))));
        hi_sat = max(INT8_MIN, min(INT8_MAX, round(hi_vec(i))));

        lo_fail = val < lo_sat;
        hi_fail = val > hi_sat;
        bit = bitshift(uint8(1), i - 1);

        if lo_fail || hi_fail
            error_mask = bitor(error_mask, bit);
            violated_count = violated_count + 1;
        end
        if lo_fail
            violated_lo = bitor(violated_lo, bit);
        end
        if hi_fail
            violated_hi = bitor(violated_hi, bit);
        end
    end

    % Severity classification
    if violated_count == 0
        severity = 0;  % PASS
    elseif violated_count <= floor(nc / 4)
        severity = 1;  % CAUTION
    elseif violated_count <= floor(nc / 2)
        severity = 2;  % WARNING
    else
        severity = 3;  % CRITICAL
    end

    passed = (violated_count == 0);
end

% ═══════════════════════════════════════════════════════════════════════
% PRESET LOADER
% ═══════════════════════════════════════════════════════════════════════

function [lo_vec, hi_vec, names] = flux_preset(preset_name)
%FLUX_PRESET Load industry preset constraint bounds
%   Returns vectors compatible with Simulink MATLAB Function blocks.
%
%   Usage: [lo, hi, names] = flux_preset('aviation')

    switch lower(preset_name)
        case 'aviation'
            lo_vec = [-55, 75, 0, 60];
            hi_vec = [70, 101, 100, 100];
            names = {'cabin_temp_C', 'cabin_pressure_kPa', 'fuel_flow_pct', 'hydraulic_pct'};
        case 'automotive'
            lo_vec = [-40, 0, 0, 20];
            hi_vec = [60, 100, 100, 80];
            names = {'battery_temp_C', 'soc_pct', 'charge_rate_pct', 'cabin_temp_C'};
        case 'medical'
            lo_vec = [36, 60, 95, 80];
            hi_vec = [38, 100, 100, 120];
            names = {'body_temp_C', 'heart_rate_bpm', 'spo2_pct', 'bp_systolic_mmHg'};
        case 'nuclear'
            lo_vec = [0, 0, 72, 0];
            hi_vec = [110, 65, 100, 100];
            names = {'neutron_flux_pct', 'core_temp_C_x10', 'pressurizer_pct', 'coolant_flow_pct'};
        case 'maritime'
            lo_vec = [-2, 50, 0, 0];
            hi_vec = [35, 100, 50, 80];
            names = {'sea_temp_C', 'hull_integrity_pct', 'wave_height_m', 'wind_speed_kn'};
        case 'energy'
            lo_vec = [49, 95, 0, 0];
            hi_vec = [51, 105, 80, 100];
            names = {'grid_freq_Hz_x10', 'voltage_pct', 'transformer_temp_C', 'line_load_pct'};
        case 'railway'
            lo_vec = [0, 0, 0, 0];
            hi_vec = [100, 100, 1, 80];
            names = {'speed_pct', 'brake_pressure_pct', 'door_interlock', 'track_temp_C'};
        case 'robotics'
            lo_vec = [-100, 0, 0, -127];
            hi_vec = [100, 100, 100, 127];
            names = {'joint_torque_pct', 'speed_pct', 'force_pct', 'position_mm'};
        case 'space'
            lo_vec = [-40, 0, 0, 0];
            hi_vec = [50, 100, 100, 100];
            names = {'temp_C', 'solar_panel_pct', 'propellant_pct', 'battery_pct'};
        case 'underwater'
            lo_vec = [0, 0, -5, 0];
            hi_vec = [100, 100, 35, 100];
            names = {'depth_pct', 'battery_pct', 'water_temp_C', 'thruster_pct'};
        otherwise
            error('Unknown preset: %s. Available: aviation, automotive, medical, nuclear, maritime, energy, railway, robotics, space, underwater', preset_name);
    end
end

% ═══════════════════════════════════════════════════════════════════════
% BATCH CHECK (for MATLAB workspace testing)
% ═══════════════════════════════════════════════════════════════════════

function results = flux_batch_check(values, lo_vec, hi_vec)
%FLUX_BATCH_CHECK Check array of values against constraints
%   Returns struct array with per-value results.

    n = length(values);
    results = struct('error_mask', {}, 'severity', {}, 'passed', {}, ...
                     'violated_count', {}, 'value', {});

    for i = 1:n
        [em, sev, pass, ~, ~, vc] = flux_simulink_check(values(i), lo_vec, hi_vec);
        results(i).error_mask = em;
        results(i).severity = sev;
        results(i).passed = pass;
        results(i).violated_count = vc;
        results(i).value = values(i);
    end
end

% ═══════════════════════════════════════════════════════════════════════
% BENCHMARK
% ═══════════════════════════════════════════════════════════════════════

function bench = flux_benchmark(preset_name, iterations)
%FLUX_BENCHMARK Benchmark FLUX constraint checking in MATLAB/Octave
%   Usage: bench = flux_benchmark('aviation', 1000000)

    if nargin < 2, iterations = 1000000; end

    [lo_vec, hi_vec, ~] = flux_preset(preset_name);
    values = randi([-127, 127], 1, iterations);

    tic;
    for i = 1:iterations
        flux_simulink_check(values(i), lo_vec, hi_vec);
    end
    elapsed = toc;

    nc = length(lo_vec);
    total_checks = iterations * nc;
    rate = total_checks / elapsed;

    bench.preset = preset_name;
    bench.iterations = iterations;
    bench.constraints = nc;
    bench.total_checks = total_checks;
    bench.elapsed_sec = elapsed;
    bench.rate_per_sec = rate;
    bench.rate_M = rate / 1e6;

    fprintf('═══ FLUX Benchmark — MATLAB/Octave ═══\n');
    fprintf('Preset: %s (%d constraints)\n', preset_name, nc);
    fprintf('Iterations: %s\n', num2str(iterations));
    fprintf('Time: %.1f ms\n', elapsed * 1000);
    fprintf('Rate: %.2f M checks/sec\n', bench.rate_M);
end

% ═══════════════════════════════════════════════════════════════════════
% DEMO
% ═══════════════════════════════════════════════════════════════════════

% Only run demo when executed directly (not as library)
% In MATLAB: run('flux_simulink_check.m')
% In Octave: source('flux_simulink_check.m') -- wraps in function, so
%            call flux_demo() directly.

function flux_demo()
    fprintf('═══════════════════════════════════════════════════════\n');
    fprintf('  FLUX Constraint Engine — MATLAB/Simulink\n');
    fprintf('  INT8 saturated constraint checking\n');
    fprintf('═══════════════════════════════════════════════════════\n\n');

    % Load aviation preset
    [lo, hi, names] = flux_preset('aviation');
    fprintf('Aviation preset: %d constraints\n', length(lo));
    for i = 1:length(lo)
        fprintf('  %s: [%d, %d]\n', names{i}, lo(i), hi(i));
    end
    fprintf('\n');

    % Check some values
    test_vals = [-60, 0, 25, 70, 90, 127];
    fprintf('Checking values:\n');
    for v = test_vals
        [em, sev, pass, vlo, vhi, vc] = flux_simulink_check(v, lo, hi);
        sev_name = {'PASS', 'CAUTION', 'WARNING', 'CRITICAL'};
        status = sev_name{sev + 1};
        fprintf('  val=%4d: %s  mask=0x%02X  passed=%d\n', v, status, em, pass);
    end

    % Batch test
    fprintf('\nBatch test (1000 values):\n');
    values = randi([-127, 127], 1, 1000);
    results = flux_batch_check(values, lo, hi);
    n_pass = sum([results.passed]);
    fprintf('  PASS: %d / %d\n', n_pass, length(results));

    % Benchmark
    fprintf('\n');
    bench = flux_benchmark('aviation', 100000);

    % Simulink integration guide
    fprintf('\n═══ Simulink Integration ═══\n');
    fprintf('1. Add this file to your MATLAB path\n');
    fprintf('2. In Simulink: Add "MATLAB Function" block\n');
    fprintf('3. Set function: [mask, sev, pass] = flux_simulink_check(value, lo, hi)\n');
    fprintf('4. Define lo and hi as constants in the model\n');
    fprintf('5. Connect severity output to alarm subsystem\n');
    fprintf('6. Set output data types: mask=uint8, sev=uint8, pass=boolean\n');
end
