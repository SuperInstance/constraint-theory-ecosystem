using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;

namespace Flux
{
    public enum Severity { Pass = 0, Caution = 1, Warning = 2, Critical = 3 }

    public class ConstraintDef
    {
        public int Lo { get; set; }
        public int Hi { get; set; }
        public string Name { get; set; }

        public ConstraintDef(int lo, int hi, string name)
        {
            Lo = Saturate(lo);
            Hi = Saturate(hi);
            Name = name;
        }
    }

    public class FluxResult
    {
        public int ErrorMask { get; set; }
        public Severity Severity { get; set; }
        public int ViolatedLo { get; set; }
        public int ViolatedHi { get; set; }
        public int ViolatedCount { get; set; }
        public bool Passed => Severity == Severity.Pass;
        public List<(string Name, int Lo, int Hi, bool Passed)> Details { get; set; } = new();
    }

    public class FluxChecker
    {
        private readonly List<ConstraintDef> _constraints;

        public FluxChecker(List<ConstraintDef> constraints)
        {
            if (constraints == null || constraints.Count == 0)
                throw new ArgumentException("Non-empty constraints required");
            if (constraints.Count > 8)
                throw new ArgumentException("Max 8 constraints (INT8 × 8 flat bounds)");
            _constraints = constraints;
        }

        public FluxResult Check(int value)
        {
            int val = Saturate(value);
            var result = new FluxResult();
            int violated = 0;

            for (int i = 0; i < _constraints.Count; i++)
            {
                var c = _constraints[i];
                bool loFail = val < c.Lo;
                bool hiFail = val > c.Hi;
                bool passed = !loFail && !hiFail;

                if (!passed) { result.ErrorMask |= (1 << i); violated++; }
                if (loFail) result.ViolatedLo |= (1 << i);
                if (hiFail) result.ViolatedHi |= (1 << i);

                result.Details.Add((c.Name, c.Lo, c.Hi, passed));
            }

            int nc = _constraints.Count;
            result.ViolatedCount = violated;
            result.Severity = violated == 0 ? Severity.Pass
                : violated <= nc / 4 ? Severity.Caution
                : violated <= nc / 2 ? Severity.Warning
                : Severity.Critical;

            return result;
        }

        public (List<FluxResult> Results, Dictionary<string, int> Stats) CheckBatch(IEnumerable<int> values)
        {
            var results = new List<FluxResult>();
            var stats = new Dictionary<string, int>
            {
                ["pass"] = 0, ["caution"] = 0, ["warning"] = 0, ["critical"] = 0
            };

            foreach (var v in values)
            {
                var r = Check(v);
                results.Add(r);
                stats[r.Severity.ToString().ToLower()]++;
            }
            return (results, stats);
        }

        public (double Rate, double Ms) Benchmark(int iterations = 1_000_000)
        {
            var sw = Stopwatch.StartNew();
            for (int i = 0; i < iterations; i++)
                Check((i % 254) - 127);
            sw.Stop();
            double rate = iterations * _constraints.Count / (sw.Elapsed.TotalMilliseconds / 1000.0);
            return (rate, sw.Elapsed.TotalMilliseconds);
        }

        public static FluxChecker FromPreset(string name)
        {
            if (!Presets.ContainsKey(name))
                throw new ArgumentException($"Unknown preset: {name}. Available: {string.Join(", ", Presets.Keys)}");
            return new FluxChecker(Presets[name]);
        }

        public static int Saturate(int val) => Math.Max(-127, Math.Min(127, val));

        public static readonly Dictionary<string, List<ConstraintDef>> Presets = new()
        {
            ["aviation"] = new()
            {
                new(-55, 70, "cabin_temp_C"),
                new(75, 101, "cabin_pressure_kPa"),
                new(0, 100, "fuel_flow_pct"),
                new(60, 100, "hydraulic_pct")
            },
            ["medical"] = new()
            {
                new(36, 38, "body_temp_C"),
                new(60, 100, "heart_rate_bpm"),
                new(95, 100, "spo2_pct"),
                new(80, 120, "bp_systolic_mmHg")
            },
            ["maritime"] = new()
            {
                new(-2, 35, "sea_temp_C"),
                new(50, 100, "hull_integrity_pct"),
                new(0, 50, "wave_height_m"),
                new(0, 80, "wind_speed_kn")
            },
            ["automotive"] = new()
            {
                new(-40, 60, "battery_temp_C"),
                new(0, 100, "soc_pct"),
                new(0, 100, "charge_rate_pct"),
                new(20, 80, "cabin_temp_C")
            },
            ["energy"] = new()
            {
                new(49, 51, "grid_freq_Hz_x10"),
                new(95, 105, "voltage_pct"),
                new(0, 80, "transformer_temp_C"),
                new(0, 100, "line_load_pct")
            }
        };
    }

    // Tests
    public static class FluxTests
    {
        public static void RunAll()
        {
            Console.WriteLine("╔══════════════════════════════════════════════════════╗");
            Console.WriteLine("║  FLUX Constraint Engine — C#                         ║");
            Console.WriteLine("╚══════════════════════════════════════════════════════╝\n");

            // Test 1: Saturate
            Assert(FluxChecker.Saturate(-128) == -127, "saturate(-128)");
            Assert(FluxChecker.Saturate(128) == 127, "saturate(128)");
            Assert(FluxChecker.Saturate(0) == 0, "saturate(0)");
            Console.WriteLine("✓ saturate boundaries");

            // Test 2: Pass
            var fc = new FluxChecker(new List<ConstraintDef> { new(0, 100, "test") });
            var r1 = fc.Check(50);
            Assert(r1.Passed, "should pass");
            Console.WriteLine("✓ single constraint pass");

            // Test 3: Fail
            var r2 = fc.Check(150);
            Assert(!r2.Passed, "should fail");
            Assert(r2.ErrorMask != 0, "should have error");
            Console.WriteLine("✓ single constraint fail");

            // Test 4: Multi
            var fc2 = new FluxChecker(new List<ConstraintDef>
            {
                new(0, 50, "a"), new(0, 100, "b"), new(-10, 10, "c")
            });
            var r3 = fc2.Check(30);
            Assert(!r3.Passed, "should fail");
            Console.WriteLine("✓ multi constraint mixed");

            // Test 5: Severity
            var fc3 = new FluxChecker(new List<ConstraintDef>
            {
                new(0, 10, "a"), new(0, 10, "b"), new(0, 10, "c"), new(0, 10, "d")
            });
            var r4 = fc3.Check(50);
            Assert(r4.Severity == Severity.Critical, "should be critical");
            Assert(r4.ViolatedCount == 4, "all 4 should fail");
            Console.WriteLine("✓ severity critical");

            // Test 6: Preset
            var fc4 = FluxChecker.FromPreset("aviation");
            Assert(fc4._constraints.Count == 4, "aviation should have 4");
            Console.WriteLine("✓ preset loading");

            // Test 7: Batch
            var (results, stats) = fc.CheckBatch(new[] { -60, 0, 50, 100, 127 });
            Assert(results.Count == 5, "should have 5 results");
            Console.WriteLine("✓ batch checking");

            // Benchmark
            var (rate, ms) = fc4.Benchmark();
            Console.WriteLine($"\n  Benchmark: {rate / 1e6:F1}M checks/sec ({ms:F1}ms)");
            Console.WriteLine("\n  ✓ All tests pass");
        }

        static void Assert(bool condition, string msg)
        {
            if (!condition) throw new Exception($"FAIL: {msg}");
        }
    }
}
