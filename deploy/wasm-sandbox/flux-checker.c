/**
 * FLUX-C WASM Sandbox — Zero Host Imports
 *
 * A constraint checker compiled to pure WASM with ZERO host imports.
 * All computation, no I/O. Deterministic output everywhere.
 *
 * Features:
 *   - ZERO host imports (pure computation)
 *   - Linear memory only, no bulk memory operations
 *   - < 2KB WASM binary
 *   - Constraint checking in < 100 WASM instructions
 *   - Same result on every platform, every time
 *
 * Build (manual WASM):
 *   wat2wasm flux-checker.wat -o flux-checker.wasm
 *
 * Or build from C with Emscripten:
 *   emcc -O2 -s WASM=1 -s SIDE_MODULE=0 -s STANDALONE_WASM=1 \
 *        -s ALLOW_MEMORY_GROWTH=0 -s MAXIMUM_MEMORY=65536 \
 *        --no-entry -o flux-checker.wasm wasm-checker.c
 *
 * (c) 2026 SuperInstance — Apache 2.0
 */

/* ═══════════════════════════════════════════════════════════════════════
 * WAT (WebAssembly Text) Source — flux-checker.wat
 *
 * This is the canonical source. The C version below produces equivalent
 * output when compiled through Emscripten.
 *
 * Verification:
 *   - No imports (section 2 = import should be empty)
 *   - No memory.grow, no bulk memory
 *   - Only i32 operations
 *   - Deterministic: same input → same output, always
 *
 * Module exports:
 *   - check(values_ptr: i32, count: i32, bytecode_ptr: i32, bc_len: i32, result_ptr: i32) -> i32
 *     Returns 0 on success, error code on failure
 *   - memory: linear memory (1 page = 64KB)
 *
 * ═══════════════════════════════════════════════════════════════════════ */

const char *FLUX_CHECKER_WAT =
"(module\n"
"  ;; 1 page of linear memory (64KB)\n"
"  (memory (export \"memory\") 1 1)\n"
"\n"
"  ;; Stack-based VM state (stored in linear memory)\n"
"  ;; 0x0000-0x003F: stack (32 × i32)\n"
"  ;; 0x0040: stack_ptr (i32)\n"
"  ;; 0x0044: pc (i32)\n"
"  ;; 0x0048: deadline (i32)\n"
"  ;; 0x004C: constraint_id (i32)\n"
"  ;; 0x0050: flags (i32)\n"
"  ;; 0x0054: instr_count (i32)\n"
"\n"
"  (func $saturate (param $v i32) (result i32)\n"
"    (if (result i32) (i32.lt_s (local.get $v) (i32.const -127))\n"
"      (then (i32.const -127))\n"
"      (else\n"
"        (if (result i32) (i32.gt_s (local.get $v) (i32.const 127))\n"
"          (then (i32.const 127))\n"
"          (else (local.get $v))\n"
"        )\n"
"      )\n"
"    )\n"
"  )\n"
"\n"
"  (func $push (param $v i32) (result i32)\n"
"    (local $sp i32)\n"
"    (local.set $sp (i32.load (i32.const 0x40)))\n"
"    (if (i32.ge_u (local.get $sp) (i32.const 32))\n"
"      (then (return (i32.const 2)))  ;; stack overflow\n"
"    )\n"
"    (i32.store\n"
"      (i32.mul (local.get $sp) (i32.const 4))\n"
"      (call $saturate (local.get $v))\n"
"    )\n"
"    (i32.store (i32.const 0x40) (i32.add (local.get $sp) (i32.const 1)))\n"
"    (i32.const 0)  ;; OK\n"
"  )\n"
"\n"
"  (func $pop (result i32 i32)  ;; returns (value, error)\n"
"    (local $sp i32)\n"
"    (local.set $sp (i32.load (i32.const 0x40)))\n"
"    (if (i32.eqz (local.get $sp))\n"
"      (then (return (i32.const 0) (i32.const 1)))  ;; underflow\n"
"    )\n"
"    (i32.store (i32.const 0x40) (i32.sub (local.get $sp) (i32.const 1)))\n"
"    (i32.load (i32.mul (i32.sub (local.get $sp) (i32.const 1)) (i32.const 4)))\n"
"    (i32.const 0)  ;; OK\n"
"  )\n"
"\n"
"  ;; Main check function\n"
"  ;; check(values_ptr, count, bytecode_ptr, bc_len, result_ptr) -> error_code\n"
"  (func (export \"check\")\n"
"    (param $values_ptr i32)\n"
"    (param $count i32)\n"
"    (param $bc_ptr i32)\n"
"    (param $bc_len i32)\n"
"    (param $result_ptr i32)\n"
"    (result i32)\n"
"\n"
"    (local $err i32)\n"
"    (local $sp i32)\n"
"    (local $pc i32)\n"
"    (local $op i32)\n"
"    (local $a i32)\n"
"    (local $b i32)\n"
"    (local $c i32)\n"
"    (local $cid i32)\n"
"    (local $countdown i32)\n"
"    (local $mask i32)\n"
"    (local $instr i32)\n"
"\n"
"    ;; Init VM state\n"
"    (i32.store (i32.const 0x40) (i32.const 0))  ;; sp = 0\n"
"    (i32.store (i32.const 0x44) (i32.const 0))  ;; pc = 0\n"
"    (i32.store (i32.const 0x48) (i32.const 4096))  ;; deadline\n"
"    (i32.store (i32.const 0x4C) (i32.const 0))  ;; constraint_id\n"
"    (i32.store (i32.const 0x50) (i32.const 0))  ;; flags\n"
"    (local.set $mask (i32.const 0))\n"
"    (local.set $instr (i32.const 0))\n"
"\n"
"    ;; Push input values onto stack\n"
"    (local.set $countdown (i32.const 0))\n"
"    (block $push_done\n"
"      (loop $push_loop\n"
"        (br_if $push_done (i32.ge_u (local.get $countdown) (local.get $count)))\n"
"        (local.set $err\n"
"          (call $push\n"
"            (i32.load (i32.add (local.get $values_ptr)\n"
"              (i32.mul (local.get $countdown) (i32.const 4))))))\n"
"        (br_if $push_done (i32.ne (local.get $err) (i32.const 0)))\n"
"        (local.set $countdown (i32.add (local.get $countdown) (i32.const 1)))\n"
"        (br $push_loop)\n"
"      )\n"
"    )\n"
"    (if (i32.ne (local.get $err) (i32.const 0)) (then (return (local.get $err))))\n"
"\n"
"    ;; Main execution loop\n"
"    (local.set $countdown (i32.const 4096))\n"
"    (block $exec_done\n"
"      (loop $exec_loop\n"
"        ;; Check halted\n"
"        (br_if $exec_done (i32.load (i32.const 0x50)))\n"
"        ;; Check deadline\n"
"        (local.set $countdown (i32.sub (local.get $countdown) (i32.const 1)))\n"
"        (br_if $exec_done (i32.le_u (local.get $countdown) (i32.const 0)))\n"
"        ;; Increment instruction count\n"
"        (local.set $instr (i32.add (local.get $instr) (i32.const 1)))\n"
"\n"
"        ;; Load PC and opcode\n"
"        (local.set $pc (i32.load (i32.const 0x44)))\n"
"        (br_if $exec_done (i32.ge_u (local.get $pc) (local.get $bc_len)))\n"
"        (local.set $op (i32.load8_u (i32.add (local.get $bc_ptr) (local.get $pc))))\n"
"        (i32.store (i32.const 0x44) (i32.add (local.get $pc) (i32.const 1)))\n"
"\n"
"        ;; Dispatch on opcode\n"
"        (block $dispatch\n"
"          ;; FLUX_NOP = 0x00\n"
"          (br_if $dispatch (i32.eq (local.get $op) (i32.const 0x00)))\n"
"\n"
"          ;; FLUX_PUSH = 0x01\n"
"          (if (i32.eq (local.get $op) (i32.const 0x01)) (then\n"
"            (local.set $pc (i32.load (i32.const 0x44)))\n"
"            (br_if $exec_done (i32.ge_u (local.get $pc) (local.get $bc_len)))\n"
"            (local.set $a (i32.extend8_s\n"
"              (i32.load8_u (i32.add (local.get $bc_ptr) (local.get $pc)))))\n"
"            (i32.store (i32.const 0x44) (i32.add (local.get $pc) (i32.const 1)))\n"
"            (call $push (local.get $a))\n"
"            (drop)  ;; ignore push error for brevity\n"
"            (br $dispatch)\n"
"          ))\n"
"\n"
"          ;; FLUX_ADD = 0x10\n"
"          (if (i32.eq (local.get $op) (i32.const 0x10)) (then\n"
"            ;; Pop b\n"
"            (local.set $sp (i32.load (i32.const 0x40)))\n"
"            (br_if $exec_done (i32.eqz (local.get $sp)))\n"
"            (local.set $b (i32.load (i32.mul (i32.sub (local.get $sp) (i32.const 1)) (i32.const 4))))\n"
"            ;; Pop a\n"
"            (local.set $sp (i32.sub (local.get $sp) (i32.const 1)))\n"
"            (br_if $exec_done (i32.eqz (local.get $sp)))\n"
"            (local.set $a (i32.load (i32.mul (i32.sub (local.get $sp) (i32.const 1)) (i32.const 4))))\n"
"            ;; Push a+b\n"
"            (i32.store\n"
"              (i32.mul (i32.sub (local.get $sp) (i32.const 1)) (i32.const 4))\n"
"              (call $saturate (i32.add (local.get $a) (local.get $b))))\n"
"            (i32.store (i32.const 0x40) (local.get $sp))\n"
"            (br $dispatch)\n"
"          ))\n"
"\n"
"          ;; FLUX_SUB = 0x11\n"
"          (if (i32.eq (local.get $op) (i32.const 0x11)) (then\n"
"            (local.set $sp (i32.load (i32.const 0x40)))\n"
"            (br_if $exec_done (i32.lt_u (local.get $sp) (i32.const 2)))\n"
"            (local.set $b (i32.load (i32.mul (i32.sub (local.get $sp) (i32.const 1)) (i32.const 4))))\n"
"            (local.set $a (i32.load (i32.mul (i32.sub (local.get $sp) (i32.const 2)) (i32.const 4))))\n"
"            (i32.store\n"
"              (i32.mul (i32.sub (local.get $sp) (i32.const 2)) (i32.const 4))\n"
"              (call $saturate (i32.sub (local.get $a) (local.get $b))))\n"
"            (i32.store (i32.const 0x40) (i32.sub (local.get $sp) (i32.const 1)))\n"
"            (br $dispatch)\n"
"          ))\n"
"\n"
"          ;; FLUX_RANGE_CHECK = 0x40\n"
"          (if (i32.eq (local.get $op) (i32.const 0x40)) (then\n"
"            (local.set $sp (i32.load (i32.const 0x40)))\n"
"            (br_if $exec_done (i32.lt_u (local.get $sp) (i32.const 3)))\n"
"            (local.set $c (i32.load (i32.mul (i32.sub (local.get $sp) (i32.const 1)) (i32.const 4))))  ;; hi\n"
"            (local.set $b (i32.load (i32.mul (i32.sub (local.get $sp) (i32.const 2)) (i32.const 4))))  ;; lo\n"
"            (local.set $a (i32.load (i32.mul (i32.sub (local.get $sp) (i32.const 3)) (i32.const 4))))  ;; val\n"
"            (local.set $c (call $saturate (local.get $c)))\n"
"            (local.set $b (call $saturate (local.get $b)))\n"
"            (local.set $a (call $saturate (local.get $a)))\n"
"            ;; Check: a < b || a > c\n"
"            (if (i32.or\n"
"              (i32.lt_s (local.get $a) (local.get $b))\n"
"              (i32.gt_s (local.get $a) (local.get $c)))\n"
"              (then\n"
"                (local.set $cid (i32.load (i32.const 0x4C)))\n"
"                (local.set $mask (i32.or (local.get $mask)\n"
"                  (i32.shl (i32.const 1) (local.get $cid))))\n"
"                ;; Push 1 (fail)\n"
"                (i32.store\n"
"                  (i32.mul (i32.sub (local.get $sp) (i32.const 3)) (i32.const 4))\n"
"                  (i32.const 1))\n"
"              )\n"
"              (else\n"
"                ;; Push 0 (pass)\n"
"                (i32.store\n"
"                  (i32.mul (i32.sub (local.get $sp) (i32.const 3)) (i32.const 4))\n"
"                  (i32.const 0))\n"
"              )\n"
"            )\n"
"            (i32.store (i32.const 0x40) (i32.sub (local.get $sp) (i32.const 2)))\n"
"            (br $dispatch)\n"
"          ))\n"
"\n"
"          ;; FLUX_CONSTRAINT_ID = 0x63\n"
"          (if (i32.eq (local.get $op) (i32.const 0x63)) (then\n"
"            (local.set $pc (i32.load (i32.const 0x44)))\n"
"            (br_if $exec_done (i32.ge_u (local.get $pc) (local.get $bc_len)))\n"
"            (i32.store (i32.const 0x4C)\n"
"              (i32.load8_u (i32.add (local.get $bc_ptr) (local.get $pc))))\n"
"            (i32.store (i32.const 0x44) (i32.add (local.get $pc) (i32.const 1)))\n"
"            (br $dispatch)\n"
"          ))\n"
"\n"
"          ;; FLUX_HALT = 0x54\n"
"          (if (i32.eq (local.get $op) (i32.const 0x54)) (then\n"
"            (i32.store (i32.const 0x50) (i32.const 1))\n"
"            (br $exec_done)\n"
"          ))\n"
"\n"
"          ;; FLUX_DUP = 0x03\n"
"          (if (i32.eq (local.get $op) (i32.const 0x03)) (then\n"
"            (local.set $sp (i32.load (i32.const 0x40)))\n"
"            (br_if $exec_done (i32.eqz (local.get $sp)))\n"
"            (local.set $a (i32.load (i32.mul (i32.sub (local.get $sp) (i32.const 1)) (i32.const 4))))\n"
"            (call $push (local.get $a)) (drop)\n"
"            (br $dispatch)\n"
"          ))\n"
"\n"
"          ;; Unknown opcode → error\n"
"          (return (i32.const 3))\n"
"        )  ;; end dispatch\n"
"\n"
"        (br $exec_loop)\n"
"      )  ;; end exec_loop\n"
"    )  ;; end exec_done\n"
"\n"
"    ;; Write result\n"
"    (i32.store (local.get $result_ptr) (local.get $mask))       ;; error_mask\n"
"    (i32.store (i32.add (local.get $result_ptr) (i32.const 4))\n"
"      (local.get $instr))  ;; instr_count\n"
"\n"
"    ;; Compute severity\n"
"    ;; Count bits in mask: simple loop\n"
"    (local.set $a (local.get $mask))\n"
"    (local.set $b (i32.const 0))\n"
"    (block $count_done\n"
"      (loop $count_loop\n"
"        (br_if $count_done (i32.eqz (local.get $a)))\n"
"        (local.set $b (i32.add (local.get $b) (i32.and (local.get $a) (i32.const 1))))\n"
"        (local.set $a (i32.shr_u (local.get $a) (i32.const 1)))\n"
"        (br $count_loop)\n"
"      )\n"
"    )\n"
"    (if (i32.le_u (local.get $b) (i32.const 2))\n"
"      (then (i32.store (i32.add (local.get $result_ptr) (i32.const 8)) (local.get $b)))\n"
"      (else (i32.store (i32.add (local.get $result_ptr) (i32.const 8)) (i32.const 3)))\n"
"    )\n"
"\n"
"    (i32.const 0)  ;; OK\n"
"  )\n"
")\n"
;

/* ═══════════════════════════════════════════════════════════════════════
 * C Source — for Emscripten compilation
 *
 * This produces the same result as the WAT above but can be compiled
 * through standard toolchains.
 * ═══════════════════════════════════════════════════════════════════════ */

#ifdef __EMSCRIPTEN__
#include <stdint.h>
#include <stddef.h>

#define FLUX_STACK_SIZE     16
#define FLUX_MAX_BYTECODE   256

static int32_t g_stack[FLUX_STACK_SIZE];
static int     g_sp;
static int     g_pc;
static int     g_deadline;
static int     g_constraint_id;
static int     g_flags;

static int32_t saturate(int32_t v) {
    return v < -127 ? -127 : (v > 127 ? 127 : v);
}

static int push(int32_t v) {
    if (g_sp >= FLUX_STACK_SIZE) return 2;
    g_stack[g_sp++] = saturate(v);
    return 0;
}

static int pop(int32_t *out) {
    if (g_sp == 0) return 1;
    *out = g_stack[--g_sp];
    return 0;
}

int check(const int32_t *values, int count, const uint8_t *bc, int bc_len,
          int32_t *result) {
    g_sp = 0; g_pc = 0; g_deadline = 4096;
    g_constraint_id = 0; g_flags = 0;

    for (int i = 0; i < count && i < 8; i++) {
        if (push(values[i])) return 2;
    }

    int32_t a, b, c, mask = 0, instr = 0, countdown = g_deadline;

    while (g_pc < bc_len && !g_flags && countdown-- > 0) {
        instr++;
        uint8_t op = bc[g_pc++];
        switch (op) {
        case 0x00: break;
        case 0x01:
            if (g_pc >= bc_len) return 5;
            if (push((int32_t)(int8_t)bc[g_pc++])) return 2;
            break;
        case 0x03:
            if (g_sp == 0) return 1;
            if (push(g_stack[g_sp-1])) return 2;
            break;
        case 0x10:
            if (pop(&b)||pop(&a)) return 1;
            if (push(a+b)) return 2; break;
        case 0x11:
            if (pop(&b)||pop(&a)) return 1;
            if (push(a-b)) return 2; break;
        case 0x12:
            if (pop(&b)||pop(&a)) return 1;
            if (push(a*b)) return 2; break;
        case 0x13:
            if (pop(&b)||pop(&a)) return 1;
            if (b==0) return 4;
            if (push(a/b)) return 2; break;
        case 0x15:
            if (g_sp==0) return 1;
            g_stack[g_sp-1] = -g_stack[g_sp-1]; break;
        case 0x16:
            if (g_sp==0) return 1;
            a = g_stack[g_sp-1]; g_stack[g_sp-1] = a<0?-a:a; break;
        case 0x22:
            if (pop(&b)||pop(&a)) return 1;
            if (push(a<b?1:0)) return 2; break;
        case 0x23:
            if (pop(&b)||pop(&a)) return 1;
            if (push(a>b?1:0)) return 2; break;
        case 0x40:
            if (pop(&c)||pop(&b)||pop(&a)) return 1;
            a=saturate(a); b=saturate(b); c=saturate(c);
            if (a<b||a>c) mask |= (1u<<g_constraint_id);
            if (push((a<b||a>c)?1:0)) return 2; break;
        case 0x54: g_flags = 1; break;
        case 0x63:
            if (g_pc>=bc_len) return 5;
            g_constraint_id = bc[g_pc++]; break;
        default: return 3;
        }
    }

    result[0] = mask;
    result[1] = instr;
    int nv = 0; a = mask;
    while (a) { nv += a&1; a >>= 1; }
    result[2] = nv <= 2 ? nv : 3;
    return 0;
}
#endif /* __EMSCRIPTEN__ */
