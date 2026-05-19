package main

import (
	"fmt"
	"time"
)

func saturate(val int) int8 {
	if val < -127 {
		return -127
	}
	if val > 127 {
		return 127
	}
	return int8(val)
}

type constraint struct{ lo, hi int8 }

func main() {
	cs := [4]constraint{{-55, 70}, {75, 101}, {0, 100}, {60, 100}}
	iters := 10_000_000
	var accumulator uint64 = 0
	t0 := time.Now()

	for i := 0; i < iters; i++ {
		val := saturate((i % 254) - 127)
		var m uint8 = 0
		for j := 0; j < 4; j++ {
			if val < cs[j].lo || val > cs[j].hi {
				m |= 1 << j
			}
		}
		accumulator += uint64(m)
	}

	elapsed := time.Since(t0)
	if accumulator == 0xDEADBEEF {
		fmt.Print(accumulator)
	}
	sec := elapsed.Seconds()
	rate := float64(iters*4) / sec
	fmt.Printf("%.0f %.1f %d\n", rate, sec*1000, iters)
}
