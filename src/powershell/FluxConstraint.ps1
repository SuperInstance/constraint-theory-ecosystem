# FLUX Constraint Engine — PowerShell
# Pure INT8 saturated constraint checking. Zero dependencies.

function Saturate-Int8 {
    param([int]$Value)
    [System.Math]::Max(-127, [System.Math]::Min(127, $Value))
}

function Test-FluxConstraint {
    param(
        [Parameter(Mandatory)]
        [int]$Value,
        [Parameter(Mandatory)]
        [array]$Constraints  # @( @{Lo=0; Hi=100}, ... )
    )

    $val = Saturate-Int8 $Value
    $errorMask = 0
    $violatedLo = 0
    $violatedHi = 0
    $violatedCount = 0

    for ($i = 0; $i -lt $Constraints.Count; $i++) {
        $c = $Constraints[$i]
        $lo = Saturate-Int8 $c.Lo
        $hi = Saturate-Int8 $c.Hi
        $loFail = $val -lt $lo
        $hiFail = $val -gt $hi

        if ($loFail -or $hiFail) {
            $errorMask = $errorMask -bor (1 -shl $i)
            $violatedCount++
        }
        if ($loFail) { $violatedLo = $violatedLo -bor (1 -shl $i) }
        if ($hiFail) { $violatedHi = $violatedHi -bor (1 -shl $i) }
    }

    $nc = $Constraints.Count
    $severity = if ($violatedCount -eq 0) { 0 }
                elseif ($violatedCount -le [math]::Floor($nc / 4)) { 1 }
                elseif ($violatedCount -le [math]::Floor($nc / 2)) { 2 }
                else { 3 }

    [PSCustomObject]@{
        ErrorMask     = $errorMask
        Severity      = $severity
        ViolatedLo    = $violatedLo
        ViolatedHi    = $violatedHi
        ViolatedCount = $violatedCount
        Passed        = ($violatedCount -eq 0)
    }
}

# Self-test
Write-Host "FLUX Constraint Engine — PowerShell"
Write-Host "==================================="

assert (Saturate-Int8 -128 -eq -127) "saturate min"
assert (Saturate-Int8 128 -eq 127) "saturate max"
Write-Host "  saturate: OK"

$r = Test-FluxConstraint -Value 50 -Constraints @(,@(@{Lo=0; Hi=100}))
assert $r.Passed "pass"
Write-Host "  check: OK"

Write-Host "  All tests pass"
