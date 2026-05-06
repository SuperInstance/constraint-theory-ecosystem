--  FLUX Constraint Engine — Ada 2012 Implementation

with Interfaces; use Interfaces;

package body Flux_Constraint is

   function Saturate (Val : Integer) return Integer_8 is
   begin
      if Val < Integer (INT8_Min) then
         return INT8_Min;
      elsif Val > Integer (INT8_Max) then
         return INT8_Max;
      else
         return Integer_8 (Val);
      end if;
   end Saturate;

   function Check
     (Constraints : Constraint_Array;
      Value       : Integer) return Flux_Result
   is
      Val   : Integer_8 := Saturate (Value);
      R     : Flux_Result;
      Count : Natural := 0;
   begin
      for I in Constraints'Range loop
         declare
            C : Constraint_Bounds := Constraints (I);
            Bit : Unsigned_8 := Shift_Left (1, Unsigned_8 (I));
            Lo_Fail : Boolean := Integer (Val) < Integer (C.Lo);
            Hi_Fail : Boolean := Integer (Val) > Integer (C.Hi);
         begin
            if Lo_Fail or Hi_Fail then
               R.Error_Mask := R.Error_Mask or Bit;
               Count := Count + 1;
            end if;
            if Lo_Fail then
               R.Violated_Lo := R.Violated_Lo or Bit;
            end if;
            if Hi_Fail then
               R.Violated_Hi := R.Violated_Hi or Bit;
            end if;
         end;
      end loop;

      R.Violated_Count := Count;
      R.Passed := (Count = 0);

      declare
         NC : constant Natural := Constraints'Length;
      begin
         if Count = 0 then
            R.Severity := Pass;
         elsif Count <= NC / 4 then
            R.Severity := Caution;
         elsif Count <= NC / 2 then
            R.Severity := Warning;
         else
            R.Severity := Critical;
         end if;
      end;

      return R;
   end Check;

   function Check_Batch
     (Constraints : Constraint_Array;
      Values      : Integer_Array) return Result_Array
   is
      Results : Result_Array (Values'Range);
   begin
      for I in Values'Range loop
         Results (I) := Check (Constraints, Values (I));
      end loop;
      return Results;
   end Check_Batch;

end Flux_Constraint;

--  Self-test (compile with: gnatmake flux_constraint.adb)
with Ada.Text_IO; use Ada.Text_IO;
with Flux_Constraint; use Flux_Constraint;

procedure Flux_Test is
   Cs : Constraint_Array (0..0) := (0 => (Lo => 0, Hi => 100));
   R  : Flux_Result;
begin
   Put_Line ("FLUX Constraint Engine - Ada");
   Put_Line ("============================");

   --  Test saturate
   pragma Assert (Saturate (-128) = INT8_Min);
   pragma Assert (Saturate (128)  = INT8_Max);
   pragma Assert (Saturate (0)    = 0);
   Put_Line ("  saturate: OK");

   --  Test pass
   R := Check (Cs, 50);
   pragma Assert (R.Passed);
   Put_Line ("  pass: OK");

   --  Test fail
   R := Check (Cs, 150);
   pragma Assert (not R.Passed);
   pragma Assert (R.Error_Mask = 1);
   Put_Line ("  fail: OK");

   --  Multi-constraint
   declare
      Cs2 : Constraint_Array (0..3) :=
        (0 => (Lo => 0, Hi => 10),
         1 => (Lo => 0, Hi => 10),
         2 => (Lo => 0, Hi => 10),
         3 => (Lo => 0, Hi => 10));
   begin
      R := Check (Cs2, 50);
      pragma Assert (R.Severity = Critical);
      pragma Assert (R.Violated_Count = 4);
      Put_Line ("  severity: OK");
   end;

   Put_Line ("  All tests pass");
end Flux_Test;
