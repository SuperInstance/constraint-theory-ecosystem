//go:build ignore
// +build ignore

package main

import (
	"encoding/json"
	"fmt"
	"os"
)

func saturate(v int) int {
	if v < -127 { return -127 }
	if v > 127 { return 127 }
	return v
}

type Constraint struct { Lo, Hi int }
type Vector struct {
	Id         int
	Value      int
	Constraints []Constraint
	Expected   struct {
		ErrorMask     int `json:"error_mask"`
		ViolatedLo    int `json:"violated_lo"`
		ViolatedHi    int `json:"violated_hi"`
		ViolatedCount int `json:"violated_count"`
		Passed        bool
	}
}

func check(cs []Constraint, value int) (errorMask, violatedLo, violatedHi, violatedCount int, passed bool) {
	v := saturate(value)
	for i, c := range cs {
		lo, hi := saturate(c.Lo), saturate(c.Hi)
		loFail := v < lo
		hiFail := v > hi
		if loFail || hiFail { errorMask |= (1 << i); violatedCount++ }
		if loFail { violatedLo |= (1 << i) }
		if hiFail { violatedHi |= (1 << i) }
	}
	passed = errorMask == 0
	return
}

func main() {
	data, err := os.ReadFile("tools/golden_vectors.json")
	if err != nil { fmt.Println("Error:", err); os.Exit(1) }
	
	var vectors []Vector
	json.Unmarshal(data, &vectors)
	
	mismatches := 0
	for _, v := range vectors {
		em, vlo, vhi, vc, passed := check(v.Constraints, v.Value)
		_ = vlo; _ = vhi
		if em != v.Expected.ErrorMask || passed != v.Expected.Passed || vc != v.Expected.ViolatedCount {
			mismatches++
			if mismatches <= 5 {
				fmt.Printf("MISMATCH #%d: value=%d got mask=%d passed=%v expected mask=%d\n",
					v.Id, v.Value, em, passed, v.Expected.ErrorMask)
			}
		}
	}
	
	fmt.Printf("\nGo: %d vectors, %d mismatches\n", len(vectors), mismatches)
	if mismatches > 0 { os.Exit(1) }
}
