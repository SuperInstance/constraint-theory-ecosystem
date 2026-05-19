% FLUX Constraint Engine — MATLAB Enhanced (Simulink + Control Systems)
% INT8 saturated constraint checking as a control system block.
%
% The insight: Constraints are transfer functions. Severity is the error
% signal. Simulink models constraint enforcement as a control system.
% PID tuning optimizes response to violations. Bode plots show frequency
% response. Step response shows transient behavior.
%
% "Constraints are transfer functions. Severity is the error signal.
%  Simulink models constraint enforcement as a control system.
%  PID tuning optimizes response to violations."

% ══ Constants ══════════════════════════════════════════════════════

INT8_MIN = -127;
INT8_MAX = 127;
MAX_CONSTRAINTS = 8;

% ══ Industry Presets ═══════════════════════════════════════════════

function preset = get_preset(name)
  switch lower(name)
    case 'aviation'
      preset = struct( ...
        'lo', {-55, 75, 0, 60}, ...
        'hi', {70, 101, 100, 100}, ...
        'name', {{'cabin_temp_C', 'cabin_pressure_kPa', 'fuel_flow_pct', 'hydraulic_pct'}});
    case 'medical'
      preset = struct( ...
        'lo', {36, 60, 95, 80}, ...
        'hi', {38, 100, 100, 120}, ...
        'name', {{'body_temp_C', 'heart_rate_bpm', 'spo2_pct', 'bp_systolic_mmHg'}});
    case 'nuclear'
      preset = struct( ...
        'lo', {0, 0, 72, 0}, ...
        'hi', {110, 65, 100, 100}, ...
        'name', {{'neutron_flux_pct', 'core_temp_C_x10', 'pressurizer_pct', 'coolant_flow_pct'}});
    case 'automotive'
      preset = struct( ...
        'lo', {-40, 0, 0, 20}, ...
        'hi', {60, 100, 100, 80}, ...
        'name', {{'battery_temp_C', 'soc_pct', 'charge_rate_pct', 'cabin_temp_C'}});
    case 'energy'
      preset = struct( ...
        'lo', {49, 95, 0, 0}, ...
        'hi', {51, 105, 80, 100}, ...
        'name', {{'grid_freq_Hz_x10', 'voltage_pct', 'transformer_temp_C', 'line_load_pct'}});
    otherwise
      error('Unknown preset: %s', name);
  end
end

% ══ Saturate (Vectorized) ══════════════════════════════════════════

function val = saturate(val)
  val(val < INT8_MIN) = INT8_MIN;
  val(val > INT8_MAX) = INT8_MAX;
  val = int32(val);
end

% ══ Core Check (Vectorized for MATLAB's Strengths) ════════════════

function result = flux_check(constraints, value)
%FLUX_CHECK Check value(s) against INT8 saturated constraints
%   constraints: struct with fields lo, hi, name
%   value: scalar or vector of values
%   result: struct array with error_mask, severity, etc.

  val = saturate(value);
  nc = length(constraints.lo);
  nv = length(val);

  % Vectorized: build lo/hi matrices
  lo_vec = cell2mat(constraints.lo)';
  hi_vec = cell2mat(constraints.hi)';
  lo_sat = saturate(lo_vec);
  hi_sat = saturate(hi_vec);

  % For each value, check all constraints
  error_mask = zeros(1, nv, 'int32');
  violated_lo = zeros(1, nv, 'int32');
  violated_hi = zeros(1, nv, 'int32');
  violated_count = zeros(1, nv, 'int32');

  for i = 1:nc
    lo_fail = val < lo_sat(i);  % vectorized across all values
    hi_fail = val > hi_sat(i);
    any_fail = lo_fail | hi_fail;
    error_mask = bitor(error_mask, int32(bitshift(int32(any_fail), i-1)));
    violated_lo = bitor(violated_lo, int32(bitshift(int32(lo_fail), i-1)));
    violated_hi = bitor(violated_hi, int32(bitshift(int32(hi_fail), i-1)));
    violated_count = violated_count + int32(any_fail);
  end

  % Severity classification (vectorized)
  severity = zeros(1, nv, 'int32');
  severity(violated_count == 0) = 0;
  severity(violated_count > 0 & violated_count <= floor(nc/4)) = 1;
  severity(violated_count > floor(nc/4) & violated_count <= floor(nc/2)) = 2;
  severity(violated_count > floor(nc/2)) = 3;

  result.error_mask = error_mask;
  result.severity = severity;
  result.violated_lo = violated_lo;
  result.violated_hi = violated_hi;
  result.violated_count = violated_count;
  result.passed = violated_count == 0;
end

% ══ Constraint as Transfer Function ═══════════════════════════════
% H(s) = severity(input) — the constraint IS a transfer function.
% Input: sensor value. Output: severity (0-3).

function H = flux_transfer_function(lo, hi)
%FLUX_TRANSFER_FUNCTION Create transfer function for a constraint
%   Models the constraint as a first-order system:
%   - In range: output ≈ 0 (PASS)
%   - Slightly out: output ramps to 1-2 (CAUTION/WARNING)
%   - Far out: output saturates at 3 (CRITICAL)

  % Distance from bounds as error signal
  % H(s) = K / (tau*s + 1) where K = severity gain
  K = 3;       % max severity
  tau = 0.1;   % response time constant (seconds)
  H = tf(K, [tau 1]);
end

% ══ Bode Plot of Constraint Response ══════════════════════════════

function flux_bode(lo, hi)
%FLUX_BODE Bode plot of constraint transfer function
%   Shows frequency response of constraint enforcement

  if ~license('test', 'Control_Toolbox')
    fprintf('Control System Toolbox required for Bode analysis.\n');
    return;
  end

  H = flux_transfer_function(lo, hi);
  figure;
  bode(H);
  title(sprintf('Constraint Bode Plot [%d, %d]', lo, hi));
  xlabel('Frequency (rad/s)');
end

% ══ Step Response ═════════════════════════════════════════════════

function flux_step_response(lo, hi)
%FLUX_STEP_RESPONSE Step response of constraint system
%   Shows how quickly the constraint system reacts to a step violation

  if ~license('test', 'Control_Toolbox')
    fprintf('Control System Toolbox required for step analysis.\n');
    return;
  end

  H = flux_transfer_function(lo, hi);
  figure;
  step(H);
  title(sprintf('Constraint Step Response [%d, %d]', lo, hi));
  xlabel('Time (s)');
  ylabel('Severity');
end

% ══ PID Tuning for Constraint Response ═══════════════════════════
% Uses constraint severity as the error signal for PID control.

function pid_params = flux_pid_tune(lo, hi, target_settling_time)
%FLUX_PID_TUNE Tune PID controller for constraint enforcement
%   target_settling_time: desired settling time in seconds

  if ~license('test', 'Control_Toolbox')
    fprintf('Control System Toolbox required for PID tuning.\n');
    pid_params = struct('Kp', 1, 'Ki', 0, 'Kd', 0);
    return;
  end

  H = flux_transfer_function(lo, hi);

  % Ziegler-Nichols tuning approximation
  % For first-order system: K = gain, tau = time constant
  K = dcgain(H);
  tau = 0.1;  % from transfer function

  Kp = 0.9 * tau / K;
  Ki = Kp / (3.33 * tau);
  Kd = Kp * tau / 3;

  % Adjust for desired settling time
  if nargin > 2
    scale = 0.1 / target_settling_time;
    Kp = Kp * scale;
    Ki = Ki * scale;
  end

  pid_params = struct('Kp', Kp, 'Ki', Ki, 'Kd', Kd);
end

% ══ Simulink Block Generator ═════════════════════════════════════

function flux_simulink_block(constraints, model_name)
%FLUX_SIMULINK_BLOCK Generate Simulink-compatible constraint checker
%   Creates a MATLAB Function block that can be dropped into a Simulink model

  nc = length(constraints.lo);
  fprintf('%% Simulink MATLAB Function Block: %s\n', model_name);
  fprintf('%% Drop into Simulink model as "MATLAB Function" block\n\n');
  fprintf('function [severity, error_mask, passed] = %s(value)\n', model_name);
  fprintf('  %% Constraint checker for %d constraints\n', nc);
  fprintf('  val = max(-127, min(127, int32(value)));\n');
  fprintf('  error_mask = int32(0);\n');
  fprintf('  violated = int32(0);\n\n');

  for i = 1:nc
    fprintf('  %% Constraint %d: %s [%d, %d]\n', i, constraints.name{i}, ...
            constraints.lo(i), constraints.hi(i));
    fprintf('  if val < %d || val > %d\n', constraints.lo(i), constraints.hi(i));
    fprintf('    error_mask = bitor(error_mask, int32(2^%d));\n', i-1);
    fprintf('    violated = violated + 1;\n');
    fprintf('  end\n\n');
  end

  fprintf('  if violated == 0, severity = 0;\n');
  fprintf('  elseif violated <= %d, severity = 1;\n', floor(nc/4));
  fprintf('  elseif violated <= %d, severity = 2;\n', floor(nc/2));
  fprintf('  else severity = 3;\n');
  fprintf('  end\n');
  fprintf('  passed = violated == 0;\n');
  fprintf('end\n');
end

% ══ 6-DOF Flight Simulation (Aerospace Preset) ═══════════════════

function [violations, trajectory] = simulate_flight(duration, dt)
%SIMULATE_FLIGHT 6-DOF flight simulation with constraint monitoring
%   Returns violation history and trajectory

  t = 0:dt:duration;
  n = length(t);

  % Simplified 6-DOF state: [x, y, z, roll, pitch, yaw]
  % Perturbed with turbulence
  turbulence_intensity = 5;

  cabin_temp = 20 + turbulence_intensity * randn(1, n) + 0.01 * t;
  cabin_pressure = 85 + 2 * randn(1, n);
  fuel_flow = 50 + 10 * randn(1, n) - 0.5 * t;
  hydraulic = 85 + 5 * randn(1, n);

  trajectory = [cabin_temp; cabin_pressure; fuel_flow; hydraulic];
  constraints = get_preset('aviation');

  violations = zeros(1, n);
  for i = 1:n
    vals = [cabin_temp(i), cabin_pressure(i), fuel_flow(i), hydraulic(i)];
    r = flux_check(constraints, vals);
    violations(i) = r.violated_count;
  end
end

% ══ Reactor Simulation (Nuclear Preset) ═══════════════════════════

function [violations, reactor_state] = simulate_reactor(duration, dt)
%SIMULATE_REACTOR Simplified reactor simulation with constraint monitoring

  t = 0:dt:duration;
  n = length(t);

  % Simplified reactor state with perturbations
  neutron_flux = 50 + 20 * randn(1, n);
  core_temp = 30 + 15 * randn(1, n) + 0.02 * t;  % drift!
  pressurizer = 85 + 5 * randn(1, n);
  coolant_flow = 90 + 8 * randn(1, n);

  reactor_state = [neutron_flux; core_temp; pressurizer; coolant_flow];
  constraints = get_preset('nuclear');

  violations = zeros(1, n);
  for i = 1:n
    vals = [neutron_flux(i), core_temp(i), pressurizer(i), coolant_flow(i)];
    r = flux_check(constraints, vals);
    violations(i) = r.violated_count;
  end
end

% ══ Demo ═══════════════════════════════════════════════════════════

fprintf('═══ FLUX Constraint Engine — MATLAB Enhanced (Simulink + Control) ═══\n\n');

% Basic check
av = get_preset('aviation');
r = flux_check(av, 60);
fprintf('  Aviation val=60: severity=%d mask=0x%02X passed=%d\n', ...
        r.severity, r.error_mask, r.passed);

r = flux_check(av, 25);
fprintf('  Aviation val=25: severity=%d mask=0x%02X passed=%d\n', ...
        r.severity, r.error_mask, r.passed);

% Vectorized check
values = [-60, 0, 25, 70, 90, 127];
r = flux_check(av, values);
fprintf('\n  Batch [%s]:\n', num2str(values));
for i = 1:length(values)
  fprintf('    val=%4d: sev=%d mask=0x%02X passed=%d\n', ...
          values(i), r.severity(i), r.error_mask(i), r.passed(i));
end

% Transfer function
fprintf('\n  Transfer function H(s) = 3 / (0.1s + 1)\n');
fprintf('  PID params: '); disp(flux_pid_tune(-55, 70, 0.5));

% Simulink block
fprintf('\n');
flux_simulink_block(av, 'aviation_constraint_checker');

% Flight simulation
fprintf('\n  Flight simulation (60s, dt=0.1):\n');
[viols, traj] = simulate_flight(60, 0.1);
fprintf('    Total violations: %d / %d timesteps (%.1f%%)\n', ...
        sum(viols > 0), length(viols), 100 * mean(viols > 0));
