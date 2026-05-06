#!/usr/bin/env perl
use strict;
use warnings;
use JSON::PP;
use lib 'src/perl';
use FluxConstraint;

my $json = do { local $/; open my $f, '<', 'tools/golden_vectors.json' or die $!; <$f> };
my $vectors = decode_json($json);
my $mismatches = 0;

for my $v (@$vectors) {
    my $cs = [map { { lo => $_->{lo}, hi => $_->{hi}, name => '' } } @{$v->{constraints}}];
    my $fc = FluxConstraint->new($cs);
    my $r = $fc->check($v->{value});
    my $exp = $v->{expected};
    if ($r->{error_mask} != $exp->{error_mask} || $r->{passed} ne ($exp->{passed} ? 1 : '')) {
        $mismatches++;
        print "MISMATCH #$v->{id}\n" if $mismatches <= 5;
    }
}

print "\nPerl: " . scalar(@$vectors) . " vectors, $mismatches mismatches\n";
exit($mismatches > 0 ? 1 : 0);
