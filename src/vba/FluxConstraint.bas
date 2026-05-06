' FLUX Constraint Engine — VBA (Excel/Access)
' Pure INT8 saturated constraint checking.
' Because engineers live in Excel, and Excel deserves constraints.

Option Explicit

Private Const INT8_MIN As Long = -127
Private Const INT8_MAX As Long = 127

Public Function Saturate(val As Long) As Long
    If val < INT8_MIN Then
        Saturate = INT8_MIN
    ElseIf val > INT8_MAX Then
        Saturate = INT8_MAX
    Else
        Saturate = val
    End If
End Function

Public Function FluxCheck(constraints As Variant, value As Long) As Variant
    ' constraints: Nx2 array [[lo1, hi1], [lo2, hi2], ...]
    ' Returns: Array(errorMask, severity, violatedCount, passed)
    
    Dim val As Long: val = Saturate(value)
    Dim errorMask As Long: errorMask = 0
    Dim violatedCount As Long: violatedCount = 0
    Dim i As Long, nc As Long
    Dim lo As Long, hi As Long
    Dim loFail As Boolean, hiFail As Boolean
    
    nc = UBound(constraints, 1) - LBound(constraints, 1) + 1
    
    For i = LBound(constraints, 1) To UBound(constraints, 1)
        lo = Saturate(constraints(i, 1))
        hi = Saturate(constraints(i, 2))
        loFail = (val < lo)
        hiFail = (val > hi)
        
        If loFail Or hiFail Then
            errorMask = errorMask Or (2 ^ (i - LBound(constraints, 1)))
            violatedCount = violatedCount + 1
        End If
    Next i
    
    Dim sev As Long
    If violatedCount = 0 Then
        sev = 0
    ElseIf violatedCount <= nc \ 4 Then
        sev = 1
    ElseIf violatedCount <= nc \ 2 Then
        sev = 2
    Else
        sev = 3
    End If
    
    Dim result(0 To 3) As Variant
    result(0) = errorMask
    result(1) = sev
    result(2) = violatedCount
    result(3) = (violatedCount = 0)
    
    FluxCheck = result
End Function

' Excel worksheet function: =FLUX_CHECK(A1, 0, 100)
' Returns "PASS" or "FAIL: severity X"
Public Function FLUX_CHECK(value As Long, lo As Long, hi As Long) As String
    Dim cs(1 To 1, 1 To 2) As Long
    cs(1, 1) = lo
    cs(1, 2) = hi
    Dim r As Variant
    r = FluxCheck(cs, value)
    If r(3) Then
        FLUX_CHECK = "PASS"
    Else
        FLUX_CHECK = "FAIL: severity " & r(1)
    End If
End Function

' Self-test
Public Sub TestFlux()
    Debug.Print "FLUX Constraint Engine - VBA"
    Debug.Print "============================"
    
    Debug.Assert Saturate(-128) = -127
    Debug.Assert Saturate(128) = 127
    Debug.Print "  saturate: OK"
    
    Dim cs(1 To 1, 1 To 2) As Long
    cs(1, 1) = 0: cs(1, 2) = 100
    Dim r As Variant
    r = FluxCheck(cs, 50)
    Debug.Assert r(3) = True
    Debug.Print "  pass: OK"
    
    r = FluxCheck(cs, 150)
    Debug.Assert r(3) = False
    Debug.Assert r(0) = 1
    Debug.Print "  fail: OK"
    
    Debug.Print "  All tests pass"
End Sub
