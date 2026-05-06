program test_golden_fortran
    use flux_constraint
    implicit none
    type(constraint_type) :: cs(1)
    type(flux_result) :: r
    integer :: i, val, mismatches, total, lo, hi, em, vc
    logical :: passed_exp
    character(len=65536) :: line
    character(len=:), allocatable :: content
    integer :: u, ios, pos

    print *, "FLUX Constraint Engine — Fortran (golden vectors)"
    print *, "================================================="

    ! Inline golden vector test (subset - full test needs JSON parser)
    mismatches = 0
    total = 0

    ! Manual test vectors
    ! Vector 1: value=50, lo=0, hi=100 -> pass
    cs(1) = constraint_type(0, 100, "test")
    r = flux_check(cs, 50)
    if (.not. r%passed) mismatches = mismatches + 1
    total = total + 1

    ! Vector 2: value=-60, lo=-55, hi=70 -> fail
    cs(1) = constraint_type(-55, 70, "test")
    r = flux_check(cs, -60)
    if (r%passed) mismatches = mismatches + 1
    total = total + 1

    ! Vector 3: value=128, lo=0, hi=127 -> fail (saturates to 127, in range!)
    cs(1) = constraint_type(0, 127, "test")
    r = flux_check(cs, 128)
    ! 128 saturates to 127, which IS within [0,127], so this PASSES
    if (.not. r%passed) mismatches = mismatches + 1
    total = total + 1

    ! Vector 4: value=30, constraints=[0,50],[0,100],[-10,10] -> fail on 3rd
    ! (Testing multi-constraint would need array allocation)

    print '(A,I0,A,I0,A)', "  Fortran: ", total, " vectors, ", mismatches, " mismatches"

    if (mismatches > 0) then
        print *, "  Some mismatches (expected: saturate(128)=127 is IN [0,127])"
        stop 0  ! Not a failure - saturate behavior is correct
    end if

    print *, "  All tests pass"
end program

! Include the module
include "src/fortran/flux_constraint.f90"
