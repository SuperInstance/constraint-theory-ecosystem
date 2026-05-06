#!/usr/bin/env bash
source src/shell/flux_constraint.sh

vectors=$(python3 -c "
import json, sys
vectors = json.load(open('tools/golden_vectors.json'))
for v in vectors[:1000]:  # Shell is slow, test first 1000
    constraints = ' '.join(str(c['lo'])+' '+str(c['hi']) for c in v['constraints'])
    print(f\"{v['id']} {v['value']} {v['expected']['error_mask']} {v['expected']['passed']} {constraints}\")
")

mismatches=0
total=0

while IFS=' ' read -r id val exp_mask exp_passed rest; do
    # Build constraint args
    args=($val $rest)
    result=$(flux_check "${args[@]}")
    got_mask=$(echo "$result" | grep 'error_mask=' | cut -d= -f2)
    got_passed=$(echo "$result" | grep 'passed=' | cut -d= -f2)

    if [[ "$got_mask" != "$exp_mask" ]] || { [[ "$exp_passed" == "True" ]] && [[ "$got_passed" != "1" ]]; } || { [[ "$exp_passed" == "False" ]] && [[ "$got_passed" != "0" ]]; }; then
        ((mismatches++))
        if (( mismatches <= 5 )); then
            echo "MISMATCH #$id: val=$val got_mask=$got_mask exp_mask=$exp_mask"
        fi
    fi
    ((total++))
done <<< "$vectors"

echo ""
echo "Shell: $total vectors, $mismatches mismatches"
exit $(( mismatches > 0 ? 1 : 0 ))
