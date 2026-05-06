% FLUX Constraint Engine — MATLAB/Octave
% Pure INT8 saturated constraint checking. Zero dependencies.

function r = flux_check(constraints, value)
%FLUX_CHECK Check value against INT8 saturated constraints
%   constraints: Nx2 matrix [lo, hi]
%   value: scalar integer
%   r: struct with error_mask, severity, violated_count, passed

    val = saturate(value);
    nc = size(constraints, 1);
    error_mask = 0;
    violated_lo = 0;
    violated_hi = 0;
    violated_count = 0;

    for i = 1:nc
        lo = saturate(constraints(i, 1));
        hi = saturate(constraints(i, 2));
        lo_fail = val < lo;
        hi_fail = val > hi;

        if lo_fail || hi_fail
            error_mask = bitor(error_mask, bitshift(1, i-1));
            violated_count = violated_count + 1;
        end
        if lo_fail, violated_lo = bitor(violated_lo, bitshift(1, i-1)); end
        if hi_fail, violated_hi = bitor(violated_hi, bitshift(1, i-1)); end
    end

    if violated_count == 0, severity = 0;
    elseif violated_count <= floor(nc/4), severity = 1;
    elseif violated_count <= floor(nc/2), severity = 2;
    else severity = 3;
    end

    r.error_mask = error_mask;
    r.severity = severity;
    r.violated_lo = violated_lo;
    r.violated_hi = violated_hi;
    r.violated_count = violated_count;
    r.passed = (violated_count == 0);
end

function v = saturate(val)
    v = max(-127, min(127, round(val)));
end
