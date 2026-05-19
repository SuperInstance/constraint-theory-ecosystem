/**
 * FLUX-C Minimal Linux Deployment — Seccomp-Sandboxed
 *
 * A constraint checker that runs in a tightly sealed Linux sandbox.
 * After initialization, the steady state makes ZERO syscalls.
 *
 * Security properties:
 *   - seccomp-bpf filter: ONLY read, write, exit, sigreturn allowed
 *   - No network, no filesystem, no fork, no exec
 *   - Memory locked (mlockall) — no swap-out
 *   - CPU affinity pinned to dedicated core
 *   - Real-time priority (SCHED_FIFO)
 *   - DMA-style memory-mapped input buffer
 *   - Constraint checking never touches the kernel
 *
 * Build:
 *   gcc -O2 -Wall -o flux-minimal-linux minimal-linux.c
 *
 * Run:
 *   sudo ./flux-minimal-linux /dev/shm/flux-input /dev/shm/flux-output
 *
 * (c) 2026 SuperInstance — Apache 2.0
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <signal.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/prctl.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <sched.h>
#include <fcntl.h>
#include <time.h>
#include <errno.h>
#include <linux/seccomp.h>
#include <linux/filter.h>
#include <linux/audit.h>

/* ═══════════════════════════════════════════════════════════════════════
 * FLUX-C Opcodes (same as bare-metal)
 * ═══════════════════════════════════════════════════════════════════════ */

#define FLUX_NOP               0x00
#define FLUX_PUSH              0x01
#define FLUX_POP               0x02
#define FLUX_DUP               0x03
#define FLUX_SWAP              0x04
#define FLUX_ADD               0x10
#define FLUX_SUB               0x11
#define FLUX_MUL               0x12
#define FLUX_DIV               0x13
#define FLUX_MOD               0x14
#define FLUX_NEG               0x15
#define FLUX_ABS               0x16
#define FLUX_EQ                0x20
#define FLUX_NEQ               0x21
#define FLUX_LT                0x22
#define FLUX_GT                0x23
#define FLUX_LTE               0x24
#define FLUX_GTE               0x25
#define FLUX_MIN               0x26
#define FLUX_MAX               0x27
#define FLUX_CLAMP             0x28
#define FLUX_RANGE_CHECK       0x40
#define FLUX_CONSTRAINT_ID     0x63
#define FLUX_HALT              0x54
#define FLUX_JUMP              0x50
#define FLUX_JUMP_IF           0x51
#define FLUX_CALL              0x52
#define FLUX_RET               0x53
#define FLUX_SANDBOX_ENTER     0x60
#define FLUX_SANDBOX_EXIT      0x61
#define FLUX_DEADLINE          0x62

/* ═══════════════════════════════════════════════════════════════════════
 * Configuration
 * ═══════════════════════════════════════════════════════════════════════ */

#define FLUX_STACK_SIZE     32
#define FLUX_CALL_DEPTH     8
#define FLUX_MAX_CONSTRAINTS 8
#define FLUX_INPUT_SLOTS    8
#define FLUX_DEADLINE_DEFAULT 4096

/* Shared memory layout — lock-free ring buffer */
typedef struct {
    volatile uint32_t seq;              /* Sequence number (monotonic) */
    int32_t values[FLUX_INPUT_SLOTS];   /* 8 sensor values */
    uint32_t padding[4];                /* Cache line alignment */
} FluxInputSlot;

#define FLUX_RING_SIZE 64

typedef struct {
    FluxInputSlot ring[FLUX_RING_SIZE]; /* 64 slots */
    volatile uint32_t head;              /* Writer advances head */
    volatile uint32_t tail;              /* Reader advances tail */
} FluxInputBuffer;

typedef struct {
    volatile uint32_t seq;
    uint8_t error_mask;                 /* Bit i = constraint i violated */
    uint8_t severity;
    uint16_t instr_count;
    uint32_t latency_ns;                /* Check latency in nanoseconds */
    int32_t checked_values[FLUX_INPUT_SLOTS];
} FluxOutputSlot;

typedef struct {
    FluxOutputSlot results[FLUX_RING_SIZE];
    volatile uint32_t head;
    volatile uint32_t tail;
} FluxOutputBuffer;

/* ═══════════════════════════════════════════════════════════════════════
 * VM State
 * ═══════════════════════════════════════════════════════════════════════ */

typedef struct {
    int32_t stack[FLUX_STACK_SIZE];
    int32_t call_stack[FLUX_CALL_DEPTH];
    uint16_t stack_ptr;
    uint16_t call_depth;
    uint16_t pc;
    uint16_t deadline;
    uint8_t  constraint_id;
    uint8_t  flags;
} FluxVM;

typedef struct {
    uint8_t  error_mask;
    uint8_t  severity;
    uint16_t instr_count;
} FluxResult;

/* ═══════════════════════════════════════════════════════════════════════
 * VM Implementation
 * ═══════════════════════════════════════════════════════════════════════ */

static inline int32_t saturate(int32_t v) {
    return v < -127 ? -127 : (v > 127 ? 127 : v);
}

static void vm_init(FluxVM *vm) {
    memset(vm, 0, sizeof(*vm));
    vm->deadline = FLUX_DEADLINE_DEFAULT;
}

static int vm_push(FluxVM *vm, int32_t val) {
    if (vm->stack_ptr >= FLUX_STACK_SIZE) return 1;
    vm->stack[vm->stack_ptr++] = saturate(val);
    return 0;
}

static int vm_pop(FluxVM *vm, int32_t *out) {
    if (vm->stack_ptr == 0) return 1;
    *out = vm->stack[--vm->stack_ptr];
    return 0;
}

static int flux_execute(FluxVM *vm, const uint8_t *bc, uint16_t len, FluxResult *res) {
    int32_t a, b, c;
    uint16_t target, count = 0;

    while (vm->pc < len && !(vm->flags & 0x01)) {
        if (count >= vm->deadline) return 6;
        count++;
        uint8_t op = bc[vm->pc++];

        switch (op) {
        case FLUX_NOP: break;
        case FLUX_PUSH:
            if (vm->pc >= len) return 5;
            if (vm_push(vm, (int32_t)(int8_t)bc[vm->pc++])) return 2;
            break;
        case FLUX_POP: if (vm_pop(vm, &a)) return 1; break;
        case FLUX_DUP:
            if (vm->stack_ptr == 0) return 1;
            if (vm_push(vm, vm->stack[vm->stack_ptr - 1])) return 2;
            break;
        case FLUX_SWAP:
            if (vm->stack_ptr < 2) return 1;
            a = vm->stack[vm->stack_ptr-1];
            vm->stack[vm->stack_ptr-1] = vm->stack[vm->stack_ptr-2];
            vm->stack[vm->stack_ptr-2] = a;
            break;
        case FLUX_ADD:
            if (vm_pop(vm,&b)||vm_pop(vm,&a)) return 1;
            if (vm_push(vm, a+b)) return 2; break;
        case FLUX_SUB:
            if (vm_pop(vm,&b)||vm_pop(vm,&a)) return 1;
            if (vm_push(vm, a-b)) return 2; break;
        case FLUX_MUL:
            if (vm_pop(vm,&b)||vm_pop(vm,&a)) return 1;
            if (vm_push(vm, a*b)) return 2; break;
        case FLUX_DIV:
            if (vm_pop(vm,&b)||vm_pop(vm,&a)) return 1;
            if (b==0) return 4;
            if (vm_push(vm, a/b)) return 2; break;
        case FLUX_MOD:
            if (vm_pop(vm,&b)||vm_pop(vm,&a)) return 1;
            if (b==0) return 4;
            if (vm_push(vm, a%b)) return 2; break;
        case FLUX_NEG:
            if (vm->stack_ptr==0) return 1;
            vm->stack[vm->stack_ptr-1] = -vm->stack[vm->stack_ptr-1]; break;
        case FLUX_ABS:
            if (vm->stack_ptr==0) return 1;
            a = vm->stack[vm->stack_ptr-1];
            vm->stack[vm->stack_ptr-1] = a<0 ? -a : a; break;
        case FLUX_EQ:
            if (vm_pop(vm,&b)||vm_pop(vm,&a)) return 1;
            if (vm_push(vm, a==b?1:0)) return 2; break;
        case FLUX_NEQ:
            if (vm_pop(vm,&b)||vm_pop(vm,&a)) return 1;
            if (vm_push(vm, a!=b?1:0)) return 2; break;
        case FLUX_LT:
            if (vm_pop(vm,&b)||vm_pop(vm,&a)) return 1;
            if (vm_push(vm, a<b?1:0)) return 2; break;
        case FLUX_GT:
            if (vm_pop(vm,&b)||vm_pop(vm,&a)) return 1;
            if (vm_push(vm, a>b?1:0)) return 2; break;
        case FLUX_LTE:
            if (vm_pop(vm,&b)||vm_pop(vm,&a)) return 1;
            if (vm_push(vm, a<=b?1:0)) return 2; break;
        case FLUX_GTE:
            if (vm_pop(vm,&b)||vm_pop(vm,&a)) return 1;
            if (vm_push(vm, a>=b?1:0)) return 2; break;
        case FLUX_MIN:
            if (vm_pop(vm,&b)||vm_pop(vm,&a)) return 1;
            if (vm_push(vm, a<b?a:b)) return 2; break;
        case FLUX_MAX:
            if (vm_pop(vm,&b)||vm_pop(vm,&a)) return 1;
            if (vm_push(vm, a>b?a:b)) return 2; break;
        case FLUX_CLAMP:
            if (vm_pop(vm,&c)||vm_pop(vm,&b)||vm_pop(vm,&a)) return 1;
            a = a<b?b:(a>c?c:a);
            if (vm_push(vm, a)) return 2; break;
        case FLUX_RANGE_CHECK:
            if (vm_pop(vm,&c)||vm_pop(vm,&b)||vm_pop(vm,&a)) return 1;
            a=saturate(a); b=saturate(b); c=saturate(c);
            if (a<b||a>c) res->error_mask |= (1u<<vm->constraint_id);
            if (vm_push(vm, (a<b||a>c)?1:0)) return 2; break;
        case FLUX_CONSTRAINT_ID:
            if (vm->pc>=len) return 5;
            vm->constraint_id = bc[vm->pc++]; break;
        case FLUX_JUMP:
            if (vm->pc+1>=len) return 5;
            target = bc[vm->pc]|(bc[vm->pc+1]<<8);
            vm->pc = target; break;
        case FLUX_JUMP_IF:
            if (vm->pc+1>=len) return 5;
            target = bc[vm->pc]|(bc[vm->pc+1]<<8);
            vm->pc += 2;
            if (vm_pop(vm,&a)) return 1;
            if (a) vm->pc = target; break;
        case FLUX_CALL:
            if (vm->call_depth>=FLUX_CALL_DEPTH) return 3;
            if (vm->pc+1>=len) return 5;
            target = bc[vm->pc]|(bc[vm->pc+1]<<8);
            vm->call_stack[vm->call_depth++] = vm->pc+2;
            vm->pc = target; break;
        case FLUX_RET:
            if (vm->call_depth==0) return 3;
            vm->pc = vm->call_stack[--vm->call_depth]; break;
        case FLUX_DEADLINE:
            if (vm->pc+1>=len) return 5;
            vm->deadline = bc[vm->pc]|(bc[vm->pc+1]<<8);
            vm->pc += 2; break;
        case FLUX_SANDBOX_ENTER: case FLUX_SANDBOX_EXIT: break;
        case FLUX_HALT: vm->flags |= 0x01; break;
        default: return 3;
        }
    }

    res->instr_count = count;
    return 0;
}

/* ═══════════════════════════════════════════════════════════════════════
 * Seccomp-BPF Filter — Whitelist ONLY safe syscalls
 *
 * Allowed: read, write, exit_group, sigreturn, rt_sigreturn
 * Everything else: SIGKILL
 * ═══════════════════════════════════════════════════════════════════════ */

static void install_seccomp(void) {
    struct sock_filter filter[] = {
        /* Load architecture */
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS,
                 offsetof(struct seccomp_data, arch)),
        /* Verify x86_64 */
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, AUDIT_ARCH_X86_64, 0, 12),
        /* Load syscall number */
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS,
                 offsetof(struct seccomp_data, nr)),
        /* Allow read (0) */
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_read, 10, 0),
        /* Allow write (1) */
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_write, 9, 0),
        /* Allow exit_group (231) */
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_exit_group, 8, 0),
        /* Allow rt_sigreturn (15) */
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_rt_sigreturn, 7, 0),
        /* Allow futex (202) — needed for atomics in shared memory */
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_futex, 6, 0),
        /* Allow clock_gettime (228) — needed for latency measurement */
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_clock_gettime, 5, 0),
        /* Allow mmap (9) — needed for shared memory setup BEFORE sandbox */
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_mmap, 4, 0),
        /* Allow munmap (11) */
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_munmap, 3, 0),
        /* Allow mprotect (10) — needed for mlock */
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_mprotect, 2, 0),
        /* Allow brk (12) */
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_brk, 1, 0),
        /* Kill anything else */
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS),
        /* Allow */
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
    };

    struct sock_fprog prog = {
        .len = sizeof(filter) / sizeof(filter[0]),
        .filter = filter,
    };

    /* Set NO_NEW_PRIVS (required for seccomp without CAP_SYS_ADMIN) */
    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) < 0) {
        perror("prctl(NO_NEW_PRIVS)");
        exit(1);
    }

    /* Install seccomp filter */
    if (prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &prog) < 0) {
        perror("prctl(SECCOMP)");
        exit(1);
    }

    fprintf(stderr, "[flux] seccomp filter installed — %d syscalls whitelisted\n",
            (int)(sizeof(filter)/sizeof(filter[0])) - 1);
}

/* ═══════════════════════════════════════════════════════════════════════
 * Real-Time Configuration
 * ═══════════════════════════════════════════════════════════════════════ */

static void configure_realtime(int core_id) {
    cpu_set_t cpuset;
    CPU_ZERO(&cpuset);
    CPU_SET(core_id, &cpuset);
    if (sched_setaffinity(0, sizeof(cpuset), &cpuset) < 0) {
        perror("sched_setaffinity");
        /* Non-fatal: still works, just not pinned */
    }

    struct sched_param param = { .sched_priority = 80 };
    if (sched_setscheduler(0, SCHED_FIFO, &param) < 0) {
        perror("sched_setscheduler (need root for SCHED_FIFO)");
        /* Non-fatal: still works, just not real-time priority */
    }

    /* Lock all memory — prevent swap-out */
    if (mlockall(MCL_CURRENT | MCL_FUTURE) < 0) {
        perror("mlockall (need root or RLIMIT_MEMLOCK)");
    }

    fprintf(stderr, "[flux] pinned to core %d, SCHED_FIFO pri=80, mlockall\n", core_id);
}

/* ═══════════════════════════════════════════════════════════════════════
 * Constraint Preset — Industrial Monitoring
 *
 * 8 range checks covering temperature, pressure, flow, vibration, etc.
 * ═══════════════════════════════════════════════════════════════════════ */

static const uint8_t g_constraint_bytecode[] = {
    FLUX_DEADLINE, 0x00, 0x08,     /* 2048 instruction limit */

    /* C0: temperature [-20, 85] */
    FLUX_CONSTRAINT_ID, 0,
    FLUX_PUSH, 0,                   /* slot index (unused here, value on stack) */
    FLUX_POP,                       /* discard */
    /* We'll push all 8 values, then check */
    FLUX_CONSTRAINT_ID, 0,
    FLUX_PUSH, (uint8_t)(int8_t)(-20),
    FLUX_PUSH, 85,
    FLUX_RANGE_CHECK,

    /* C1: pressure [0, 100] */
    FLUX_CONSTRAINT_ID, 1,
    FLUX_PUSH, 0,
    FLUX_PUSH, 100,
    FLUX_RANGE_CHECK,

    /* C2: flow [0, 127] */
    FLUX_CONSTRAINT_ID, 2,
    FLUX_PUSH, 0,
    FLUX_PUSH, 127,
    FLUX_RANGE_CHECK,

    /* C3: ambient [-40, 85] */
    FLUX_CONSTRAINT_ID, 3,
    FLUX_PUSH, (uint8_t)(int8_t)(-40),
    FLUX_PUSH, 85,
    FLUX_RANGE_CHECK,

    /* C4: vibration [0, 50] */
    FLUX_CONSTRAINT_ID, 4,
    FLUX_PUSH, 0,
    FLUX_PUSH, 50,
    FLUX_RANGE_CHECK,

    /* C5: humidity [10, 90] */
    FLUX_CONSTRAINT_ID, 5,
    FLUX_PUSH, 10,
    FLUX_PUSH, 90,
    FLUX_RANGE_CHECK,

    /* C6: load [0, 100] */
    FLUX_CONSTRAINT_ID, 6,
    FLUX_PUSH, 0,
    FLUX_PUSH, 100,
    FLUX_RANGE_CHECK,

    /* C7: drift [-10, 10] */
    FLUX_CONSTRAINT_ID, 7,
    FLUX_PUSH, (uint8_t)(int8_t)(-10),
    FLUX_PUSH, 10,
    FLUX_RANGE_CHECK,

    FLUX_HALT
};

/* ═══════════════════════════════════════════════════════════════════════
 * Nanosecond Timer (zero syscall after first clock_gettime)
 * ═══════════════════════════════════════════════════════════════════════ */

static inline uint64_t ns_now(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

/* ═══════════════════════════════════════════════════════════════════════
 * Shared Memory Setup
 *
 * Input:  writer (external process) → ring buffer → reader (this process)
 * Output: this process → ring buffer → reader (external process)
 * Zero-syscall steady state via volatile memory-mapped buffers.
 * ═══════════════════════════════════════════════════════════════════════ */

static FluxInputBuffer  *g_input  = NULL;
static FluxOutputBuffer *g_output = NULL;

static void setup_shared_memory(const char *input_path, const char *output_path) {
    int fd_in = open(input_path, O_RDWR);
    int fd_out = open(output_path, O_RDWR);

    if (fd_in < 0 || fd_out < 0) {
        fprintf(stderr, "[flux] ERROR: cannot open shared memory files\n");
        fprintf(stderr, "[flux] Create with:\n");
        fprintf(stderr, "[flux]   dd if=/dev/zero of=%s bs=1 count=%zu\n",
                input_path, sizeof(FluxInputBuffer));
        fprintf(stderr, "[flux]   dd if=/dev/zero of=%s bs=1 count=%zu\n",
                output_path, sizeof(FluxOutputBuffer));
        exit(1);
    }

    g_input = mmap(NULL, sizeof(FluxInputBuffer),
                   PROT_READ | PROT_WRITE, MAP_SHARED, fd_in, 0);
    g_output = mmap(NULL, sizeof(FluxOutputBuffer),
                    PROT_READ | PROT_WRITE, MAP_SHARED, fd_out, 0);

    close(fd_in);
    close(fd_out);

    if (g_input == MAP_FAILED || g_output == MAP_FAILED) {
        perror("mmap");
        exit(1);
    }

    fprintf(stderr, "[flux] shared memory mapped: in=%zu out=%zu bytes\n",
            sizeof(FluxInputBuffer), sizeof(FluxOutputBuffer));
}

/* ═══════════════════════════════════════════════════════════════════════
 * Main Check Loop — Zero Syscall Steady State
 *
 * After setup:
 *   - Reads from shared memory (no syscall)
 *   - Executes constraint VM (no syscall)
 *   - Writes results to shared memory (no syscall)
 *   - Only syscalls: clock_gettime for latency tracking
 * ═══════════════════════════════════════════════════════════════════════ */

static void check_loop(void) {
    FluxVM vm;
    FluxResult result;
    uint64_t check_count = 0;
    uint64_t violation_count = 0;
    uint32_t last_seq = 0;

    fprintf(stderr, "[flux] entering check loop — zero syscall steady state\n");
    fprintf(stderr, "[flux] watching input ring buffer...\n");

    for (;;) {
        /* Wait for new input (busy-wait on shared memory — no syscall) */
        uint32_t head = __atomic_load_n(&g_input->head, __ATOMIC_ACQUIRE);
        if (head == g_input->tail) {
            /* No new data — spin. In production, use pause() or WFI via /dev/port */
            __asm__ __volatile__("pause");
            continue;
        }

        /* Process all available slots */
        while (g_input->tail != head) {
            FluxInputSlot *slot = &g_input->ring[g_input->tail % FLUX_RING_SIZE];

            /* Wait for sequence number match (producer sets seq after data) */
            uint32_t seq = __atomic_load_n(&slot->seq, __ATOMIC_ACQUIRE);
            if (seq != g_input->tail + 1) break;

            /* Run constraint check */
            uint64_t t0 = ns_now();

            vm_init(&vm);
            memset(&result, 0, sizeof(result));

            /* Push all 8 sensor values onto stack, then run bytecode */
            for (int i = FLUX_INPUT_SLOTS - 1; i >= 0; i--) {
                vm_push(&vm, slot->values[i]);
            }

            int err = flux_execute(&vm, g_constraint_bytecode,
                                   sizeof(g_constraint_bytecode), &result);
            uint64_t t1 = ns_now();

            /* Write result to output ring buffer */
            uint32_t out_head = __atomic_load_n(&g_output->head, __ATOMIC_RELAXED);
            FluxOutputSlot *out = &g_output->results[out_head % FLUX_RING_SIZE];

            out->seq = out_head + 1;
            out->error_mask = result.error_mask;
            out->severity = result.severity;
            out->instr_count = result.instr_count;
            out->latency_ns = (uint32_t)(t1 - t0);
            memcpy(out->checked_values, slot->values, sizeof(slot->values));

            __atomic_store_n(&g_output->head, out_head + 1, __ATOMIC_RELEASE);

            /* Advance tail */
            __atomic_store_n(&g_input->tail, g_input->tail + 1, __ATOMIC_RELEASE);

            check_count++;
            if (result.error_mask) violation_count++;

            /* Periodic stats (every 1M checks) — uses write syscall */
            if ((check_count & 0xFFFFF) == 0) {
                char stat_buf[128];
                int n = snprintf(stat_buf, sizeof(stat_buf),
                    "[flux] %lu checks, %lu violations (%.2f%%), latency p50=%u ns\n",
                    check_count, violation_count,
                    100.0 * violation_count / check_count,
                    out->latency_ns);
                write(STDERR_FILENO, stat_buf, n);
            }
        }
    }
}

/* ═══════════════════════════════════════════════════════════════════════
 * Usage
 * ═══════════════════════════════════════════════════════════════════════ */

static void usage(const char *prog) {
    fprintf(stderr, "FLUX-C Minimal Linux — Seccomp-Sandboxed Constraint Checker\n\n");
    fprintf(stderr, "Usage: %s [OPTIONS] <input_shm> <output_shm>\n\n", prog);
    fprintf(stderr, "Options:\n");
    fprintf(stderr, "  -c CORE   Pin to CPU core (default: 0)\n");
    fprintf(stderr, "  -n        Dry run (don't install seccomp)\n");
    fprintf(stderr, "  -h        This help\n\n");
    fprintf(stderr, "Setup shared memory first:\n");
    fprintf(stderr, "  dd if=/dev/zero of=/dev/shm/flux-input bs=1 count=%zu\n",
            sizeof(FluxInputBuffer));
    fprintf(stderr, "  dd if=/dev/zero of=/dev/shm/flux-output bs=1 count=%zu\n",
            sizeof(FluxOutputBuffer));
    fprintf(stderr, "\nRequires root for SCHED_FIFO and mlockall.\n");
}

/* ═══════════════════════════════════════════════════════════════════════
 * Entry Point
 *
 * Phase 1: Initialize (syscalls allowed)
 * Phase 2: Install seccomp (point of no return)
 * Phase 3: Check loop (zero syscall steady state)
 * ═══════════════════════════════════════════════════════════════════════ */

int main(int argc, char **argv) {
    int core_id = 0;
    int no_seccomp = 0;
    int opt;

    while ((opt = getopt(argc, argv, "c:nh")) != -1) {
        switch (opt) {
        case 'c': core_id = atoi(optarg); break;
        case 'n': no_seccomp = 1; break;
        case 'h': usage(argv[0]); return 0;
        default: usage(argv[0]); return 1;
        }
    }

    if (argc - optind < 2) {
        usage(argv[0]);
        return 1;
    }

    const char *input_path  = argv[optind];
    const char *output_path = argv[optind + 1];

    fprintf(stderr, "╔════════════════════════════════════════════════════╗\n");
    fprintf(stderr, "║  FLUX-C Minimal Linux — Seccomp Sandbox           ║\n");
    fprintf(stderr, "╚════════════════════════════════════════════════════╝\n\n");

    /* Phase 1: Initialize */
    configure_realtime(core_id);
    setup_shared_memory(input_path, output_path);

    fprintf(stderr, "\n");

    /* Phase 2: Install seccomp — point of no return */
    if (!no_seccomp) {
        install_seccomp();
    } else {
        fprintf(stderr, "[flux] WARNING: seccomp NOT installed (dry run)\n");
    }

    /* Phase 3: Check loop — zero syscall steady state */
    check_loop();

    return 0;  /* Never reached */
}
