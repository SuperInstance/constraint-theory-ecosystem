// FLUX Constraint Engine — C++17
// Pure INT8 saturated constraint checking. Zero dependencies.
// Header-only, constexpr-friendly, <algorithm>-free.

#pragma once

#include <cstdint>
#include <vector>
#include <string>
#include <chrono>
#include <stdexcept>

namespace flux {

constexpr int8_t INT8_MIN_VAL = -127;
constexpr int8_t INT8_MAX_VAL = 127;

constexpr int saturate(int val) noexcept {
    return val < -127 ? -127 : (val > 127 ? 127 : val);
}

enum class Severity : uint8_t { Pass = 0, Caution = 1, Warning = 2, Critical = 3 };

struct Constraint {
    int lo;
    int hi;
    std::string name;
};

struct FluxResult {
    int error_mask = 0;
    Severity severity = Severity::Pass;
    int violated_lo = 0;
    int violated_hi = 0;
    int violated_count = 0;
    bool passed = true;
};

class FluxChecker {
    std::vector<Constraint> constraints_;

public:
    explicit FluxChecker(std::vector<Constraint> constraints)
        : constraints_(std::move(constraints)) {
        if (constraints_.empty())
            throw std::invalid_argument("Non-empty constraints required");
        if (constraints_.size() > 8)
            throw std::invalid_argument("Max 8 constraints");
    }

    FluxResult check(int value) const noexcept {
        const int val = saturate(value);
        FluxResult r;
        int vc = 0;

        for (size_t i = 0; i < constraints_.size(); ++i) {
            const int lo = saturate(constraints_[i].lo);
            const int hi = saturate(constraints_[i].hi);
            const bool lo_fail = val < lo;
            const bool hi_fail = val > hi;
            const int bit = 1 << static_cast<int>(i);

            if (lo_fail || hi_fail) { r.error_mask |= bit; ++vc; }
            if (lo_fail) r.violated_lo |= bit;
            if (hi_fail) r.violated_hi |= bit;
        }

        r.violated_count = vc;
        const auto nc = static_cast<int>(constraints_.size());
        r.severity = vc == 0 ? Severity::Pass
                   : vc <= nc/4 ? Severity::Caution
                   : vc <= nc/2 ? Severity::Warning
                   : Severity::Critical;
        r.passed = (r.severity == Severity::Pass);
        return r;
    }

    std::vector<FluxResult> check_batch(const std::vector<int>& values) const {
        std::vector<FluxResult> results;
        results.reserve(values.size());
        for (int v : values) results.push_back(check(v));
        return results;
    }

    double benchmark(int iterations = 1'000'000) const {
        auto t0 = std::chrono::high_resolution_clock::now();
        for (int i = 0; i < iterations; ++i)
            check((i % 254) - 127);
        auto t1 = std::chrono::high_resolution_clock::now();
        double sec = std::chrono::duration<double>(t1 - t0).count();
        return iterations * constraints_.size() / sec;
    }

    static FluxChecker from_preset(const std::string& name) {
        std::vector<Constraint> cs;
        if (name == "aviation") {
            cs = {{-55,70,"cabin_temp_C"},{75,101,"cabin_pressure_kPa"},
                  {0,100,"fuel_flow_pct"},{60,100,"hydraulic_pct"}};
        } else if (name == "medical") {
            cs = {{36,38,"body_temp_C"},{60,100,"heart_rate_bpm"},
                  {95,100,"spo2_pct"},{80,120,"bp_systolic_mmHg"}};
        } else if (name == "automotive") {
            cs = {{-40,60,"battery_temp_C"},{0,100,"soc_pct"},
                  {0,100,"charge_rate_pct"},{20,80,"cabin_temp_C"}};
        } else if (name == "energy") {
            cs = {{49,51,"grid_freq_Hz_x10"},{95,105,"voltage_pct"},
                  {0,80,"transformer_temp_C"},{0,100,"line_load_pct"}};
        } else {
            throw std::invalid_argument("Unknown preset: " + name);
        }
        return FluxChecker(std::move(cs));
    }
};

} // namespace flux

// Self-test
#ifdef FLUX_MAIN
#include <iostream>
#include <cassert>
int main() {
    std::cout << "FLUX Constraint Engine — C++17\n";
    std::cout << "==============================\n";

    assert(flux::saturate(-128) == -127);
    assert(flux::saturate(128) == 127);
    std::cout << "  saturate: OK\n";

    flux::FluxChecker fc({{0, 100, "test"}});
    assert(fc.check(50).passed);
    assert(!fc.check(150).passed);
    std::cout << "  check: OK\n";

    flux::FluxChecker fc2({{0,10,"a"},{0,10,"b"},{0,10,"c"},{0,10,"d"}});
    auto r = fc2.check(50);
    assert(r.severity == flux::Severity::Critical && r.violated_count == 4);
    std::cout << "  severity: OK\n";

    auto fc3 = flux::FluxChecker::from_preset("aviation");
    assert(fc3.check(25).passed);
    std::cout << "  presets: OK\n";

    double rate = fc3.benchmark();
    printf("  Benchmark: %.1fM checks/sec\n", rate / 1e6);
    std::cout << "  All tests pass\n";
}
#endif
