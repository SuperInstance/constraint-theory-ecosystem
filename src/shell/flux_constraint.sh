#!/usr/bin/env bash
# FLUX Constraint Engine — Bash/Shell
# Pure INT8 saturated constraint checking. Zero dependencies.
# (Yes, even bash gets constraint checking. Safety everywhere.)

flux_saturate() {
    local val=$1
    if (( val < -127 )); then echo -127
    elif (( val > 127 )); then echo 127
    else echo "$val"
    fi
}

flux_check() {
    # Usage: flux_check <value> <lo1> <hi1> [lo2 hi2] ... [lo8 hi8]
    local value=$1; shift
    local val=$(flux_saturate "$value")
    local error_mask=0 violated_lo=0 violated_hi=0 violated_count=0
    local i=0

    while (( $# >= 2 )); do
        local lo=$(flux_saturate "$1")
        local hi=$(flux_saturate "$2")
        shift 2

        local lo_fail=0 hi_fail=0
        (( val < lo )) && lo_fail=1
        (( val > hi )) && hi_fail=1

        if (( lo_fail || hi_fail )); then
            error_mask=$(( error_mask | (1 << i) ))
            (( violated_count++ ))
        fi
        (( lo_fail )) && violated_lo=$(( violated_lo | (1 << i) ))
        (( hi_fail )) && violated_hi=$(( violated_hi | (1 << i) ))
        (( i++ ))
    done

    # Output as key=value pairs
    echo "error_mask=$error_mask"
    echo "violated_lo=$violated_lo"
    echo "violated_hi=$violated_hi"
    echo "violated_count=$violated_count"
    echo "passed=$(( violated_count == 0 ))"
}

# Self-test
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "FLUX Constraint Engine — Bash"
    echo "============================="

    [[ $(flux_saturate -128) == -127 ]] || { echo "FAIL: sat(-128)"; exit 1; }
    [[ $(flux_saturate 128) == 127 ]] || { echo "FAIL: sat(128)"; exit 1; }
    echo "  saturate: OK"

    r=$(flux_check 50 0 100)
    [[ "$r" == *"passed=1"* ]] || { echo "FAIL: pass"; exit 1; }

    r=$(flux_check 150 0 100)
    [[ "$r" == *"passed=0"* ]] || { echo "FAIL: fail"; exit 1; }
    echo "  check: OK"

    r=$(flux_check 50 0 10 0 10 0 10 0 10)
    [[ "$r" == *"violated_count=4"* ]] || { echo "FAIL: critical"; exit 1; }
    echo "  severity: OK"

    echo "  All tests pass"
fi
