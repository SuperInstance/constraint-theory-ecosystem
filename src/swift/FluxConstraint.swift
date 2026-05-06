import Foundation

#if canImport(XCTest)
import XCTest
#endif

// MARK: - Severity Constants

public enum FluxSeverity {
    public static let PASS = 0
    public static let CAUTION = 1
    public static let WARNING = 2
    public static let CRITICAL = 3
}

// MARK: - FluxResult Structure

public struct FluxResult {
    public let errorMask: UInt8       // Bitmask of violated constraints (0-7)
    public let severity: Int          // Highest severity level encountered
    public let violatedLo: Int8       // Lowest violated threshold
    public let violatedHi: Int8       // Highest violated threshold
    public let checkedValue: Int8     // The clamped input value that was checked

    public init(errorMask: UInt8 = 0, severity: Int = FluxSeverity.PASS,
                violatedLo: Int8 = 0, violatedHi: Int8 = 0, checkedValue: Int8 = 0) {
        self.errorMask = errorMask
        self.severity = severity
        self.violatedLo = violatedLo
        self.violatedHi = violatedHi
        self.checkedValue = checkedValue
    }
}

// MARK: - FluxConstraint Structure

public struct FluxConstraintItem {
    public let loThreshold: Int8      // Lower threshold
    public let hiThreshold: Int8      // Upper threshold
    public let severity: Int          // Severity level for this constraint

    public init(loThreshold: Int8, hiThreshold: Int8, severity: Int) {
        self.loThreshold = loThreshold
        self.hiThreshold = hiThreshold
        self.severity = severity
    }
}

// MARK: - BatchStats Structure

public struct BatchStats {
    public let totalChecks: Int
    public let violationCount: Int
    public let maxSeverity: Int
    public let avgSeverity: Double
    public let processingTime: TimeInterval

    public init(totalChecks: Int, violationCount: Int, maxSeverity: Int,
                avgSeverity: Double, processingTime: TimeInterval) {
        self.totalChecks = totalChecks
        self.violationCount = violationCount
        self.maxSeverity = maxSeverity
        self.avgSeverity = avgSeverity
        self.processingTime = processingTime
    }
}

// MARK: - FluxConstraint Main Class

public class FluxConstraint {
    private var constraints: [FluxConstraintItem] = []
    private let maxConstraints = 8
    public let sensorName: String

    public init(sensorName: String = "unknown") {
        self.sensorName = sensorName
    }

    // MARK: - INT8 Saturation

    private func saturateINT8(_ value: Int) -> Int8 {
        return Int8(max(-127, min(127, value)))
    }

    // MARK: - Constraint Management

    public func addConstraint(loThreshold: Int8, hiThreshold: Int8, severity: Int) throws {
        guard constraints.count < maxConstraints else {
            throw FluxError.tooManyConstraints("Maximum 8 constraints allowed")
        }

        guard loThreshold <= hiThreshold else {
            throw FluxError.invalidThresholds("Low threshold cannot be greater than high threshold")
        }

        let constraint = FluxConstraintItem(loThreshold: loThreshold, hiThreshold: hiThreshold, severity: severity)
        constraints.append(constraint)
    }

    // MARK: - Single Value Checking

    public func check(_ value: Int) -> FluxResult {
        let clampedValue = saturateINT8(value)

        var errorMask: UInt8 = 0
        var maxSeverity = FluxSeverity.PASS
        var violatedLo: Int8 = 127
        var violatedHi: Int8 = -127

        for (index, constraint) in constraints.enumerated() {
            if clampedValue < constraint.loThreshold || clampedValue > constraint.hiThreshold {
                // Constraint violated
                errorMask |= (1 << UInt8(index))

                if constraint.severity > maxSeverity {
                    maxSeverity = constraint.severity
                }

                if constraint.loThreshold < violatedLo {
                    violatedLo = constraint.loThreshold
                }

                if constraint.hiThreshold > violatedHi {
                    violatedHi = constraint.hiThreshold
                }
            }
        }

        // Reset violated thresholds if no violations
        if errorMask == 0 {
            violatedLo = 0
            violatedHi = 0
        }

        return FluxResult(errorMask: errorMask, severity: maxSeverity,
                         violatedLo: violatedLo, violatedHi: violatedHi,
                         checkedValue: clampedValue)
    }

    // MARK: - Batch Processing

    public func checkBatch(_ values: [Int]) -> (results: [FluxResult], stats: BatchStats) {
        let startTime = CFAbsoluteTimeGetCurrent()

        let results = values.map { check($0) }
        let violationCount = results.filter { $0.errorMask != 0 }.count
        let maxSeverity = results.map { $0.severity }.max() ?? FluxSeverity.PASS
        let avgSeverity = results.isEmpty ? 0.0 : Double(results.map { $0.severity }.reduce(0, +)) / Double(results.count)

        let processingTime = CFAbsoluteTimeGetCurrent() - startTime

        let stats = BatchStats(totalChecks: values.count, violationCount: violationCount,
                              maxSeverity: maxSeverity, avgSeverity: avgSeverity,
                              processingTime: processingTime)

        return (results, stats)
    }

    // MARK: - Industry Presets

    public static let industryPresets: [String: [FluxConstraintItem]] = [
        "aviation": [
            FluxConstraintItem(loThreshold: -100, hiThreshold: 100, severity: FluxSeverity.PASS),
            FluxConstraintItem(loThreshold: -80, hiThreshold: 80, severity: FluxSeverity.CAUTION),
            FluxConstraintItem(loThreshold: -60, hiThreshold: 60, severity: FluxSeverity.WARNING),
            FluxConstraintItem(loThreshold: -40, hiThreshold: 40, severity: FluxSeverity.CRITICAL)
        ],
        "medical": [
            FluxConstraintItem(loThreshold: -50, hiThreshold: 50, severity: FluxSeverity.PASS),
            FluxConstraintItem(loThreshold: -40, hiThreshold: 40, severity: FluxSeverity.CAUTION),
            FluxConstraintItem(loThreshold: -30, hiThreshold: 30, severity: FluxSeverity.WARNING),
            FluxConstraintItem(loThreshold: -20, hiThreshold: 20, severity: FluxSeverity.CRITICAL)
        ],
        "maritime": [
            FluxConstraintItem(loThreshold: -120, hiThreshold: 120, severity: FluxSeverity.PASS),
            FluxConstraintItem(loThreshold: -90, hiThreshold: 90, severity: FluxSeverity.CAUTION),
            FluxConstraintItem(loThreshold: -60, hiThreshold: 60, severity: FluxSeverity.WARNING),
            FluxConstraintItem(loThreshold: -30, hiThreshold: 30, severity: FluxSeverity.CRITICAL)
        ],
        "automotive": [
            FluxConstraintItem(loThreshold: -110, hiThreshold: 110, severity: FluxSeverity.PASS),
            FluxConstraintItem(loThreshold: -85, hiThreshold: 85, severity: FluxSeverity.CAUTION),
            FluxConstraintItem(loThreshold: -55, hiThreshold: 55, severity: FluxSeverity.WARNING),
            FluxConstraintItem(loThreshold: -25, hiThreshold: 25, severity: FluxSeverity.CRITICAL)
        ],
        "energy": [
            FluxConstraintItem(loThreshold: -127, hiThreshold: 127, severity: FluxSeverity.PASS),
            FluxConstraintItem(loThreshold: -100, hiThreshold: 100, severity: FluxSeverity.CAUTION),
            FluxConstraintItem(loThreshold: -75, hiThreshold: 75, severity: FluxSeverity.WARNING),
            FluxConstraintItem(loThreshold: -50, hiThreshold: 50, severity: FluxSeverity.CRITICAL)
        ]
    ]

    public func fromPreset(_ presetName: String) throws {
        guard let presetConstraints = FluxConstraint.industryPresets[presetName] else {
            throw FluxError.unknownPreset("Unknown preset: \(presetName)")
        }

        constraints.removeAll()

        for constraint in presetConstraints {
            try addConstraint(loThreshold: constraint.loThreshold,
                             hiThreshold: constraint.hiThreshold,
                             severity: constraint.severity)
        }
    }

    // MARK: - Benchmarking

    public func benchmark(iterations: Int = 10000) throws -> Double {
        guard iterations > 0 else {
            throw FluxError.invalidParameter("Iterations must be positive")
        }

        // Prepare test data
        let testValues = (0..<1000).map { ($0 % 255) - 127 }

        let startTime = CFAbsoluteTimeGetCurrent()
        var checksPerformed = 0

        for _ in 0..<iterations {
            for value in testValues {
                _ = check(value)
                checksPerformed += 1
            }
        }

        let duration = CFAbsoluteTimeGetCurrent() - startTime
        return Double(checksPerformed) / duration
    }
}

// MARK: - Error Types

public enum FluxError: Error, LocalizedError {
    case tooManyConstraints(String)
    case invalidThresholds(String)
    case unknownPreset(String)
    case invalidParameter(String)

    public var errorDescription: String? {
        switch self {
        case .tooManyConstraints(let message),
             .invalidThresholds(let message),
             .unknownPreset(let message),
             .invalidParameter(let message):
            return message
        }
    }
}

// MARK: - Unit Tests

#if canImport(XCTest)

public class FluxConstraintTests: XCTestCase {

    func testSaturateINT8() {
        let fc = FluxConstraint(sensorName: "test")

        XCTAssertEqual(fc.saturateINT8(0), 0)
        XCTAssertEqual(fc.saturateINT8(127), 127)
        XCTAssertEqual(fc.saturateINT8(128), 127)
        XCTAssertEqual(fc.saturateINT8(-127), -127)
        XCTAssertEqual(fc.saturateINT8(-128), -127)
        XCTAssertEqual(fc.saturateINT8(1000), 127)
        XCTAssertEqual(fc.saturateINT8(-1000), -127)
    }

    func testAddConstraint() {
        let fc = FluxConstraint(sensorName: "test")

        // Test normal addition
        XCTAssertNoThrow(try fc.addConstraint(loThreshold: -50, hiThreshold: 50, severity: FluxSeverity.WARNING))

        // Test invalid threshold order
        XCTAssertThrowsError(try fc.addConstraint(loThreshold: 50, hiThreshold: -50, severity: FluxSeverity.WARNING))

        // Test maximum constraints
        for _ in 1..<8 {
            try! fc.addConstraint(loThreshold: -10, hiThreshold: 10, severity: FluxSeverity.PASS)
        }

        XCTAssertThrowsError(try fc.addConstraint(loThreshold: -5, hiThreshold: 5, severity: FluxSeverity.PASS))
    }

    func testBasicCheck() {
        let fc = FluxConstraint(sensorName: "test")
        try! fc.addConstraint(loThreshold: -50, hiThreshold: 50, severity: FluxSeverity.WARNING)

        // Test within bounds
        let result1 = fc.check(25)
        XCTAssertEqual(result1.errorMask, 0)

        // Test out of bounds
        let result2 = fc.check(75)
        XCTAssertNotEqual(result2.errorMask, 0)
        XCTAssertEqual(result2.severity, FluxSeverity.WARNING)
    }

    func testMultipleConstraints() {
        let fc = FluxConstraint(sensorName: "test")
        try! fc.addConstraint(loThreshold: -100, hiThreshold: 100, severity: FluxSeverity.PASS)
        try! fc.addConstraint(loThreshold: -50, hiThreshold: 50, severity: FluxSeverity.CAUTION)
        try! fc.addConstraint(loThreshold: -25, hiThreshold: 25, severity: FluxSeverity.WARNING)
        try! fc.addConstraint(loThreshold: -10, hiThreshold: 10, severity: FluxSeverity.CRITICAL)

        let result = fc.check(75)

        // Should violate constraints 1, 2, and 3 (bits 1, 2, 3 set)
        let expectedMask: UInt8 = 0b00001110
        XCTAssertEqual(result.errorMask, expectedMask)
        XCTAssertEqual(result.severity, FluxSeverity.CRITICAL)
    }

    func testCheckBatch() {
        let fc = FluxConstraint(sensorName: "test")
        try! fc.addConstraint(loThreshold: -50, hiThreshold: 50, severity: FluxSeverity.WARNING)

        let values = [-25, 0, 25, 75, -75]
        let (results, stats) = fc.checkBatch(values)

        XCTAssertEqual(results.count, values.count)
        XCTAssertEqual(stats.totalChecks, values.count)
        XCTAssertEqual(stats.violationCount, 2)
    }

    func testFromPreset() {
        let fc = FluxConstraint(sensorName: "test")

        let presets = ["aviation", "medical", "maritime", "automotive", "energy"]

        for preset in presets {
            XCTAssertNoThrow(try fc.fromPreset(preset))
            XCTAssertGreaterThan(fc.constraints.count, 0)
        }

        // Test invalid preset
        XCTAssertThrowsError(try fc.fromPreset("invalid"))
    }

    func testBenchmark() {
        let fc = FluxConstraint(sensorName: "test")
        try! fc.fromPreset("aviation")

        XCTAssertNoThrow(try fc.benchmark(iterations: 100))

        let rate = try! fc.benchmark(iterations: 100)
        XCTAssertGreaterThan(rate, 0)

        // Test invalid iterations
        XCTAssertThrowsError(try fc.benchmark(iterations: 0))
    }

    func testSaturationBehavior() {
        let fc = FluxConstraint(sensorName: "test")
        try! fc.addConstraint(loThreshold: -50, hiThreshold: 50, severity: FluxSeverity.WARNING)

        // Test extreme values get saturated
        let result1 = fc.check(1000)
        XCTAssertEqual(result1.checkedValue, 127)

        let result2 = fc.check(-1000)
        XCTAssertEqual(result2.checkedValue, -127)
    }

    func testViolatedThresholds() {
        let fc = FluxConstraint(sensorName: "test")
        try! fc.addConstraint(loThreshold: -30, hiThreshold: 30, severity: FluxSeverity.WARNING)
        try! fc.addConstraint(loThreshold: -60, hiThreshold: 60, severity: FluxSeverity.CAUTION)

        let result = fc.check(45)

        XCTAssertEqual(result.violatedLo, -30)
        XCTAssertEqual(result.violatedHi, 30)
    }

    func testPerformance() {
        let fc = FluxConstraint(sensorName: "performance")
        try! fc.fromPreset("aviation")

        self.measure {
            for i in 0..<10000 {
                _ = fc.check((i % 255) - 127)
            }
        }
    }
}

#endif