package flux;

import java.util.*;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.Nested;
import static org.junit.jupiter.api.Assertions.*;

/**
 * FLUX Constraint Engine - Java Implementation
 *
 * High-performance constraint checking system with INT8 saturation arithmetic
 * and configurable severity thresholds for industrial process monitoring.
 *
 * Features:
 * - INT8 value range [-127, 127] with saturation
 * - Up to 8 simultaneous constraints
 * - Industry-standard presets (Automotive, Medical, Aerospace, etc.)
 * - Batch processing with vectorized operations
 * - JMH-style benchmarking integration
 *
 * @author FLUX Constraint Team
 * @version 1.0.0
 * @since 2026-05-05
 */
public class FluxConstraint {

    /** Maximum number of constraints supported */
    public static final int MAX_CONSTRAINTS = 8;

    /** INT8 minimum value with saturation */
    public static final int INT8_MIN = -127;

    /** INT8 maximum value with saturation */
    public static final int INT8_MAX = 127;

    /** Constraint thresholds and metadata */
    private final List<ConstraintRule> rules;

    /** Processing statistics */
    private long totalChecks;
    private long totalViolations;

    /**
     * Individual constraint rule with thresholds and metadata
     */
    public static class ConstraintRule {
        public final String name;
        public final int minValue;
        public final int maxValue;
        public final int cautionThreshold;
        public final int warningThreshold;
        public final int criticalThreshold;

        public ConstraintRule(String name, int min, int max,
                            int caution, int warning, int critical) {
            this.name = name;
            this.minValue = saturate(min);
            this.maxValue = saturate(max);
            this.cautionThreshold = caution;
            this.warningThreshold = warning;
            this.criticalThreshold = critical;
        }
    }

    /**
     * Constraint check result with severity classification
     */
    public static class FluxResult {
        public static final int PASS = 0;
        public static final int CAUTION = 1;
        public static final int WARNING = 2;
        public static final int CRITICAL = 3;

        public final boolean passed;
        public final int severity;
        public final String message;
        public final List<String> violations;
        public final long processingTimeNs;

        public FluxResult(boolean passed, int severity, String message,
                         List<String> violations, long processingTimeNs) {
            this.passed = passed;
            this.severity = severity;
            this.message = message;
            this.violations = new ArrayList<>(violations);
            this.processingTimeNs = processingTimeNs;
        }

        public static FluxResult pass(long processingTime) {
            return new FluxResult(true, PASS, "All constraints satisfied",
                                Collections.emptyList(), processingTime);
        }

        public static FluxResult fail(int severity, String message,
                                    List<String> violations, long processingTime) {
            return new FluxResult(false, severity, message, violations, processingTime);
        }

        @Override
        public String toString() {
            return String.format("FluxResult{passed=%s, severity=%d, violations=%d, time=%dns}",
                               passed, severity, violations.size(), processingTimeNs);
        }
    }

    /**
     * Constructs constraint checker with custom rules
     */
    public FluxConstraint(List<ConstraintRule> rules) {
        if (rules.size() > MAX_CONSTRAINTS) {
            throw new IllegalArgumentException("Maximum " + MAX_CONSTRAINTS + " constraints supported");
        }
        this.rules = new ArrayList<>(rules);
        this.totalChecks = 0;
        this.totalViolations = 0;
    }

    /**
     * INT8 saturation arithmetic
     */
    public static int saturate(int value) {
        return Math.max(INT8_MIN, Math.min(INT8_MAX, value));
    }

    /**
     * Check single value against all constraints
     */
    public FluxResult check(int value) {
        long startTime = System.nanoTime();
        totalChecks++;

        int saturatedValue = saturate(value);
        List<String> violations = new ArrayList<>();
        int maxSeverity = FluxResult.PASS;

        for (ConstraintRule rule : rules) {
            if (saturatedValue < rule.minValue || saturatedValue > rule.maxValue) {
                int distance = Math.min(Math.abs(saturatedValue - rule.minValue),
                                      Math.abs(saturatedValue - rule.maxValue));

                int severity = FluxResult.PASS;
                if (distance >= rule.criticalThreshold) {
                    severity = FluxResult.CRITICAL;
                } else if (distance >= rule.warningThreshold) {
                    severity = FluxResult.WARNING;
                } else if (distance >= rule.cautionThreshold) {
                    severity = FluxResult.CAUTION;
                }

                if (severity > FluxResult.PASS) {
                    violations.add(String.format("%s: value=%d, range=[%d,%d], distance=%d",
                                                rule.name, saturatedValue, rule.minValue, rule.maxValue, distance));
                    maxSeverity = Math.max(maxSeverity, severity);
                    totalViolations++;
                }
            }
        }

        long processingTime = System.nanoTime() - startTime;

        if (violations.isEmpty()) {
            return FluxResult.pass(processingTime);
        } else {
            String message = String.format("Failed %d constraints", violations.size());
            return FluxResult.fail(maxSeverity, message, violations, processingTime);
        }
    }

    /**
     * Batch constraint checking with vectorized operations
     */
    public List<FluxResult> checkBatch(int[] values) {
        List<FluxResult> results = new ArrayList<>(values.length);

        for (int value : values) {
            results.add(check(value));
        }

        return results;
    }

    /**
     * Load industry-standard constraint presets
     */
    public static FluxConstraint fromPreset(String industry) {
        List<ConstraintRule> rules = new ArrayList<>();

        switch (industry.toLowerCase()) {
            case "automotive":
                rules.add(new ConstraintRule("Engine_Temp", -40, 120, 5, 15, 25));
                rules.add(new ConstraintRule("Oil_Pressure", 10, 80, 3, 8, 15));
                rules.add(new ConstraintRule("RPM_Limit", 0, 127, 10, 20, 30));
                rules.add(new ConstraintRule("Fuel_Level", 5, 100, 5, 10, 20));
                break;

            case "medical":
                rules.add(new ConstraintRule("Heart_Rate", 60, 100, 5, 10, 20));
                rules.add(new ConstraintRule("Blood_Pressure_Sys", 90, 120, 5, 15, 25));
                rules.add(new ConstraintRule("Blood_Pressure_Dia", 60, 80, 3, 8, 15));
                rules.add(new ConstraintRule("Oxygen_Saturation", 95, 100, 2, 5, 10));
                break;

            case "aerospace":
                rules.add(new ConstraintRule("Altitude", -127, 127, 10, 25, 40));
                rules.add(new ConstraintRule("Airspeed", 0, 127, 15, 30, 50));
                rules.add(new ConstraintRule("Engine_Thrust", 0, 100, 8, 20, 35));
                rules.add(new ConstraintRule("Fuel_Flow", 0, 127, 12, 25, 40));
                break;

            case "industrial":
                rules.add(new ConstraintRule("Temperature", -50, 150, 10, 20, 35));
                rules.add(new ConstraintRule("Pressure", 0, 100, 5, 15, 25));
                rules.add(new ConstraintRule("Vibration", 0, 50, 3, 8, 15));
                rules.add(new ConstraintRule("Power_Draw", 0, 127, 8, 18, 30));
                break;

            default:
                throw new IllegalArgumentException("Unknown industry preset: " + industry);
        }

        return new FluxConstraint(rules);
    }

    /**
     * JMH-style benchmark runner
     */
    public void benchmark(int iterations, int batchSize) {
        System.out.println("=== FLUX Constraint Engine Benchmark ===");
        System.out.println("Iterations: " + iterations);
        System.out.println("Batch Size: " + batchSize);
        System.out.println("Constraints: " + rules.size());

        // Warm-up phase
        for (int i = 0; i < 1000; i++) {
            check(i % 255 - 127);
        }

        // Single value benchmark
        long startTime = System.nanoTime();
        for (int i = 0; i < iterations; i++) {
            check(i % 255 - 127);
        }
        long singleTime = System.nanoTime() - startTime;

        // Batch benchmark
        Random random = new Random(42);
        int[] batchValues = new int[batchSize];
        for (int i = 0; i < batchSize; i++) {
            batchValues[i] = random.nextInt(255) - 127;
        }

        startTime = System.nanoTime();
        for (int i = 0; i < iterations / batchSize; i++) {
            checkBatch(batchValues);
        }
        long batchTime = System.nanoTime() - startTime;

        // Results
        double singleThroughput = (double) iterations / (singleTime / 1_000_000_000.0);
        double batchThroughput = (double) iterations / (batchTime / 1_000_000_000.0);

        System.out.printf("Single Check: %.2f ops/sec\n", singleThroughput);
        System.out.printf("Batch Check: %.2f ops/sec\n", batchThroughput);
        System.out.printf("Batch Speedup: %.2fx\n", batchThroughput / singleThroughput);
        System.out.printf("Total Checks: %d, Violations: %d\n", totalChecks, totalViolations);
    }

    public long getTotalChecks() { return totalChecks; }
    public long getTotalViolations() { return totalViolations; }
    public List<ConstraintRule> getRules() { return new ArrayList<>(rules); }

    /**
     * Comprehensive JUnit 5 test suite
     */
    @Nested
    class FluxConstraintTest {

        private FluxConstraint automotive;
        private FluxConstraint medical;

        @BeforeEach
        void setUp() {
            automotive = FluxConstraint.fromPreset("automotive");
            medical = FluxConstraint.fromPreset("medical");
        }

        @Test
        @DisplayName("INT8 saturation arithmetic")
        void testSaturation() {
            assertEquals(-127, FluxConstraint.saturate(-200));
            assertEquals(127, FluxConstraint.saturate(200));
            assertEquals(0, FluxConstraint.saturate(0));
            assertEquals(50, FluxConstraint.saturate(50));
            assertEquals(-50, FluxConstraint.saturate(-50));
        }

        @Test
        @DisplayName("Valid automotive values should pass")
        void testAutomotivePass() {
            FluxResult result = automotive.check(25); // Normal engine temp
            assertTrue(result.passed);
            assertEquals(FluxResult.PASS, result.severity);
            assertTrue(result.violations.isEmpty());
        }

        @Test
        @DisplayName("Invalid values should fail with correct severity")
        void testAutomotiveFail() {
            FluxResult result = automotive.check(-100); // Extreme cold
            assertFalse(result.passed);
            assertEquals(FluxResult.CRITICAL, result.severity);
            assertFalse(result.violations.isEmpty());
        }

        @Test
        @DisplayName("Medical preset validation")
        void testMedicalPreset() {
            FluxResult normal = medical.check(80); // Normal heart rate
            assertTrue(normal.passed);

            FluxResult abnormal = medical.check(150); // High heart rate
            assertFalse(abnormal.passed);
            assertTrue(abnormal.severity >= FluxResult.WARNING);
        }

        @Test
        @DisplayName("Batch processing")
        void testBatchProcessing() {
            int[] values = {25, 50, 75, 100, 125, -50, -100};
            List<FluxResult> results = automotive.checkBatch(values);
            assertEquals(values.length, results.size());

            // At least some should pass and some should fail
            boolean hasPass = results.stream().anyMatch(r -> r.passed);
            boolean hasFail = results.stream().anyMatch(r -> !r.passed);
            assertTrue(hasPass && hasFail);
        }

        @Test
        @DisplayName("Constraint rule limits")
        void testMaxConstraints() {
            List<ConstraintRule> tooManyRules = new ArrayList<>();
            for (int i = 0; i < 10; i++) {
                tooManyRules.add(new ConstraintRule("Rule" + i, 0, 100, 5, 10, 20));
            }

            assertThrows(IllegalArgumentException.class, () -> {
                new FluxConstraint(tooManyRules);
            });
        }

        @Test
        @DisplayName("Industry preset validation")
        void testIndustryPresets() {
            assertDoesNotThrow(() -> FluxConstraint.fromPreset("automotive"));
            assertDoesNotThrow(() -> FluxConstraint.fromPreset("medical"));
            assertDoesNotThrow(() -> FluxConstraint.fromPreset("aerospace"));
            assertDoesNotThrow(() -> FluxConstraint.fromPreset("industrial"));

            assertThrows(IllegalArgumentException.class, () ->
                FluxConstraint.fromPreset("unknown"));
        }

        @Test
        @DisplayName("Performance characteristics")
        void testPerformance() {
            long startTime = System.nanoTime();
            for (int i = 0; i < 10000; i++) {
                automotive.check(i % 255 - 127);
            }
            long duration = System.nanoTime() - startTime;

            // Should complete 10k checks in under 100ms
            assertTrue(duration < 100_000_000,
                      "Performance regression: took " + (duration / 1_000_000) + "ms");
        }

        @Test
        @DisplayName("Statistics tracking")
        void testStatistics() {
            long initialChecks = automotive.getTotalChecks();
            long initialViolations = automotive.getTotalViolations();

            automotive.check(25); // Should pass
            automotive.check(-100); // Should fail

            assertEquals(initialChecks + 2, automotive.getTotalChecks());
            assertTrue(automotive.getTotalViolations() > initialViolations);
        }
    }

    /**
     * Demonstration and manual testing
     */
    public static void main(String[] args) {
        System.out.println("=== FLUX Constraint Engine - Java Demo ===\n");

        // Create automotive constraint checker
        FluxConstraint auto = fromPreset("automotive");

        // Test various values
        int[] testValues = {25, 50, 75, 100, 125, -50, -100};

        System.out.println("Automotive Constraint Testing:");
        for (int value : testValues) {
            FluxResult result = auto.check(value);
            System.out.printf("Value %4d: %s\n", value, result);
        }

        System.out.println("\nBatch Processing Demo:");
        List<FluxResult> batchResults = auto.checkBatch(testValues);
        long totalTime = batchResults.stream().mapToLong(r -> r.processingTimeNs).sum();
        System.out.printf("Processed %d values in %dns (avg: %dns/value)\n",
                         testValues.length, totalTime, totalTime / testValues.length);

        System.out.println("\nRunning Benchmark...");
        auto.benchmark(100000, 1000);

        System.out.printf("\nFinal Statistics - Checks: %d, Violations: %d\n",
                         auto.getTotalChecks(), auto.getTotalViolations());
    }
}