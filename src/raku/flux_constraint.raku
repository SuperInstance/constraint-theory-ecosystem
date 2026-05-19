# FLUX Constraint Engine — Raku (2015, Grammar-First)
# Pure INT8 saturated constraint checking. Zero dependencies.
#
# The insight: Raku has grammars BUILT INTO THE LANGUAGE.
# GUARD DSL syntax can be parsed natively — no external parser needed.
# The grammar IS the type checker. The action class IS the compiler.
# Raku blurs the line between language and metalanguage.
#
# "Grammars are first-class. The parser IS the program.
#  GUARD DSL isn't a foreign language — it's a Raku grammar."

use v6.d;

# ══ Constants ══════════════════════════════════════════════════════

constant INT8-MIN = -127;
constant INT8-MAX = 127;
constant MAX-CONSTRAINTS = 8;

# ══ Severity ══════════════════════════════════════════════════════

enum Severity (
    :Pass(0),
    :Caution(1),
    :Warning(2),
    :Critical(3),
);

sub severity-name(Severity $s --> Str) {
    given $s {
        when Pass     { 'PASS' }
        when Caution  { 'CAUTION' }
        when Warning  { 'WARNING' }
        when Critical { 'CRITICAL' }
    }
}

# ══ Saturate ══════════════════════════════════════════════════════

sub saturate(Int $val --> Int) is pure {
    max(INT8-MIN, min(INT8-MAX, $val));
}

# ══ Constraint ════════════════════════════════════════════════════

class Constraint {
    has Int $.lo is required;
    has Int $.hi is required;
    has Str $.name is rw = '';
}

# ══ FluxResult ═══════════════════════════════════════════════════

class FluxResult {
    has Int $.error-mask is required;
    has Severity $.severity is required;
    has Int $.violated-lo is required;
    has Int $.violated-hi is required;
    has Int $.violated-count is required;
    has Bool $.passed is required;

    method gist() {
        my $sev = severity-name($!severity);
        "FluxResult($sev, mask=0x{$!error-mask.fmt('%02X')}, passed={$!passed})"
    }
}

# ══ Severity classification ══════════════════════════════════════

sub classify-severity(Int $vc, Int $n --> Severity) is pure {
    when $vc == 0                    { Pass }
    when $n > 0 && $vc ≤ $n div 4   { Caution }
    when $n > 0 && $vc ≤ $n div 2   { Warning }
    default                          { Critical }
}

# ══ Core check ═══════════════════════════════════════════════════

sub check(@constraints, Int $raw-val --> FluxResult) is pure {
    my Int $val = saturate($raw-val);
    my Int $em = 0;
    my Int $vlo = 0;
    my Int $vhi = 0;
    my Int $vc = 0;
    my Int $n = @constraints.elems;

    for @constraints.kv -> $i, $c {
        my Bool $lo-fail = $val < $c.lo;
        my Bool $hi-fail = $val > $c.hi;
        my Bool $any-fail = $lo-fail || $hi-fail;
        my Int $bit = 1 +< $i;  # left shift

        $em  +|= $bit if $any-fail;
        $vlo +|= $bit if $lo-fail;
        $vhi +|= $bit if $hi-fail;
        $vc++          if $any-fail;
    }

    FluxResult.new(
        error-mask     => $em,
        severity       => classify-severity($vc, $n),
        violated-lo    => $vlo,
        violated-hi    => $vhi,
        violated-count => $vc,
        passed         => $vc == 0,
    );
}

# ══ Batch check ══════════════════════════════════════════════════

sub check-batch(@constraints, @values --> List) {
    @values.map(-> $v { check(@constraints, $v) }).List;
}

# ══ GUARD DSL Grammar ═════════════════════════════════════════════
# This is the KEY: Raku parses GUARD DSL natively.

grammar GUARD::DSL {
    token TOP {
        ^ \s*
        [ <comment> | <blank> | <guard-stmt> ]*
        \s* $
    }
    token comment { '#' \N* }
    token blank { \s* }
    token guard-stmt {
        'GUARD' \s+ <name> \s+
        [ 'in' \s+ '[' \s* <lo=integer> \s* ',' \s* <hi=integer> \s* ']'
        | '>' \s+ <hi=integer>
        | '<' \s* <lo=integer>
        ]
        [ \s+ 'with' \s+ 'priority' \s+ <priority> ]?
    }
    token name { \w+ [ '_' \w+ ]* }
    token integer { '-'? \d+ }
    token priority { \w+ }
}

class GUARD::DSL::Actions {
    method TOP($/) {
        make $/.grep(*.defined).map: *.ast;
    }
    method guard-stmt($/) {
        my $c = Constraint.new(
            lo => $/<lo> ?? +$/<lo> !! INT8-MIN,
            hi => $/<hi> ?? +$/<hi> !! INT8-MAX,
            name => ~$/<name>,
        );
        make $c;
    }
    method comment($/) { make Nil }
    method blank($/)   { make Nil }
}

sub parse-guard(Str $text --> Array[Constraint]) {
    my $ast = GUARD::DSL.parse($text, :actions(GUARD::DSL::Actions));
    $ast.ast.grep(Constraint).Array;
}

# ══ Industry Presets ══════════════════════════════════════════════

my Array[Constraint] $aviation = [
    Constraint.new(:lo(-55), :hi(70), :name<cabin_temp_C>),
    Constraint.new(:lo(75),  :hi(101), :name<cabin_pressure_kPa>),
    Constraint.new(:lo(0),   :hi(100), :name<fuel_flow_pct>),
    Constraint.new(:lo(60),  :hi(100), :name<hydraulic_pct>),
];

my Array[Constraint] $automotive = [
    Constraint.new(:lo(-40), :hi(60), :name<battery_temp_C>),
    Constraint.new(:lo(0),   :hi(100), :name<soc_pct>),
    Constraint.new(:lo(0),   :hi(100), :name<charge_rate_pct>),
    Constraint.new(:lo(20),  :hi(80), :name<cabin_temp_C>),
];

my Array[Constraint] $nuclear = [
    Constraint.new(:lo(0),  :hi(110), :name<neutron_flux_pct>),
    Constraint.new(:lo(0),  :hi(65),  :name<core_temp_C_x10>),
    Constraint.new(:lo(72), :hi(100), :name<pressurizer_pct>),
    Constraint.new(:lo(0),  :hi(100), :name<coolant_flow_pct>),
];

my Array[Constraint] $medical = [
    Constraint.new(:lo(36), :hi(38),  :name<body_temp_C>),
    Constraint.new(:lo(60), :hi(100), :name<heart_rate_bpm>),
    Constraint.new(:lo(95), :hi(100), :name<spo2_pct>),
    Constraint.new(:lo(80), :hi(120), :name<bp_systolic_mmHg>),
];

my Array[Constraint] $maritime = [
    Constraint.new(:lo(-2), :hi(35),  :name<sea_temp_C>),
    Constraint.new(:lo(50), :hi(100), :name<hull_integrity_pct>),
    Constraint.new(:lo(0),  :hi(50),  :name<wave_height_m>),
    Constraint.new(:lo(0),  :hi(80),  :name<wind_speed_kn>),
];

# ══ Main ══════════════════════════════════════════════════════════

sub MAIN() {
    say "═══ FLUX Constraint Engine — Raku (Grammar-First) ═══";
    say "";

    my $r1 = check($aviation, 60);
    say "  Aviation val=60:  {$r1.gist}";

    my $r2 = check($aviation, 25);
    say "  Aviation val=25:  {$r2.gist}";

    my $r3 = check($nuclear, 127);
    say "  Nuclear val=127:  {$r3.gist}";

    say "";
    say "GUARD DSL Grammar:";
    my $guard-text = q:to/END/;
        GUARD battery_temp in [15, 55]
        GUARD charge_rate in [0, 100]
        END
    my $parsed = parse-guard($guard-text);
    say "  Parsed {$parsed.elems} constraints from GUARD DSL text";
    for $parsed.kv -> $i, $c {
        say "    {$c.name}: [{$c.lo}, {$c.hi}]";
    }
    my $r4 = check($parsed, 60);
    say "  Check val=60: {$r4.gist}";
}

# Raku teaches us that the parser CAN BE the program.
# GUARD DSL isn't a foreign language — it's a Raku grammar.
# The grammar parses. The action class compiles. The result checks.
# No external tools. No code generation. The language IS the DSL.
