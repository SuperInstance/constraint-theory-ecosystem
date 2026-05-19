#define FLUX_EXACT_IMPL
// Remove the main from the header
#define FLUX_EXACT_NO_MAIN
#include "flux_constraint_exact.h"
#include <stdio.h>
#include <time.h>

int main() {
    FluxExact fc;
    flux_exact_init(&fc);
    flux_exact_add(&fc, -1000, 45000, "altitude");
    flux_exact_add(&fc, 0, 600, "speed");
    flux_exact_add(&fc, -180, 180, "heading");
    flux_exact_add(&fc, -55, 70, "cabin_temp");
    flux_exact_add(&fc, 75, 101, "pressure");
    flux_exact_add(&fc, 0, 100, "fuel");
    
    printf("Constraints: %d\n", fc.n);
    
    // Hot path benchmark
    int iters = 100000000;
    clock_t t0 = clock();
    volatile uint8_t sink = 0;
    for (int i = 0; i < iters; i++) {
        float val = (float)(i % 50000) - 25000;
        sink |= flux_check_exact(&fc, val);
    }
    clock_t t1 = clock();
    double secs = (double)(t1 - t0) / CLOCKS_PER_SEC;
    double rate = (double)iters / secs;
    printf("C hot path: %.0f checks/sec (%.1fM/s)\n", rate, rate/1e6);
    (void)sink;
    
    // Batch benchmark
    float values[10000];
    for (int i = 0; i < 10000; i++) values[i] = (float)(i % 50000) - 25000;
    uint8_t masks[10000];
    int batch_iters = 100000;
    
    // Scalar batch
    t0 = clock();
    for (int b = 0; b < batch_iters; b++) {
        flux_check_batch(&fc, values, 10000, masks);
    }
    t1 = clock();
    secs = (double)(t1 - t0) / CLOCKS_PER_SEC;
    rate = (double)(batch_iters * 10000) / secs;
    printf("C scalar batch: %.0f checks/sec (%.1fM/s)\n", rate, rate/1e6);
    
    // AVX2 batch
    t0 = clock();
    for (int b = 0; b < batch_iters; b++) {
        flux_check_batch_avx2(&fc, values, 10000, masks);
    }
    t1 = clock();
    secs = (double)(t1 - t0) / CLOCKS_PER_SEC;
    rate = (double)(batch_iters * 10000) / secs;
    printf("C AVX2 batch: %.0f checks/sec (%.1fM/s)\n", rate, rate/1e6);
    
    return 0;
}
