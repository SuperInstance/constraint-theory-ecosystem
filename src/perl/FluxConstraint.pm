# FLUX Constraint Engine — Perl 5
# Pure INT8 saturated constraint checking. Zero dependencies.

package FluxConstraint;
use strict;
use warnings;

use constant INT8_MIN => -127;
use constant INT8_MAX => 127;

sub saturate {
    my ($val) = @_;
    $val = INT8_MIN if $val < INT8_MIN;
    $val = INT8_MAX if $val > INT8_MAX;
    return int($val);
}

sub new {
    my ($class, $constraints) = @_;
    die "Non-empty constraints required" unless @$constraints;
    die "Max 8 constraints" if @$constraints > 8;
    my @cs = map {
        { lo => saturate($_->{lo}), hi => saturate($_->{hi}), name => $_->{name} // "C$_" }
    } @$constraints;
    return bless { constraints => \@cs }, $class;
}

sub check {
    my ($self, $value) = @_;
    my $val = saturate($value);
    my ($error_mask, $violated_lo, $violated_hi, $violated_count) = (0, 0, 0, 0);

    for my $i (0 .. $#{$self->{constraints}}) {
        my $c = $self->{constraints}[$i];
        my $lo_fail = $val < $c->{lo};
        my $hi_fail = $val > $c->{hi};

        if ($lo_fail || $hi_fail) {
            $error_mask |= (1 << $i);
            $violated_count++;
        }
        $violated_lo |= (1 << $i) if $lo_fail;
        $violated_hi |= (1 << $i) if $hi_fail;
    }

    my $nc = scalar @{$self->{constraints}};
    my $severity = $violated_count == 0 ? 0
                 : $violated_count <= int($nc/4) ? 1
                 : $violated_count <= int($nc/2) ? 2
                 : 3;

    return {
        error_mask => $error_mask,
        severity => $severity,
        violated_lo => $violated_lo,
        violated_hi => $violated_hi,
        violated_count => $violated_count,
        passed => $violated_count == 0,
    };
}

sub check_batch {
    my ($self, $values) = @_;
    my @results = map { $self->check($_) } @$values;
    my %stats = (
        pass => scalar(grep { $_->{severity} == 0 } @results),
        caution => scalar(grep { $_->{severity} == 1 } @results),
        warning => scalar(grep { $_->{severity} == 2 } @results),
        critical => scalar(grep { $_->{severity} == 3 } @results),
    );
    return (\@results, \%stats);
}

sub benchmark {
    my ($self, $iterations) = @_;
    $iterations //= 1_000_000;
    my $t0 = time();
    my $dummy;
    for my $i (1..$iterations) {
        $dummy = $self->check(($i % 254) - 127);
    }
    my $elapsed = time() - $t0;
    my $rate = $iterations * scalar(@{$self->{constraints}}) / ($elapsed || 1);
    return ($rate, $elapsed * 1000);
}

# Presets
my %PRESETS = (
    aviation => [
        { lo => -55, hi => 70, name => 'cabin_temp_C' },
        { lo => 75, hi => 101, name => 'cabin_pressure_kPa' },
        { lo => 0, hi => 100, name => 'fuel_flow_pct' },
        { lo => 60, hi => 100, name => 'hydraulic_pct' },
    ],
    medical => [
        { lo => 36, hi => 38, name => 'body_temp_C' },
        { lo => 60, hi => 100, name => 'heart_rate_bpm' },
        { lo => 95, hi => 100, name => 'spo2_pct' },
        { lo => 80, hi => 120, name => 'bp_systolic_mmHg' },
    ],
    maritime => [
        { lo => -2, hi => 35, name => 'sea_temp_C' },
        { lo => 50, hi => 100, name => 'hull_integrity_pct' },
        { lo => 0, hi => 50, name => 'wave_height_m' },
        { lo => 0, hi => 80, name => 'wind_speed_kn' },
    ],
    automotive => [
        { lo => -40, hi => 60, name => 'battery_temp_C' },
        { lo => 0, hi => 100, name => 'soc_pct' },
        { lo => 0, hi => 100, name => 'charge_rate_pct' },
        { lo => 20, hi => 80, name => 'cabin_temp_C' },
    ],
    energy => [
        { lo => 49, hi => 51, name => 'grid_freq_Hz_x10' },
        { lo => 95, hi => 105, name => 'voltage_pct' },
        { lo => 0, hi => 80, name => 'transformer_temp_C' },
        { lo => 0, hi => 100, name => 'line_load_pct' },
    ],
);

sub from_preset {
    my ($class, $name) = @_;
    die "Unknown preset: $name" unless $PRESETS{$name};
    return $class->new($PRESETS{$name});
}

1;

# Self-test
__END__
=cut
perl -Isrc/perl -MFluxConstraint -e '
    print "FLUX Constraint Engine - Perl\n";
    print "==============================\n";

    die "sat" unless FluxConstraint::saturate(-128) == -127;
    die "sat" unless FluxConstraint::saturate(128) == 127;
    print "  saturate: OK\n";

    my $fc = FluxConstraint->new([{ lo => 0, hi => 100, name => "test" }]);
    die "pass" unless $fc->check(50)->{passed};
    die "fail" if $fc->check(150)->{passed};
    print "  check: OK\n";

    my $fc2 = FluxConstraint->new([{lo=>0,hi=>10},{lo=>0,hi=>10},{lo=>0,hi=>10},{lo=>0,hi=>10}]);
    my $r = $fc2->check(50);
    die "sev" unless $r->{severity} == 3 && $r->{violated_count} == 4;
    print "  severity: OK\n";

    my $fc3 = FluxConstraint->from_preset("aviation");
    die "preset" unless @{$fc3->{constraints}} == 4;
    print "  presets: OK\n";

    print "  All tests pass\n";
'
=cut
