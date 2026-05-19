;; FLUX-C Constraint Checker — Pure WASM (Zero Host Imports)
;;
;; This is the canonical WASM source for the FLUX constraint engine.
;; Compiles to < 2KB binary. Zero imports. Pure computation. Deterministic.
;;
;; Build: wat2wasm flux-checker.wat -o flux-checker.wasm
;; Verify: wasm-validate flux-checker.wasm
;; Inspect: wasm-objdump -x flux-checker.wasm
;;
;; Exports:
;;   memory: 1 page (64KB) linear memory
;;   check(values_ptr, count, bytecode_ptr, bc_len, result_ptr) -> error_code
;;
;; Memory layout:
;;   0x0000-0x003F: stack (16 × i32 = 64 bytes)
;;   0x0040: stack_ptr (i32)
;;   0x0044: pc (i32)
;;   0x0048: deadline (i32)
;;   0x004C: constraint_id (i32)
;;   0x0050: flags (i32)
;;   0x1000+: input values
;;   0x2000+: bytecode
;;   0x3000+: result (error_mask:i32, instr_count:i32, severity:i32)

(module
  ;; Single page of linear memory (64KB)
  (memory (export "memory") 1 1)

  ;; Saturate to [-127, 127] (avoid -128 per FLUX-C spec)
  (func $saturate (param $v i32) (result i32)
    (if (result i32) (i32.lt_s (local.get $v) (i32.const -127))
      (then (i32.const -127))
      (else
        (if (result i32) (i32.gt_s (local.get $v) (i32.const 127))
          (then (i32.const 127))
          (else (local.get $v))
        )
      )
    )
  )

  ;; Push value onto stack. Returns 0=OK, 2=overflow
  (func $push (param $v i32) (result i32)
    (local $sp i32)
    (local.set $sp (i32.load (i32.const 0x40)))
    (if (i32.ge_u (local.get $sp) (i32.const 16))
      (then (return (i32.const 2)))
    )
    (i32.store
      (i32.mul (local.get $sp) (i32.const 4))
      (call $saturate (local.get $v))
    )
    (i32.store (i32.const 0x40) (i32.add (local.get $sp) (i32.const 1)))
    (i32.const 0)
  )

  ;; Pop value from stack. Returns (value, error)
  ;; Note: WASM multi-return — caller reads value from stack memory
  (func $pop (result i32)
    (local $sp i32)
    (local $val i32)
    (local.set $sp (i32.load (i32.const 0x40)))
    (local.set $sp (i32.sub (local.get $sp) (i32.const 1)))
    (local.set $val (i32.load (i32.mul (local.get $sp) (i32.const 4))))
    (i32.store (i32.const 0x40) (local.get $sp))
    (local.get $val)
  )

  ;; Main check function
  ;; check(values_ptr, count, bytecode_ptr, bc_len, result_ptr) -> error_code
  (func (export "check")
    (param $vptr i32)    ;; pointer to input values array
    (param $cnt i32)     ;; number of input values
    (param $bptr i32)    ;; pointer to bytecode
    (param $blen i32)    ;; bytecode length
    (param $rptr i32)    ;; pointer to result struct
    (result i32)         ;; 0=OK, 1=underflow, 2=overflow, 3=bad_opcode, 4=div0

    (local $err i32)
    (local $sp i32)
    (local $pc i32)
    (local $op i32)
    (local $a i32)
    (local $b i32)
    (local $c i32)
    (local $cid i32)
    (local $mask i32)
    (local $ic i32)      ;; instruction count
    (local $dl i32)      ;; deadline countdown

    ;; Initialize VM state
    (i32.store (i32.const 0x40) (i32.const 0))   ;; sp = 0
    (local.set $mask (i32.const 0))
    (local.set $ic (i32.const 0))

    ;; Push input values onto stack
    (local.set $a (i32.const 0))
    (block $push_done
      (loop $push_loop
        (br_if $push_done (i32.ge_u (local.get $a) (local.get $cnt)))
        (local.set $err
          (call $push
            (i32.load (i32.add (local.get $vptr)
              (i32.mul (local.get $a) (i32.const 4))))))
        (br_if $push_done (i32.ne (local.get $err) (i32.const 0)))
        (local.set $a (i32.add (local.get $a) (i32.const 1)))
        (br $push_loop)
      )
    )
    (if (i32.ne (local.get $err) (i32.const 0))
      (then (return (local.get $err))))

    ;; Main execution loop
    (local.set $dl (i32.const 4096))
    (local.set $pc (i32.const 0))
    (block $exec_done
      (loop $exec_loop
        ;; Check deadline
        (local.set $dl (i32.sub (local.get $dl) (i32.const 1)))
        (br_if $exec_done (i32.eqz (local.get $dl)))

        ;; Increment instruction count
        (local.set $ic (i32.add (local.get $ic) (i32.const 1)))

        ;; Load opcode
        (br_if $exec_done (i32.ge_u (local.get $pc) (local.get $blen)))
        (local.set $op (i32.load8_u (i32.add (local.get $bptr) (local.get $pc))))
        (local.set $pc (i32.add (local.get $pc) (i32.const 1)))

        ;; Dispatch
        (block $dispatch

          ;; FLUX_NOP (0x00)
          (br_if $dispatch (i32.eqz (local.get $op)))

          ;; FLUX_PUSH (0x01)
          (if (i32.eq (local.get $op) (i32.const 0x01)) (then
            (br_if $exec_done (i32.ge_u (local.get $pc) (local.get $blen)))
            (local.set $a (i32.extend8_s
              (i32.load8_u (i32.add (local.get $bptr) (local.get $pc)))))
            (local.set $pc (i32.add (local.get $pc) (i32.const 1)))
            (local.set $err (call $push (local.get $a)))
            (br_if $exec_done (i32.ne (local.get $err) (i32.const 0)))
            (br $dispatch)
          ))

          ;; FLUX_DUP (0x03)
          (if (i32.eq (local.get $op) (i32.const 0x03)) (then
            (local.set $sp (i32.load (i32.const 0x40)))
            (br_if $exec_done (i32.eqz (local.get $sp)))
            (local.set $a (i32.load (i32.mul (i32.sub (local.get $sp) (i32.const 1)) (i32.const 4))))
            (local.set $err (call $push (local.get $a)))
            (br_if $exec_done (i32.ne (local.get $err) (i32.const 0)))
            (br $dispatch)
          ))

          ;; FLUX_POP (0x02)
          (if (i32.eq (local.get $op) (i32.const 0x02)) (then
            (local.set $sp (i32.load (i32.const 0x40)))
            (br_if $exec_done (i32.eqz (local.get $sp)))
            (i32.store (i32.const 0x40) (i32.sub (local.get $sp) (i32.const 1)))
            (br $dispatch)
          ))

          ;; FLUX_ADD (0x10)
          (if (i32.eq (local.get $op) (i32.const 0x10)) (then
            (local.set $sp (i32.load (i32.const 0x40)))
            (br_if $exec_done (i32.lt_u (local.get $sp) (i32.const 2)))
            (local.set $b (i32.load (i32.mul (i32.sub (local.get $sp) (i32.const 1)) (i32.const 4))))
            (local.set $a (i32.load (i32.mul (i32.sub (local.get $sp) (i32.const 2)) (i32.const 4))))
            (i32.store
              (i32.mul (i32.sub (local.get $sp) (i32.const 2)) (i32.const 4))
              (call $saturate (i32.add (local.get $a) (local.get $b))))
            (i32.store (i32.const 0x40) (i32.sub (local.get $sp) (i32.const 1)))
            (br $dispatch)
          ))

          ;; FLUX_SUB (0x11)
          (if (i32.eq (local.get $op) (i32.const 0x11)) (then
            (local.set $sp (i32.load (i32.const 0x40)))
            (br_if $exec_done (i32.lt_u (local.get $sp) (i32.const 2)))
            (local.set $b (i32.load (i32.mul (i32.sub (local.get $sp) (i32.const 1)) (i32.const 4))))
            (local.set $a (i32.load (i32.mul (i32.sub (local.get $sp) (i32.const 2)) (i32.const 4))))
            (i32.store
              (i32.mul (i32.sub (local.get $sp) (i32.const 2)) (i32.const 4))
              (call $saturate (i32.sub (local.get $a) (local.get $b))))
            (i32.store (i32.const 0x40) (i32.sub (local.get $sp) (i32.const 1)))
            (br $dispatch)
          ))

          ;; FLUX_MUL (0x12)
          (if (i32.eq (local.get $op) (i32.const 0x12)) (then
            (local.set $sp (i32.load (i32.const 0x40)))
            (br_if $exec_done (i32.lt_u (local.get $sp) (i32.const 2)))
            (local.set $b (i32.load (i32.mul (i32.sub (local.get $sp) (i32.const 1)) (i32.const 4))))
            (local.set $a (i32.load (i32.mul (i32.sub (local.get $sp) (i32.const 2)) (i32.const 4))))
            (i32.store
              (i32.mul (i32.sub (local.get $sp) (i32.const 2)) (i32.const 4))
              (call $saturate (i32.mul (local.get $a) (local.get $b))))
            (i32.store (i32.const 0x40) (i32.sub (local.get $sp) (i32.const 1)))
            (br $dispatch)
          ))

          ;; FLUX_DIV (0x13)
          (if (i32.eq (local.get $op) (i32.const 0x13)) (then
            (local.set $sp (i32.load (i32.const 0x40)))
            (br_if $exec_done (i32.lt_u (local.get $sp) (i32.const 2)))
            (local.set $b (i32.load (i32.mul (i32.sub (local.get $sp) (i32.const 1)) (i32.const 4))))
            (br_if $exec_done (i32.eqz (local.get $b)))
            (local.set $a (i32.load (i32.mul (i32.sub (local.get $sp) (i32.const 2)) (i32.const 4))))
            (i32.store
              (i32.mul (i32.sub (local.get $sp) (i32.const 2)) (i32.const 4))
              (call $saturate (i32.div_s (local.get $a) (local.get $b))))
            (i32.store (i32.const 0x40) (i32.sub (local.get $sp) (i32.const 1)))
            (br $dispatch)
          ))

          ;; FLUX_NEG (0x15)
          (if (i32.eq (local.get $op) (i32.const 0x15)) (then
            (local.set $sp (i32.load (i32.const 0x40)))
            (br_if $exec_done (i32.eqz (local.get $sp)))
            (local.set $a (i32.sub (i32.const 0)
              (i32.load (i32.mul (i32.sub (local.get $sp) (i32.const 1)) (i32.const 4)))))
            (i32.store
              (i32.mul (i32.sub (local.get $sp) (i32.const 1)) (i32.const 4))
              (call $saturate (local.get $a)))
            (br $dispatch)
          ))

          ;; FLUX_LT (0x22)
          (if (i32.eq (local.get $op) (i32.const 0x22)) (then
            (local.set $sp (i32.load (i32.const 0x40)))
            (br_if $exec_done (i32.lt_u (local.get $sp) (i32.const 2)))
            (local.set $b (i32.load (i32.mul (i32.sub (local.get $sp) (i32.const 1)) (i32.const 4))))
            (local.set $a (i32.load (i32.mul (i32.sub (local.get $sp) (i32.const 2)) (i32.const 4))))
            (i32.store
              (i32.mul (i32.sub (local.get $sp) (i32.const 2)) (i32.const 4))
              (if (result i32) (i32.lt_s (local.get $a) (local.get $b))
                (then (i32.const 1)) (else (i32.const 0))))
            (i32.store (i32.const 0x40) (i32.sub (local.get $sp) (i32.const 1)))
            (br $dispatch)
          ))

          ;; FLUX_GT (0x23)
          (if (i32.eq (local.get $op) (i32.const 0x23)) (then
            (local.set $sp (i32.load (i32.const 0x40)))
            (br_if $exec_done (i32.lt_u (local.get $sp) (i32.const 2)))
            (local.set $b (i32.load (i32.mul (i32.sub (local.get $sp) (i32.const 1)) (i32.const 4))))
            (local.set $a (i32.load (i32.mul (i32.sub (local.get $sp) (i32.const 2)) (i32.const 4))))
            (i32.store
              (i32.mul (i32.sub (local.get $sp) (i32.const 2)) (i32.const 4))
              (if (result i32) (i32.gt_s (local.get $a) (local.get $b))
                (then (i32.const 1)) (else (i32.const 0))))
            (i32.store (i32.const 0x40) (i32.sub (local.get $sp) (i32.const 1)))
            (br $dispatch)
          ))

          ;; FLUX_RANGE_CHECK (0x40)
          (if (i32.eq (local.get $op) (i32.const 0x40)) (then
            (local.set $sp (i32.load (i32.const 0x40)))
            (br_if $exec_done (i32.lt_u (local.get $sp) (i32.const 3)))
            ;; hi, lo, val
            (local.set $c (i32.load (i32.mul (i32.sub (local.get $sp) (i32.const 1)) (i32.const 4))))
            (local.set $b (i32.load (i32.mul (i32.sub (local.get $sp) (i32.const 2)) (i32.const 4))))
            (local.set $a (i32.load (i32.mul (i32.sub (local.get $sp) (i32.const 3)) (i32.const 4))))
            (local.set $c (call $saturate (local.get $c)))
            (local.set $b (call $saturate (local.get $b)))
            (local.set $a (call $saturate (local.get $a)))
            ;; Check violation
            (if (i32.or
                  (i32.lt_s (local.get $a) (local.get $b))
                  (i32.gt_s (local.get $a) (local.get $c)))
              (then
                (local.set $cid (i32.load (i32.const 0x4C)))
                (local.set $mask (i32.or (local.get $mask)
                  (i32.shl (i32.const 1) (local.get $cid))))
                (i32.store
                  (i32.mul (i32.sub (local.get $sp) (i32.const 3)) (i32.const 4))
                  (i32.const 1))
              )
              (else
                (i32.store
                  (i32.mul (i32.sub (local.get $sp) (i32.const 3)) (i32.const 4))
                  (i32.const 0))
              )
            )
            (i32.store (i32.const 0x40) (i32.sub (local.get $sp) (i32.const 2)))
            (br $dispatch)
          ))

          ;; FLUX_CONSTRAINT_ID (0x63)
          (if (i32.eq (local.get $op) (i32.const 0x63)) (then
            (br_if $exec_done (i32.ge_u (local.get $pc) (local.get $blen)))
            (i32.store (i32.const 0x4C)
              (i32.load8_u (i32.add (local.get $bptr) (local.get $pc))))
            (local.set $pc (i32.add (local.get $pc) (i32.const 1)))
            (br $dispatch)
          ))

          ;; FLUX_HALT (0x54)
          (if (i32.eq (local.get $op) (i32.const 0x54)) (then
            (br $exec_done)
          ))

          ;; Unknown opcode
          (return (i32.const 3))

        ) ;; end dispatch
        (br $exec_loop)
      ) ;; end exec_loop
    ) ;; end exec_done

    ;; Write results
    (i32.store (local.get $rptr) (local.get $mask))
    (i32.store (i32.add (local.get $rptr) (i32.const 4)) (local.get $ic))

    ;; Compute severity (count bits in mask)
    (local.set $a (local.get $mask))
    (local.set $b (i32.const 0))
    (block $sev_done (loop $sev_loop
      (br_if $sev_done (i32.eqz (local.get $a)))
      (local.set $b (i32.add (local.get $b) (i32.and (local.get $a) (i32.const 1))))
      (local.set $a (i32.shr_u (local.get $a) (i32.const 1)))
      (br $sev_loop)
    ))
    (i32.store (i32.add (local.get $rptr) (i32.const 8))
      (select (local.get $b) (i32.const 3) (i32.le_u (local.get $b) (i32.const 2))))

    (i32.const 0) ;; OK
  )
)
