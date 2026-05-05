<?php

declare(strict_types=1);

use PHPUnit\Framework\TestCase;

/**
 * Test suite for FluxConstraint class
 *
 * Comprehensive tests covering constraint checking, saturation,
 * batch operations, and industry presets.
 */
class FluxConstraintTest extends TestCase
{
    private FluxConstraint $basicConstraint;
    private FluxConstraint $multiConstraint;

    protected function setUp(): void
    {
        $this->basicConstraint = new FluxConstraint([
            ['lo' => -10, 'hi' => 10, 'name' => 'basic_range']
        ]);

        $this->multiConstraint = new FluxConstraint([
            ['lo' => -50, 'hi' => 50, 'name' => 'wide_range', 'severity' => FluxResult::CAUTION],
            ['lo' => -10, 'hi' => 10, 'name' => 'tight_range', 'severity' => FluxResult::WARNING],
            ['lo' => 0, 'hi' => 100, 'name' => 'positive_range', 'severity' => FluxResult::CRITICAL]
        ]);
    }

    /**
     * Test 1: Basic range check - value passes
     */
    public function testBasicRangePass(): void
    {
        $result = $this->basicConstraint->check(5);

        $this->assertTrue($result->isPassing());
        $this->assertEquals(0, $result->error_mask);
        $this->assertEquals(FluxResult::PASS, $result->severity);
        $this->assertEquals(0, $result->violated_lo);
        $this->assertEquals(0, $result->violated_hi);
        $this->assertTrue($result->constraint_results['basic_range']['passed']);
    }

    /**
     * Test 2: Basic range check - value fails below
     */
    public function testBasicRangeFailBelow(): void
    {
        $result = $this->basicConstraint->check(-15);

        $this->assertFalse($result->isPassing());
        $this->assertEquals(1, $result->error_mask);
        $this->assertEquals(FluxResult::WARNING, $result->severity);
        $this->assertEquals(1, $result->violated_lo);
        $this->assertEquals(0, $result->violated_hi);
        $this->assertFalse($result->constraint_results['basic_range']['passed']);
    }

    /**
     * Test 3: Basic range check - value fails above
     */
    public function testBasicRangeFailAbove(): void
    {
        $result = $this->basicConstraint->check(15);

        $this->assertFalse($result->isPassing());
        $this->assertEquals(1, $result->error_mask);
        $this->assertEquals(FluxResult::WARNING, $result->severity);
        $this->assertEquals(0, $result->violated_lo);
        $this->assertEquals(1, $result->violated_hi);
        $this->assertFalse($result->constraint_results['basic_range']['passed']);
    }

    /**
     * Test 4: Saturation - value beyond INT8_MAX
     */
    public function testSaturationMax(): void
    {
        $saturated = FluxConstraint::saturate(200);
        $this->assertEquals(127, $saturated);

        $result = $this->basicConstraint->check(200);
        $this->assertEquals(127, $result->constraint_results['basic_range']['value']);
    }

    /**
     * Test 5: Saturation - value beyond INT8_MIN
     */
    public function testSaturationMin(): void
    {
        $saturated = FluxConstraint::saturate(-200);
        $this->assertEquals(-127, $saturated);

        $result = $this->basicConstraint->check(-200);
        $this->assertEquals(-127, $result->constraint_results['basic_range']['value']);
    }

    /**
     * Test 6: Saturation - edge cases
     */
    public function testSaturationEdgeCases(): void
    {
        $this->assertEquals(127, FluxConstraint::saturate(127));
        $this->assertEquals(-127, FluxConstraint::saturate(-127));
        $this->assertEquals(0, FluxConstraint::saturate(0));
        $this->assertEquals(50, FluxConstraint::saturate(50));
        $this->assertEquals(-50, FluxConstraint::saturate(-50));
    }

    /**
     * Test 7: Multiple constraints - all pass
     */
    public function testMultipleConstraintsAllPass(): void
    {
        $result = $this->multiConstraint->check(5);

        $this->assertTrue($result->isPassing());
        $this->assertEquals(0, $result->error_mask);
        $this->assertEquals(FluxResult::PASS, $result->severity);

        // All three constraints should pass
        $this->assertTrue($result->constraint_results['wide_range']['passed']);
        $this->assertTrue($result->constraint_results['tight_range']['passed']);
        $this->assertTrue($result->constraint_results['positive_range']['passed']);
    }

    /**
     * Test 8: Multiple constraints - mixed pass/fail
     */
    public function testMultipleConstraintsMixed(): void
    {
        $result = $this->multiConstraint->check(-20); // Fails tight and positive, passes wide

        $this->assertFalse($result->isPassing());
        $this->assertEquals(6, $result->error_mask); // Binary: 110 (constraints 1 and 2 failed)
        $this->assertEquals(FluxResult::CRITICAL, $result->severity); // Highest severity wins

        $this->assertTrue($result->constraint_results['wide_range']['passed']);
        $this->assertFalse($result->constraint_results['tight_range']['passed']);
        $this->assertFalse($result->constraint_results['positive_range']['passed']);
    }

    /**
     * Test 9: Severity calculation
     */
    public function testSeverityCalculation(): void
    {
        // Test each severity level
        $cautionResult = $this->multiConstraint->check(60); // Fails only wide_range (CAUTION)
        $this->assertEquals(FluxResult::CAUTION, $cautionResult->severity);

        $warningResult = $this->multiConstraint->check(-20); // Fails tight_range (WARNING) and positive_range (CRITICAL)
        $this->assertEquals(FluxResult::CRITICAL, $warningResult->severity); // Higher severity wins
    }

    /**
     * Test 10: Batch checking - all pass
     */
    public function testBatchCheckingAllPass(): void
    {
        $values = [0, 5, -5, 8, -8];
        $results = $this->basicConstraint->checkBatch($values);

        $this->assertCount(5, $results);
        foreach ($results as $result) {
            $this->assertTrue($result->isPassing());
            $this->assertEquals(FluxResult::PASS, $result->severity);
        }
    }

    /**
     * Test 11: Batch checking - mixed results
     */
    public function testBatchCheckingMixed(): void
    {
        $values = [-15, 5, 20, 0, -8]; // Two failures, three passes
        $results = $this->basicConstraint->checkBatch($values);

        $this->assertCount(5, $results);
        $this->assertFalse($results[0]->isPassing()); // -15
        $this->assertTrue($results[1]->isPassing());  // 5
        $this->assertFalse($results[2]->isPassing()); // 20
        $this->assertTrue($results[3]->isPassing());  // 0
        $this->assertTrue($results[4]->isPassing());  // -8
    }

    /**
     * Test 12: Industry preset - aviation
     */
    public function testIndustryPresetAviation(): void
    {
        $aviation = FluxConstraint::fromIndustry('aviation');
        $constraints = $aviation->getConstraints();

        $this->assertCount(3, $constraints);
        $this->assertEquals('altitude_deviation', $constraints[0]['name']);
        $this->assertEquals(FluxResult::CRITICAL, $constraints[0]['severity']);
        $this->assertEquals(-50, $constraints[0]['lo']);
        $this->assertEquals(50, $constraints[0]['hi']);
    }

    /**
     * Test 13: Industry preset - medical
     */
    public function testIndustryPresetMedical(): void
    {
        $medical = FluxConstraint::fromIndustry('medical');
        $result = $medical->check(75); // Normal heart rate

        $this->assertTrue($result->constraint_results['heart_rate_bpm']['passed']);
        $this->assertTrue($result->isPassing());
    }

    /**
     * Test 14: Invalid industry preset
     */
    public function testInvalidIndustryPreset(): void
    {
        $this->expectException(InvalidArgumentException::class);
        $this->expectExceptionMessage('Unknown industry preset: nonexistent');

        FluxConstraint::fromIndustry('nonexistent');
    }

    /**
     * Test 15: Available presets
     */
    public function testAvailablePresets(): void
    {
        $presets = FluxConstraint::getAvailablePresets();

        $this->assertIsArray($presets);
        $this->assertContains('aviation', $presets);
        $this->assertContains('medical', $presets);
        $this->assertContains('maritime', $presets);
        $this->assertContains('automotive', $presets);
        $this->assertContains('industrial', $presets);
        $this->assertContains('financial', $presets);
        $this->assertCount(6, $presets);
    }

    /**
     * Test 16: Edge case - zero values
     */
    public function testZeroValues(): void
    {
        $zeroConstraint = new FluxConstraint([
            ['lo' => 0, 'hi' => 0, 'name' => 'zero_only']
        ]);

        $passResult = $zeroConstraint->check(0);
        $this->assertTrue($passResult->isPassing());

        $failResult = $zeroConstraint->check(1);
        $this->assertFalse($failResult->isPassing());
    }

    /**
     * Test 17: Edge case - boundary values
     */
    public function testBoundaryValues(): void
    {
        // Test exact boundary matches
        $result1 = $this->basicConstraint->check(-10); // Exact lower bound
        $this->assertTrue($result1->isPassing());

        $result2 = $this->basicConstraint->check(10); // Exact upper bound
        $this->assertTrue($result2->isPassing());

        $result3 = $this->basicConstraint->check(-11); // Just below lower bound
        $this->assertFalse($result3->isPassing());

        $result4 = $this->basicConstraint->check(11); // Just above upper bound
        $this->assertFalse($result4->isPassing());
    }

    /**
     * Test 18: FluxResult utility methods
     */
    public function testFluxResultUtilities(): void
    {
        $passResult = $this->basicConstraint->check(5);
        $failResult = $this->basicConstraint->check(15);

        // Test isPassing
        $this->assertTrue($passResult->isPassing());
        $this->assertFalse($failResult->isPassing());

        // Test severity names
        $this->assertEquals('PASS', $passResult->getSeverityName());
        $this->assertEquals('WARNING', $failResult->getSeverityName());

        // Test isCritical
        $criticalConstraint = new FluxConstraint([
            ['lo' => 0, 'hi' => 10, 'name' => 'critical_test', 'severity' => FluxResult::CRITICAL]
        ]);
        $criticalResult = $criticalConstraint->check(-5);
        $this->assertTrue($criticalResult->isCritical());
    }

    /**
     * Test 19: Invalid constraint construction
     */
    public function testInvalidConstraintConstruction(): void
    {
        $this->expectException(InvalidArgumentException::class);
        $this->expectExceptionMessage('Each constraint must have lo, hi, and name');

        new FluxConstraint([
            ['lo' => 0] // Missing 'hi' and 'name'
        ]);
    }

    /**
     * Test 20: Constraint metadata access
     */
    public function testConstraintMetadataAccess(): void
    {
        $constraints = $this->multiConstraint->getConstraints();
        $count = $this->multiConstraint->getConstraintCount();

        $this->assertCount(3, $constraints);
        $this->assertEquals(3, $count);

        // Verify constraint structure
        foreach ($constraints as $constraint) {
            $this->assertArrayHasKey('lo', $constraint);
            $this->assertArrayHasKey('hi', $constraint);
            $this->assertArrayHasKey('name', $constraint);
            $this->assertArrayHasKey('severity', $constraint);
        }
    }
}