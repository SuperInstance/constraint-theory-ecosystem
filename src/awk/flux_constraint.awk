# FLUX Constraint Engine — AWK (1977, Data-Driven / Pattern-Action)
# Pure INT8 saturated constraint checking. Zero dependencies.
#
# The insight: constraints as stream processing. AWK reads a value,
# pattern-matches it against rules, and emits results. The data flow
# IS the constraint check. No functions needed — pattern-action pairs
# ARE the logic. Every line of input is a check. Every rule is a constraint.
#
# Usage:
#   echo "60" | awk -f flux_constraint.awk
#   echo -e "aviation\n60" | awk -f flux_constraint.awk
#   seq -60 5 127 | awk -f flux_constraint.awk          # batch
#   cat sensor_data.txt | awk -f flux_constraint.awk     # stream

# ══ Constants ═══════════════════════════════════════════════════════

BEGIN {
    INT8_MIN = -127
    INT8_MAX = 127
    MAX_C = 8

    # Default preset: automotive
    split("-40,60,battery_temp_C,0,100,soc_pct,0,100,charge_rate_pct,20,80,cabin_temp_C", default_a, ",")
    n_constraints = 0
    for (i = 1; i <= length(default_a); i += 3) {
        c_lo[n_constraints] = int(default_a[i])
        c_hi[n_constraints] = int(default_a[i+1])
        c_name[n_constraints] = default_a[i+2]
        n_constraints++
    }

    # Track state
    total_checks = 0
    total_pass = 0
    total_caution = 0
    total_warning = 0
    total_critical = 0
}

# ══ Saturate function ══════════════════════════════════════════════

function saturate(val) {
    if (val < INT8_MIN) return INT8_MIN
    if (val > INT8_MAX) return INT8_MAX
    return int(val)
}

# ══ Severity from violation count ══════════════════════════════════

function severity_name(vc, n) {
    if (vc == 0) return "PASS"
    if (vc <= int(n / 4)) return "CAUTION"
    if (vc <= int(n / 2)) return "WARNING"
    return "CRITICAL"
}

# ══ Load preset by name ═══════════════════════════════════════════

function load_preset(name) {
    n_constraints = 0

    if (name == "aviation") {
        split("-55,70,cabin_temp_C,75,101,cabin_pressure_kPa,0,100,fuel_flow_pct,60,100,hydraulic_pct", a, ",")
    } else if (name == "automotive") {
        split("-40,60,battery_temp_C,0,100,soc_pct,0,100,charge_rate_pct,20,80,cabin_temp_C", a, ",")
    } else if (name == "maritime") {
        split("-2,35,sea_temp_C,50,100,hull_integrity_pct,0,50,wave_height_m,0,80,wind_speed_kn", a, ",")
    } else if (name == "medical") {
        split("36,38,body_temp_C,60,100,heart_rate_bpm,95,100,spo2_pct,80,120,bp_systolic_mmHg", a, ",")
    } else if (name == "energy") {
        split("49,51,grid_freq_Hz_x10,95,105,voltage_pct,0,80,transformer_temp_C,0,100,line_load_pct", a, ",")
    } else if (name == "nuclear") {
        split("0,110,neutron_flux_pct,0,65,core_temp_C_x10,72,100,pressurizer_pct,0,100,coolant_flow_pct", a, ",")
    } else if (name == "railway") {
        split("0,100,speed_pct,0,100,brake_pressure_pct,0,1,door_interlock,0,80,track_temp_C", a, ",")
    } else if (name == "robotics") {
        split("-100,100,joint_torque_pct,0,100,speed_pct,0,100,force_pct,-127,127,position_mm", a, ",")
    } else if (name == "space") {
        split("-40,50,temp_C,0,100,solar_panel_pct,0,100,propellant_pct,0,100,battery_pct", a, ",")
    } else if (name == "underwater") {
        split("0,100,depth_pct,0,100,battery_pct,-5,35,water_temp_C,0,100,thruster_pct", a, ",")
    } else {
        return 0
    }

    for (i = 1; i <= length(a); i += 3) {
        c_lo[n_constraints] = int(a[i])
        c_hi[n_constraints] = int(a[i+1])
        c_name[n_constraints] = a[i+2]
        n_constraints++
    }
    return 1
}

# ══ Check function ════════════════════════════════════════════════

function check_value(raw,    val, em, vlo, vhi, vc, i, lo_f, hi_f, sev) {
    val = saturate(raw)
    em = 0; vlo = 0; vhi = 0; vc = 0

    for (i = 0; i < n_constraints; i++) {
        lo_f = (val < c_lo[i]) ? 1 : 0
        hi_f = (val > c_hi[i]) ? 1 : 0

        if (lo_f || hi_f) {
            em = or(em, lshift(1, i))
            vc++
        }
        if (lo_f) vlo = or(vlo, lshift(1, i))
        if (hi_f) vhi = or(vhi, lshift(1, i))
    }

    sev = severity_name(vc, n_constraints)
    total_checks++

    if (sev == "PASS") total_pass++
    else if (sev == "CAUTION") total_caution++
    else if (sev == "WARNING") total_warning++
    else total_critical++

    printf "val=%4d → %s mask=0x%02X lo=0x%02X hi=0x%02X count=%d\n", val, sev, em, vlo, vhi, vc
}

# ══ Pattern-action rules — the AWK way ════════════════════════════

# Load preset (lines starting with preset name)
$0 ~ /^(aviation|automotive|maritime|medical|energy|nuclear|railway|robotics|space|underwater)$/ {
    if (load_preset($0)) {
        printf " Loaded preset: %s (%d constraints)\n", $0, n_constraints
        for (i = 0; i < n_constraints; i++) {
            printf "   %s [%d, %d]\n", c_name[i], c_lo[i], c_hi[i]
        }
    }
    next
}

# Numeric values get checked
$0 ~ /^-?[0-9]+$/ {
    check_value(int($0))
    next
}

# Summary on end of input
END {
    if (total_checks > 0) {
        printf "\n═══ Summary: %d checks ═══\n", total_checks
        printf "  PASS:     %d\n", total_pass
        printf "  CAUTION:  %d\n", total_caution
        printf "  WARNING:  %d\n", total_warning
        printf "  CRITICAL: %d\n", total_critical
    }
}

# ══ AWK's gift to constraint theory ═══════════════════════════════
#
# "Data-driven constraint checking. Every line of input is a check.
#  Every pattern-action rule is a constraint. The stream IS the engine.
#  AWK was doing event-driven architecture in 1977."
#
# Example sessions:
#
#   $ echo -e "aviation\n-60\n0\n25\n70\n127" | awk -f flux_constraint.awk
#   $ cat /dev/ttyS0 | awk -f flux_constraint.awk    # live serial stream
#   $ tail -f /var/log/sensors.log | awk -f flux_constraint.awk  # live monitoring
