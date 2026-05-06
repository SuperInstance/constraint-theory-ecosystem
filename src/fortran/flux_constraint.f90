!     FLUX Constraint Engine — Fortran 2008
!     Pure INT8 saturated constraint checking. Zero dependencies.

module flux_constraint
    implicit none
    private
    public :: saturate, flux_check, flux_result, constraint_type

    integer, parameter :: INT8_MIN = -127
    integer, parameter :: INT8_MAX = 127

    type constraint_type
        integer :: lo, hi
        character(len=32) :: name
    end type

    type flux_result
        integer :: error_mask = 0
        integer :: violated_lo = 0
        integer :: violated_hi = 0
        integer :: violated_count = 0
        integer :: severity = 0     ! 0=pass 1=caution 2=warning 3=critical
        logical :: passed = .true.
    end type

contains

    function saturate(val) result(res)
        integer, intent(in) :: val
        integer :: res
        if (val < INT8_MIN) then
            res = INT8_MIN
        else if (val > INT8_MAX) then
            res = INT8_MAX
        else
            res = val
        end if
    end function

    function flux_check(constraints, value) result(r)
        type(constraint_type), intent(in) :: constraints(:)
        integer, intent(in) :: value
        type(flux_result) :: r
        integer :: val, i, nc, lo_sat, hi_sat
        logical :: lo_fail, hi_fail

        val = saturate(value)
        r%error_mask = 0
        r%violated_lo = 0
        r%violated_hi = 0
        r%violated_count = 0
        r%passed = .true.

        do i = 1, size(constraints)
            lo_sat = saturate(constraints(i)%lo)
            hi_sat = saturate(constraints(i)%hi)
            lo_fail = val < lo_sat
            hi_fail = val > hi_sat

            if (lo_fail .or. hi_fail) then
                r%error_mask = ior(r%error_mask, ishft(1, i-1))
                r%violated_count = r%violated_count + 1
            end if
            if (lo_fail) r%violated_lo = ior(r%violated_lo, ishft(1, i-1))
            if (hi_fail) r%violated_hi = ior(r%violated_hi, ishft(1, i-1))
        end do

        nc = size(constraints)
        r%passed = (r%violated_count == 0)

        if (r%violated_count == 0) then
            r%severity = 0
        else if (r%violated_count <= nc / 4) then
            r%severity = 1
        else if (r%violated_count <= nc / 2) then
            r%severity = 2
        else
            r%severity = 3
        end if
    end function

end module

! Self-test program
program flux_test
    use flux_constraint
    implicit none
    type(constraint_type) :: cs(1), cs4(4)
    type(flux_result) :: r

    print *, "FLUX Constraint Engine - Fortran"
    print *, "================================"

    ! Saturate
    if (saturate(-128) /= -127 .or. saturate(128) /= 127) stop 1
    print *, "  saturate: OK"

    ! Pass
    cs(1) = constraint_type(0, 100, "test")
    r = flux_check(cs, 50)
    if (.not. r%passed) stop 1
    print *, "  pass: OK"

    ! Fail
    r = flux_check(cs, 150)
    if (r%passed .or. r%error_mask /= 1) stop 1
    print *, "  fail: OK"

    ! Critical
    cs4 = [constraint_type(0,10,"a"), constraint_type(0,10,"b"), &
            constraint_type(0,10,"c"), constraint_type(0,10,"d")]
    r = flux_check(cs4, 50)
    if (r%severity /= 3 .or. r%violated_count /= 4) stop 1
    print *, "  severity: OK"

    print *, "  All tests pass"
end program
