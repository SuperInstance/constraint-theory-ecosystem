<?php
require_once __DIR__ . '/../src/php/FluxConstraint.php';

$vectors = json_decode(file_get_contents(__DIR__ . '/golden_vectors.json'), true);
$mismatches = 0;

foreach ($vectors as $v) {
    $cs = array_map(fn($c) => ['lo' => $c['lo'], 'hi' => $c['hi'], 'name' => ''], $v['constraints']);
    $fc = new FluxConstraint($cs);
    $r = $fc->check($v['value']);
    $exp = $v['expected'];
    if ($r->error_mask !== $exp['error_mask'] || $r->isPass() !== $exp['passed']) {
        $mismatches++;
        if ($mismatches <= 5) echo "MISMATCH #{$v['id']}: value={$v['value']} got mask={$r->error_mask} expected={$exp['error_mask']}\n";
    }
}

echo "\nPHP: " . count($vectors) . " vectors, $mismatches mismatches\n";
exit($mismatches > 0 ? 1 : 0);
