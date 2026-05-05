<?php

declare(strict_types=1);

/**
 * FLUX Constraint Checking for PHP
 *
 * Pure PHP implementation of INT8 saturated constraint checking
 * following the FLUX constraint theory ecosystem standards.
 *
 * @package FluxConstraint
 * @version 1.0.0
 * @author FLUX Constraint Theory Ecosystem
 */

/**
 * Represents the result of a constraint check operation
 */
class FluxResult
{
    /** No violations - all constraints pass */
    public const PASS = 0;
    /** Minor violations that warrant attention */
    public const CAUTION = 1;
    /** Significant violations requiring action */
    public const WARNING = 2;
    /** Critical violations requiring immediate action */
    public const CRITICAL = 3;

    /**
     * @param int $error_mask Bitmask of violated constraints
     * @param int $severity Maximum severity level (0-3)
     * @param int $violated_lo Number of lower bound violations
     * @param int $violated_hi Number of upper bound violations
     * @param array<string, array{passed: bool, severity: int, value: int, lo: int, hi: int}> $constraint_results
     */
    public function __construct(
        public readonly int $error_mask,
        public readonly int $severity,
        public readonly int $violated_lo,
        public readonly int $violated_hi,
        public readonly array $constraint_results
    ) {}

    /**
     * Check if all constraints passed
     */
    public function isPassing(): bool
    {
        return $this->error_mask === 0;
    }

    /**
     * Check if result indicates critical failure
     */
    public function isCritical(): bool
    {
        return $this->severity >= self::CRITICAL;
    }

    /**
     * Get human-readable severity description
     */
    public function getSeverityName(): string
    {
        return match ($this->severity) {
            self::PASS => 'PASS',
            self::CAUTION => 'CAUTION',
            self::WARNING => 'WARNING',
            self::CRITICAL => 'CRITICAL',
            default => 'UNKNOWN'
        };
    }
}

/**
 * FLUX constraint checker for INT8 saturated arithmetic
 *
 * Implements constraint checking with saturated arithmetic where all values
 * are clamped to the INT8 range [-127, 127] before processing.
 */
class FluxConstraint
{
    /** Minimum INT8 value */
    public const INT8_MIN = -127;
    /** Maximum INT8 value */
    public const INT8_MAX = 127;

    /**
     * @var array<array{lo: int, hi: int, name: string, severity: int}> $constraints
     */
    private array $constraints;

    /**
     * Create a new constraint checker
     *
     * @param array<array{lo: int, hi: int, name: string, severity?: int}> $constraints
     *        Array of constraints, each with 'lo', 'hi', 'name', and optional 'severity'
     */
    public function __construct(array $constraints)
    {
        $this->constraints = [];
        foreach ($constraints as $constraint) {
            if (!isset($constraint['lo'], $constraint['hi'], $constraint['name'])) {
                throw new InvalidArgumentException('Each constraint must have lo, hi, and name');
            }

            $this->constraints[] = [
                'lo' => self::saturate((int) $constraint['lo']),
                'hi' => self::saturate((int) $constraint['hi']),
                'name' => (string) $constraint['name'],
                'severity' => (int) ($constraint['severity'] ?? FluxResult::WARNING)
            ];
        }
    }

    /**
     * Saturate a value to INT8 range [-127, 127]
     *
     * @param int $val Value to saturate
     * @return int Saturated value
     */
    public static function saturate(int $val): int
    {
        if ($val < self::INT8_MIN) {
            return self::INT8_MIN;
        }
        if ($val > self::INT8_MAX) {
            return self::INT8_MAX;
        }
        return $val;
    }

    /**
     * Check a single value against all constraints
     *
     * @param int $value Value to check (will be saturated)
     * @return FluxResult Check results
     */
    public function check(int $value): FluxResult
    {
        $saturated_value = self::saturate($value);
        $error_mask = 0;
        $max_severity = FluxResult::PASS;
        $violated_lo = 0;
        $violated_hi = 0;
        $constraint_results = [];

        foreach ($this->constraints as $i => $constraint) {
            $passed = $saturated_value >= $constraint['lo'] && $saturated_value <= $constraint['hi'];

            if (!$passed) {
                $error_mask |= (1 << $i);
                if ($saturated_value < $constraint['lo']) {
                    $violated_lo++;
                }
                if ($saturated_value > $constraint['hi']) {
                    $violated_hi++;
                }
                $max_severity = max($max_severity, $constraint['severity']);
            }

            $constraint_results[$constraint['name']] = [
                'passed' => $passed,
                'severity' => $constraint['severity'],
                'value' => $saturated_value,
                'lo' => $constraint['lo'],
                'hi' => $constraint['hi']
            ];
        }

        return new FluxResult(
            $error_mask,
            $max_severity,
            $violated_lo,
            $violated_hi,
            $constraint_results
        );
    }

    /**
     * Check multiple values against all constraints
     *
     * @param array<int> $values Values to check
     * @return array<FluxResult> Results for each value
     */
    public function checkBatch(array $values): array
    {
        $results = [];
        foreach ($values as $value) {
            $results[] = $this->check($value);
        }
        return $results;
    }

    /**
     * Create constraint checker with industry-standard presets
     *
     * @param string $name Industry preset name
     * @return self New constraint checker
     * @throws InvalidArgumentException If preset name is unknown
     */
    public static function fromIndustry(string $name): self
    {
        $presets = [
            'aviation' => [
                ['lo' => -50, 'hi' => 50, 'name' => 'altitude_deviation', 'severity' => FluxResult::CRITICAL],
                ['lo' => -20, 'hi' => 20, 'name' => 'heading_deviation', 'severity' => FluxResult::WARNING],
                ['lo' => -10, 'hi' => 10, 'name' => 'speed_deviation', 'severity' => FluxResult::WARNING]
            ],
            'medical' => [
                ['lo' => 60, 'hi' => 100, 'name' => 'heart_rate_bpm', 'severity' => FluxResult::CRITICAL],
                ['lo' => 90, 'hi' => 120, 'name' => 'systolic_bp', 'severity' => FluxResult::WARNING],
                ['lo' => 60, 'hi' => 80, 'name' => 'diastolic_bp', 'severity' => FluxResult::WARNING]
            ],
            'maritime' => [
                ['lo' => -30, 'hi' => 30, 'name' => 'course_deviation', 'severity' => FluxResult::WARNING],
                ['lo' => 0, 'hi' => 50, 'name' => 'wind_speed_knots', 'severity' => FluxResult::CAUTION],
                ['lo' => -10, 'hi' => 10, 'name' => 'depth_variance', 'severity' => FluxResult::CRITICAL]
            ],
            'automotive' => [
                ['lo' => -5, 'hi' => 5, 'name' => 'steering_angle', 'severity' => FluxResult::WARNING],
                ['lo' => 0, 'hi' => 80, 'name' => 'engine_temp_c', 'severity' => FluxResult::CRITICAL],
                ['lo' => 0, 'hi' => 120, 'name' => 'speed_kmh', 'severity' => FluxResult::WARNING]
            ],
            'industrial' => [
                ['lo' => 18, 'hi' => 25, 'name' => 'temperature_c', 'severity' => FluxResult::WARNING],
                ['lo' => 30, 'hi' => 70, 'name' => 'humidity_percent', 'severity' => FluxResult::CAUTION],
                ['lo' => -100, 'hi' => 100, 'name' => 'pressure_diff', 'severity' => FluxResult::CRITICAL]
            ],
            'financial' => [
                ['lo' => -50, 'hi' => 50, 'name' => 'price_change_percent', 'severity' => FluxResult::WARNING],
                ['lo' => 0, 'hi' => 100, 'name' => 'volatility_index', 'severity' => FluxResult::CAUTION],
                ['lo' => -20, 'hi' => 20, 'name' => 'risk_score', 'severity' => FluxResult::CRITICAL]
            ]
        ];

        if (!isset($presets[$name])) {
            throw new InvalidArgumentException("Unknown industry preset: {$name}");
        }

        return new self($presets[$name]);
    }

    /**
     * Get list of available industry presets
     *
     * @return array<string> Available preset names
     */
    public static function getAvailablePresets(): array
    {
        return ['aviation', 'medical', 'maritime', 'automotive', 'industrial', 'financial'];
    }

    /**
     * Get constraint definitions
     *
     * @return array<array{lo: int, hi: int, name: string, severity: int}> Constraint definitions
     */
    public function getConstraints(): array
    {
        return $this->constraints;
    }

    /**
     * Get total number of constraints
     */
    public function getConstraintCount(): int
    {
        return count($this->constraints);
    }
}