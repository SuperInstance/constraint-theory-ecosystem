; FLUX Constraint Engine — x86_64 Assembly (Linux, NASM)
; INT8 saturated constraint checking at the metal.
; 3 instructions for saturate, branchless constraint comparison.

section .text
global _start

; int32_t saturate(int32_t val)
; rdi = val, returns in rax
saturate:
    mov eax, edi                ; eax = val
    cmp eax, -127               ; compare with INT8_MIN
    cmovl eax, [rel .int8_min]  ; if < -127, use -127
    cmp eax, 127                ; compare with INT8_MAX
    cmovg eax, [rel .int8_max]  ; if > 127, use 127
    ret

; int32_t flux_check(int32_t* bounds, int count, int32_t value)
; rdi = bounds array (lo,hi pairs), rsi = count, edx = value
; returns error_mask in rax
flux_check:
    push rbx
    push r12
    mov r12, rdi                ; r12 = bounds
    mov ecx, esi                ; ecx = count
    call saturate               ; saturate(value) in eax (uses edx)
    ; Actually, call saturate on edx
    mov edi, edx
    call saturate
    mov r8d, eax                ; r8d = saturated value

    xor eax, eax                ; error_mask = 0
    xor r9d, r9d                ; index = 0
    xor r10d, r10d              ; violated_count = 0

.loop:
    cmp r9d, ecx
    jge .done

    ; Load lo and hi
    mov r11d, [r12 + r9*8]      ; lo = bounds[i*2]
    mov ebx, [r12 + r9*8 + 4]   ; hi = bounds[i*2+1]

    ; Saturate bounds
    mov edi, r11d
    call saturate
    mov r11d, eax               ; r11d = sat_lo
    mov edi, ebx
    call saturate
    mov ebx, eax                ; ebx = sat_hi

    ; Compare
    cmp r8d, r11d               ; val < lo?
    setl dl
    cmp r8d, ebx                ; val > hi?
    setg bl
    or dl, bl                   ; lo_fail || hi_fail
    jz .next

    ; Set bit in error_mask
    mov edi, 1
    mov ecx, r9d
    shl edi, cl
    or eax, edi
    inc r10d

.next:
    inc r9d
    jmp .loop

.done:
    mov eax, eax                ; return error_mask
    pop r12
    pop rbx
    ret

section .rodata
.int8_min: dd -127
.int8_max: dd 127

section .data
test_bounds:
    dd 0, 100                   ; lo=0, hi=100

section .bss
result_str: resb 32

section .text
_start:
    ; Test saturate(-128) == -127
    mov edi, -128
    call saturate
    cmp eax, -127
    jne .fail

    ; Test saturate(128) == 127
    mov edi, 128
    call saturate
    cmp eax, 127
    jne .fail

    ; Test flux_check with value=50, bounds=[0,100]
    lea rdi, [rel test_bounds]
    mov esi, 1                  ; 1 constraint
    mov edx, 50                 ; value=50
    call flux_check
    cmp eax, 0                  ; should pass (mask=0)
    jne .fail

    ; Test flux_check with value=150
    lea rdi, [rel test_bounds]
    mov esi, 1
    mov edx, 150
    call flux_check
    cmp eax, 1                  ; should fail (mask=1)
    jne .fail

    ; Print success
    lea rsi, [rel .msg_ok]
    mov edx, 17
    mov edi, 1
    mov eax, 1                  ; sys_write
    syscall

    ; Exit 0
    xor edi, edi
    mov eax, 60                 ; sys_exit
    syscall

.fail:
    lea rsi, [rel .msg_fail]
    mov edx, 6
    mov edi, 1
    mov eax, 1
    syscall
    mov edi, 1
    mov eax, 60
    syscall

section .rodata
.msg_ok:   db "Assembly: ALL PASS", 10
.msg_fail: db "FAIL!", 10
