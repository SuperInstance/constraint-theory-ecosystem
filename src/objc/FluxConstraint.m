// FLUX Constraint Engine — Objective-C
// Pure INT8 saturated constraint checking. Foundation-only.

#import <Foundation/Foundation.h>

NS_ASSUME_NONNULL_BEGIN

extern const NSInteger INT8_FLUX_MIN;
extern const NSInteger INT8_FLUX_MAX;

typedef NS_ENUM(NSInteger, FluxSeverity) {
    FluxSeverityPass = 0,
    FluxSeverityCaution = 1,
    FluxSeverityWarning = 2,
    FluxSeverityCritical = 3
};

@interface FluxConstraint : NSObject
@property (nonatomic, readonly) NSInteger lo;
@property (nonatomic, readonly) NSInteger hi;
@property (nonatomic, readonly) NSString *name;
- (instancetype)initWithLo:(NSInteger)lo hi:(NSInteger)hi name:(NSString *)name;
@end

@interface FluxResult : NSObject
@property (nonatomic, readonly) NSInteger errorMask;
@property (nonatomic, readonly) FluxSeverity severity;
@property (nonatomic, readonly) NSInteger violatedLo;
@property (nonatomic, readonly) NSInteger violatedHi;
@property (nonatomic, readonly) NSInteger violatedCount;
@property (nonatomic, readonly) BOOL passed;
@end

@interface FluxChecker : NSObject
- (instancetype)initWithConstraints:(NSArray<FluxConstraint *> *)constraints;
- (FluxResult *)check:(NSInteger)value;
- (NSArray<FluxResult *> *)checkBatch:(NSArray<NSNumber *> *)values;
- (double)benchmark:(NSInteger)iterations;
+ (FluxChecker *)fromPreset:(NSString *)name;
+ (NSInteger)saturate:(NSInteger)val;
@end

NS_ASSUME_NONNULL_END

// === Implementation ===

const NSInteger INT8_FLUX_MIN = -127;
const NSInteger INT8_FLUX_MAX = 127;

@implementation FluxConstraint
- (instancetype)initWithLo:(NSInteger)lo hi:(NSInteger)hi name:(NSString *)name {
    self = [super init];
    if (self) {
        _lo = lo; _hi = hi; _name = name ?: @"";
    }
    return self;
}
@end

@implementation FluxResult
@end

@implementation FluxChecker {
    NSArray<FluxConstraint *> *_constraints;
}

+ (NSInteger)saturate:(NSInteger)val {
    if (val < INT8_FLUX_MIN) return INT8_FLUX_MIN;
    if (val > INT8_FLUX_MAX) return INT8_FLUX_MAX;
    return val;
}

- (instancetype)initWithConstraints:(NSArray<FluxConstraint *> *)constraints {
    self = [super init];
    NSAssert(constraints.count > 0, @"Non-empty constraints required");
    NSAssert(constraints.count <= 8, @"Max 8 constraints");
    if (self) _constraints = [constraints copy];
    return self;
}

- (FluxResult *)check:(NSInteger)value {
    NSInteger val = [FluxChecker saturate:value];
    NSInteger errorMask = 0, violatedLo = 0, violatedHi = 0, violatedCount = 0;

    for (NSInteger i = 0; i < (NSInteger)_constraints.count; i++) {
        FluxConstraint *c = _constraints[i];
        NSInteger lo = [FluxChecker saturate:c.lo];
        NSInteger hi = [FluxChecker saturate:c.hi];
        BOOL loFail = val < lo, hiFail = val > hi;
        NSInteger bit = 1 << i;
        if (loFail || hiFail) { errorMask |= bit; violatedCount++; }
        if (loFail) violatedLo |= bit;
        if (hiFail) violatedHi |= bit;
    }

    NSInteger nc = _constraints.count;
    FluxSeverity sev;
    if (violatedCount == 0) sev = FluxSeverityPass;
    else if (violatedCount <= nc/4) sev = FluxSeverityCaution;
    else if (violatedCount <= nc/2) sev = FluxSeverityWarning;
    else sev = FluxSeverityCritical;

    FluxResult *r = [[FluxResult alloc] init];
    [r setValue:@(errorMask) forKey:@"errorMask"];
    [r setValue:@(sev) forKey:@"severity"];
    [r setValue:@(violatedLo) forKey:@"violatedLo"];
    [r setValue:@(violatedHi) forKey:@"violatedHi"];
    [r setValue:@(violatedCount) forKey:@"violatedCount"];
    [r setValue:@(sev == FluxSeverityPass) forKey:@"passed"];
    return r;
}

- (NSArray<FluxResult *> *)checkBatch:(NSArray<NSNumber *> *)values {
    NSMutableArray *results = [NSMutableArray array];
    for (NSNumber *v in values) [results addObject:[self check:v.integerValue]];
    return results;
}

- (double)benchmark:(NSInteger)iterations {
    NSDate *t0 = [NSDate date];
    for (NSInteger i = 0; i < iterations; i++)
        [self check:(i % 254) - 127];
    double sec = -[t0 timeIntervalSinceNow];
    return iterations * _constraints.count / sec;
}

+ (FluxChecker *)fromPreset:(NSString *)name {
    NSArray *cs;
    if ([name isEqualToString:@"aviation"])
        cs = @[[[FluxConstraint alloc] initWithLo:-55 hi:70 name:@"cabin_temp_C"],
               [[FluxConstraint alloc] initWithLo:75 hi:101 name:@"cabin_pressure_kPa"],
               [[FluxConstraint alloc] initWithLo:0 hi:100 name:@"fuel_flow_pct"],
               [[FluxConstraint alloc] initWithLo:60 hi:100 name:@"hydraulic_pct"]];
    else if ([name isEqualToString:@"medical"])
        cs = @[[[FluxConstraint alloc] initWithLo:36 hi:38 name:@"body_temp_C"],
               [[FluxConstraint alloc] initWithLo:60 hi:100 name:@"heart_rate_bpm"],
               [[FluxConstraint alloc] initWithLo:95 hi:100 name:@"spo2_pct"],
               [[FluxConstraint alloc] initWithLo:80 hi:120 name:@"bp_systolic_mmHg"]];
    else
        @throw [NSException exceptionWithName:@"BadPreset" reason:name userInfo:nil];
    return [[FluxChecker alloc] initWithConstraints:cs];
}
@end

// Self-test
int main(int argc, char *argv[]) {
    @autoreleasepool {
        NSLog(@"FLUX Constraint Engine — Objective-C");
        NSLog(@"=====================================");
        NSCAssert([FluxChecker saturate:-128] == -127, @"sat min");
        NSCAssert([FluxChecker saturate:128] == 127, @"sat max");
        NSLog(@"  saturate: OK");

        FluxChecker *fc = [[FluxChecker alloc] initWithConstraints:@[
            [[FluxConstraint alloc] initWithLo:0 hi:100 name:@"test"]
        ]];
        NSCAssert([fc check:50].passed, @"should pass");
        NSCAssert(![fc check:150].passed, @"should fail");
        NSLog(@"  check: OK");

        FluxChecker *fc3 = [FluxChecker fromPreset:@"aviation"];
        NSLog(@"  presets: OK (%lu constraints)", (unsigned long)fc3.constraints.count);
        NSLog(@"  All tests pass");
    }
    return 0;
}
