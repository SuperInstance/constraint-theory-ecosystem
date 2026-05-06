--  FLUX Constraint Engine — Ada 2012
--  Safety-critical INT8 saturated constraint checking.
--  Ravenscar-compatible, DO-178C ready.

with Interfaces; use Interfaces;

package Flux_Constraint is

   INT8_Min : constant Integer_8 := -127;
   INT8_Max : constant Integer_8 := 127;

   type Severity_Level is (Pass, Caution, Warning, Critical);
   pragma Ordered (Severity_Level);

   type Constraint_Bounds is record
      Lo : Integer_8;
      Hi : Integer_8;
   end record;

   type Constraint_Array is array (Natural range <>) of Constraint_Bounds;
   --  Max 8 constraints

   type Flux_Result is record
      Error_Mask    : Unsigned_8 := 0;
      Violated_Lo   : Unsigned_8 := 0;
      Violated_Hi   : Unsigned_8 := 0;
      Violated_Count : Natural   := 0;
      Severity      : Severity_Level := Pass;
      Passed        : Boolean    := True;
   end record;

   function Saturate (Val : Integer) return Integer_8;
   --  Clamp to [-127, 127]

   function Check
     (Constraints : Constraint_Array;
      Value       : Integer) return Flux_Result;
   --  Check value against all constraints

   function Check_Batch
     (Constraints : Constraint_Array;
      Values      : Integer_Array) return Result_Array;
   --  Batch check

private

   type Integer_Array is array (Natural range <>) of Integer;
   type Result_Array is array (Natural range <>) of Flux_Result;

end Flux_Constraint;
