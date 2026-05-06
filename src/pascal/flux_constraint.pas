program FluxConstraintTest;

{  FLUX Constraint Engine — Free Pascal / Delphi
   Pure INT8 saturated constraint checking. Zero dependencies.
   Designed for agentic cooperation: readable, deterministic, portable.

   Compile: fpc flux_constraint.pas
            or: dcc32 flux_constraint.pas (Delphi)
   Run:     ./flux_constraint
}

{$mode objfpc}{$H+}
{$ifdef FPC}
  {$modeswitch result}
  {$warn 4056 off} { Converting pointers to unsigned }
{$endif}

interface

const
  INT8_MIN = -127;
  INT8_MAX = 127;

type
  TSeverity = (sevPass, sevCaution, sevWarning, sevCritical);

  TConstraint = record
    Lo: Integer;
    Hi: Integer;
    Name: string;
  end;

  TConstraintArray = array of TConstraint;

  TFluxResult = record
    ErrorMask: Integer;
    Severity: TSeverity;
    ViolatedLo: Integer;
    ViolatedHi: Integer;
    ViolatedCount: Integer;
    Passed: Boolean;
  end;

  TFluxResultArray = array of TFluxResult;

  TBatchStats = record
    PassCount: Integer;
    CautionCount: Integer;
    WarningCount: Integer;
    CriticalCount: Integer;
  end;

  TFluxChecker = class
  private
    FConstraints: TConstraintArray;
  public
    constructor Create(const AConstraints: TConstraintArray);
    function Check(Value: Integer): TFluxResult;
    function CheckBatch(const Values: array of Integer): TFluxResultArray;
    function Benchmark(Iterations: Integer = 1000000): Double;
    property Constraints: TConstraintArray read FConstraints;
  end;

function Saturate(Val: Integer): Integer;
function FromPreset(const Name: string): TFluxChecker;

implementation

uses
  SysUtils, DateUtils;

{ Saturate to INT8 [-127, 127] }
function Saturate(Val: Integer): Integer;
begin
  if Val < INT8_MIN then
    Result := INT8_MIN
  else if Val > INT8_MAX then
    Result := INT8_MAX
  else
    Result := Val;
end;

{ TFluxChecker }

constructor TFluxChecker.Create(const AConstraints: TConstraintArray);
var
  I: Integer;
begin
  inherited Create;
  if Length(AConstraints) = 0 then
    raise Exception.Create('Non-empty constraints required');
  if Length(AConstraints) > 8 then
    raise Exception.Create('Max 8 constraints (INT8 x8 flat bounds)');
  SetLength(FConstraints, Length(AConstraints));
  for I := 0 to High(AConstraints) do
  begin
    FConstraints[I].Lo := Saturate(AConstraints[I].Lo);
    FConstraints[I].Hi := Saturate(AConstraints[I].Hi);
    FConstraints[I].Name := AConstraints[I].Name;
  end;
end;

function TFluxChecker.Check(Value: Integer): TFluxResult;
var
  Val, Lo, Hi: Integer;
  I, NC, VC: Integer;
  LoFail, HiFail: Boolean;
  Bit: Integer;
begin
  Val := Saturate(Value);
  Result.ErrorMask := 0;
  Result.ViolatedLo := 0;
  Result.ViolatedHi := 0;
  VC := 0;

  for I := 0 to High(FConstraints) do
  begin
    Lo := Saturate(FConstraints[I].Lo);
    Hi := Saturate(FConstraints[I].Hi);
    LoFail := Val < Lo;
    HiFail := Val > Hi;
    Bit := 1 shl I;

    if LoFail or HiFail then
    begin
      Result.ErrorMask := Result.ErrorMask or Bit;
      Inc(VC);
    end;
    if LoFail then
      Result.ViolatedLo := Result.ViolatedLo or Bit;
    if HiFail then
      Result.ViolatedHi := Result.ViolatedHi or Bit;
  end;

  Result.ViolatedCount := VC;
  NC := Length(FConstraints);

  if VC = 0 then
    Result.Severity := sevPass
  else if VC <= NC div 4 then
    Result.Severity := sevCaution
  else if VC <= NC div 2 then
    Result.Severity := sevWarning
  else
    Result.Severity := sevCritical;

  Result.Passed := (Result.Severity = sevPass);
end;

function TFluxChecker.CheckBatch(const Values: array of Integer): TFluxResultArray;
var
  I: Integer;
begin
  SetLength(Result, Length(Values));
  for I := 0 to High(Values) do
    Result[I] := Check(Values[I]);
end;

function TFluxChecker.Benchmark(Iterations: Integer): Double;
var
  T0: TDateTime;
  I: Integer;
  ElapsedMs: Double;
begin
  T0 := Now;
  for I := 0 to Iterations - 1 do
    Check((I mod 254) - 127);
  ElapsedMs := MilliSecondsBetween(Now, T0);
  if ElapsedMs > 0 then
    Result := Iterations * Length(FConstraints) / (ElapsedMs / 1000.0)
  else
    Result := 0;
end;

function FromPreset(const Name: string): TFluxChecker;
var
  CS: TConstraintArray;
begin
  if SameText(Name, 'aviation') then
  begin
    SetLength(CS, 4);
    CS[0] := (Lo: -55; Hi: 70; Name: 'cabin_temp_C');
    CS[1] := (Lo: 75; Hi: 101; Name: 'cabin_pressure_kPa');
    CS[2] := (Lo: 0; Hi: 100; Name: 'fuel_flow_pct');
    CS[3] := (Lo: 60; Hi: 100; Name: 'hydraulic_pct');
  end
  else if SameText(Name, 'medical') then
  begin
    SetLength(CS, 4);
    CS[0] := (Lo: 36; Hi: 38; Name: 'body_temp_C');
    CS[1] := (Lo: 60; Hi: 100; Name: 'heart_rate_bpm');
    CS[2] := (Lo: 95; Hi: 100; Name: 'spo2_pct');
    CS[3] := (Lo: 80; Hi: 120; Name: 'bp_systolic_mmHg');
  end
  else if SameText(Name, 'maritime') then
  begin
    SetLength(CS, 4);
    CS[0] := (Lo: -2; Hi: 35; Name: 'sea_temp_C');
    CS[1] := (Lo: 50; Hi: 100; Name: 'hull_integrity_pct');
    CS[2] := (Lo: 0; Hi: 50; Name: 'wave_height_m');
    CS[3] := (Lo: 0; Hi: 80; Name: 'wind_speed_kn');
  end
  else if SameText(Name, 'automotive') then
  begin
    SetLength(CS, 4);
    CS[0] := (Lo: -40; Hi: 60; Name: 'battery_temp_C');
    CS[1] := (Lo: 0; Hi: 100; Name: 'soc_pct');
    CS[2] := (Lo: 0; Hi: 100; Name: 'charge_rate_pct');
    CS[3] := (Lo: 20; Hi: 80; Name: 'cabin_temp_C');
  end
  else if SameText(Name, 'energy') then
  begin
    SetLength(CS, 4);
    CS[0] := (Lo: 49; Hi: 51; Name: 'grid_freq_Hz_x10');
    CS[1] := (Lo: 95; Hi: 105; Name: 'voltage_pct');
    CS[2] := (Lo: 0; Hi: 80; Name: 'transformer_temp_C');
    CS[3] := (Lo: 0; Hi: 100; Name: 'line_load_pct');
  end
  else
    raise Exception.CreateFmt('Unknown preset: %s', [Name]);

  Result := TFluxChecker.Create(CS);
end;

{ Self-test program }

procedure RunTests;
var
  FC: TFluxChecker;
  R: TFluxResult;
  CS: TConstraintArray;
  Rate: Double;
begin
  WriteLn('FLUX Constraint Engine — Pascal');
  WriteLn('================================');

  { Test 1: Saturate }
  Assert(Saturate(-128) = -127, 'saturate(-128)');
  Assert(Saturate(128) = 127, 'saturate(128)');
  Assert(Saturate(0) = 0, 'saturate(0)');
  WriteLn('  saturate: OK');

  { Test 2: Pass }
  SetLength(CS, 1);
  CS[0] := (Lo: 0; Hi: 100; Name: 'test');
  FC := TFluxChecker.Create(CS);
  R := FC.Check(50);
  Assert(R.Passed, 'should pass');
  WriteLn('  single pass: OK');

  { Test 3: Fail }
  R := FC.Check(150);
  Assert(not R.Passed, 'should fail');
  Assert(R.ErrorMask = 1, 'error mask should be 1');
  WriteLn('  single fail: OK');

  { Test 4: Critical }
  SetLength(CS, 4);
  CS[0] := (Lo: 0; Hi: 10; Name: 'a');
  CS[1] := (Lo: 0; Hi: 10; Name: 'b');
  CS[2] := (Lo: 0; Hi: 10; Name: 'c');
  CS[3] := (Lo: 0; Hi: 10; Name: 'd');
  FC.Free;
  FC := TFluxChecker.Create(CS);
  R := FC.Check(50);
  Assert(R.Severity = sevCritical, 'should be critical');
  Assert(R.ViolatedCount = 4, 'all 4 should fail');
  WriteLn('  severity critical: OK');

  { Test 5: Preset }
  FC.Free;
  FC := FromPreset('aviation');
  Assert(Length(FC.Constraints) = 4, 'aviation should have 4');
  WriteLn('  preset loading: OK');

  { Test 6: Batch }
  R := FC.Check(25);
  WriteLn(Format('  aviation check(25): mask=%d passed=%s',
    [R.ErrorMask, BoolToStr(R.Passed, True)]));

  { Benchmark }
  Rate := FC.Benchmark();
  WriteLn(Format('  Benchmark: %.1fM checks/sec', [Rate / 1e6]));

  FC.Free;
  WriteLn('  All tests pass');
end;

begin
  try
    RunTests;
  except
    on E: Exception do
    begin
      WriteLn('FAIL: ', E.Message);
      Halt(1);
    end;
  end;
end.
