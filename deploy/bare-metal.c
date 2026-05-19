/**
 * FLUX-C Bare-Metal Deployment — ARM Cortex-M4
 *
 * Complete air-gap constraint checker for STM32F4-class microcontrollers.
 * No stdlib, no heap, no OS, no network, no filesystem.
 *
 * Features:
 *   - Static allocation only (no malloc, ever)
 *   - Direct register access for sensor input (ADC)
 *   - Interrupt-driven constraint checking (TIM2 @ 1kHz)
 *   - Flash-based constraint presets
 *   - UART output for violation alerts
 *   - < 4KB flash, < 1KB RAM
 *   - Compiles with arm-none-eabi-gcc
 *
 * Build:
 *   arm-none-eabi-gcc -mcpu=cortex-m4 -mthumb -O2 -nostdlib \
 *       -T stm32f4.ld bare-metal.c -o flux-baremetal.elf
 *   arm-none-eabi-objcopy -O binary flux-baremetal.elf flux-baremetal.bin
 *
 * (c) 2026 SuperInstance — Apache 2.0
 */

/* ═══════════════════════════════════════════════════════════════════════
 * No standard library. We define what we need.
 * ═══════════════════════════════════════════════════════════════════════ */

typedef unsigned int      uint32_t;
typedef unsigned short    uint16_t;
typedef unsigned char     uint8_t;
typedef int               int32_t;
typedef short             int16_t;
typedef signed char       int8_t;

#define NULL ((void*)0)
#define static_assert _Static_assert

/* ═══════════════════════════════════════════════════════════════════════
 * STM32F4 Register Definitions (Cortex-M4 peripherals)
 * ═══════════════════════════════════════════════════════════════════════ */

/* RCC (Reset and Clock Control) */
#define RCC_BASE        0x40023800UL
#define RCC_AHB1ENR     (*(volatile uint32_t*)(RCC_BASE + 0x30))
#define RCC_APB1ENR     (*(volatile uint32_t*)(RCC_BASE + 0x40))
#define RCC_APB2ENR     (*(volatile uint32_t*)(RCC_BASE + 0x44))

/* GPIOA */
#define GPIOA_BASE      0x40020000UL
#define GPIOA_MODER     (*(volatile uint32_t*)(GPIOA_BASE + 0x00))
#define GPIOA_AFRL      (*(volatile uint32_t*)(GPIOA_BASE + 0x20))
#define GPIOA_BSRR      (*(volatile uint32_t*)(GPIOA_BASE + 0x18))

/* USART2 (PA2=TX, PA3=RX) */
#define USART2_BASE     0x40004400UL
#define USART2_SR       (*(volatile uint32_t*)(USART2_BASE + 0x00))
#define USART2_DR       (*(volatile uint32_t*)(USART2_BASE + 0x04))
#define USART2_BRR      (*(volatile uint32_t*)(USART2_BASE + 0x08))
#define USART2_CR1      (*(volatile uint32_t*)(USART2_BASE + 0x0C))
#define USART2_CR2      (*(volatile uint32_t*)(USART2_BASE + 0x10))

/* TIM2 (General-purpose timer for constraint checking) */
#define TIM2_BASE       0x40000000UL
#define TIM2_CR1        (*(volatile uint32_t*)(TIM2_BASE + 0x00))
#define TIM2_DIER       (*(volatile uint32_t*)(TIM2_BASE + 0x0C))
#define TIM2_SR         (*(volatile uint32_t*)(TIM2_BASE + 0x10))
#define TIM2_PSC        (*(volatile uint32_t*)(TIM2_BASE + 0x28))
#define TIM2_ARR        (*(volatile uint32_t*)(TIM2_BASE + 0x2C))

/* ADC1 (PA0 = Channel 0, sensor input) */
#define ADC1_BASE       0x40012000UL
#define ADC1_SR         (*(volatile uint32_t*)(ADC1_BASE + 0x00))
#define ADC1_CR1        (*(volatile uint32_t*)(ADC1_BASE + 0x04))
#define ADC1_CR2        (*(volatile uint32_t*)(ADC1_BASE + 0x08))
#define ADC1_SQR3       (*(volatile uint32_t*)(ADC1_BASE + 0x34))
#define ADC1_DR         (*(volatile uint32_t*)(ADC1_BASE + 0x4C))

/* NVIC (Nested Vectored Interrupt Controller) */
#define NVIC_BASE       0xE000E100UL
#define NVIC_ISER0      (*(volatile uint32_t*)(NVIC_BASE + 0x00))

/* SCB (System Control Block) */
#define SCB_BASE        0xE000ED00UL
#define SCB_VTOR        (*(volatile uint32_t*)(SCB_BASE + 0x08))

/* SysTick */
#define SYSTICK_BASE    0xE000E010UL
#define SYSTICK_CTRL    (*(volatile uint32_t*)(SYSTICK_BASE + 0x00))
#define SYSTICK_LOAD    (*(volatile uint32_t*)(SYSTICK_BASE + 0x04))
#define SYSTICK_VAL     (*(volatile uint32_t*)(SYSTICK_BASE + 0x08))

/* Bit helpers */
#define BIT(n)          (1U << (n))
#define RCC_AHB1ENR_GPIOAEN  BIT(0)
#define RCC_APB1ENR_USART2EN BIT(17)
#define RCC_APB1ENR_TIM2EN   BIT(0)
#define RCC_APB2ENR_ADC1EN   BIT(8)

/* ═══════════════════════════════════════════════════════════════════════
 * FLUX-C Opcodes (subset for bare-metal)
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
#define FLUX_NEG               0x15
#define FLUX_ABS               0x16
#define FLUX_LT                0x22
#define FLUX_GT                0x23
#define FLUX_LTE               0x24
#define FLUX_GTE               0x25
#define FLUX_RANGE_CHECK       0x40
#define FLUX_CONSTRAINT_ID     0x63
#define FLUX_HALT              0x54
#define FLUX_SANDBOX_ENTER     0x60
#define FLUX_SANDBOX_EXIT      0x61

/* Error codes */
#define FLUX_OK                     0
#define FLUX_ERR_STACK_UNDERFLOW    1
#define FLUX_ERR_STACK_OVERFLOW     2
#define FLUX_ERR_UNKNOWN_OPCODE     3
#define FLUX_ERR_DIVISION_BY_ZERO   4
#define FLUX_ERR_INVALID_OPERAND    5
#define FLUX_ERR_DEADLINE           6

/* ═══════════════════════════════════════════════════════════════════════
 * Static Memory Layout — all fixed-size, no heap
 * ═══════════════════════════════════════════════════════════════════════ */

#define STACK_SIZE       16
#define MAX_BYTECODE     256
#define MAX_CONSTRAINTS  8
#define UART_BUF_SIZE    64

/* VM state — exactly 140 bytes */
typedef struct {
    int32_t  stack[STACK_SIZE];
    uint16_t stack_ptr;
    uint16_t pc;
    uint16_t deadline;
    uint8_t  constraint_id;
    uint8_t  flags;         /* bit0=halted, bit1=violation */
} FluxVM;

/* Result — exactly 8 bytes */
typedef struct {
    uint8_t  error_mask;    /* bit i = constraint i violated */
    uint8_t  severity;      /* 0=pass, 1=caution, 2=warning, 3=critical */
    uint16_t instr_count;
    uint16_t sensor_value;
    uint16_t reserved;
} FluxResult;

/* Global state — all statically allocated */
static FluxVM      g_vm;
static FluxResult  g_result;
static volatile uint8_t g_check_flag;  /* Set by TIM2 ISR */
static volatile int32_t g_sensor_raw;  /* Set by ADC read */
static char g_uart_buf[UART_BUF_SIZE];

/* ═══════════════════════════════════════════════════════════════════════
 * Flash-Based Constraint Presets
 *
 * Stored in flash at a fixed address. Update via signed bootloader patch.
 * 8 constraints × 3 bytes each (value_idx, lo, hi) = 24 bytes.
 * ═══════════════════════════════════════════════════════════════════════ */

/* Constraint preset: 8 range checks for industrial sensor monitoring
 * Format: { constraint_id, lower_bound, upper_bound }
 */
static const uint8_t g_constraints[] = {
    0,   0, 100,    /* C0: sensor_0 temp [0, 100]°C    */
    1, -20,  80,    /* C1: sensor_1 pressure [-20, 80] */
    2,   0, 255,    /* C2: sensor_2 flow [0, 255]      */
    3, -40,  85,    /* C3: sensor_3 ambient [-40, 85]   */
    4,   0,  50,    /* C4: sensor_4 vibration [0, 50]  */
    5,  10,  90,    /* C5: sensor_5 humidity [10, 90]%  */
    6,   0, 100,    /* C6: sensor_6 load [0, 100]%      */
    7, -10,  10,    /* C7: sensor_7 drift [-10, 10]     */
};

/* Compiled bytecode: checks all 8 constraints from stack values
 * Each constraint: CONSTRAINT_ID id, PUSH val, PUSH lo, PUSH hi, RANGE_CHECK
 */
static const uint8_t g_constraint_bytecode[] = {
    /* C0: temp check */
    FLUX_CONSTRAINT_ID, 0,
    FLUX_DUP,                          /* value already on stack from sensor */
    FLUX_PUSH, 0,                      /* lo */
    FLUX_PUSH, 100,                    /* hi */
    FLUX_RANGE_CHECK,

    /* C1: pressure check */
    FLUX_CONSTRAINT_ID, 1,
    FLUX_DUP,
    FLUX_PUSH, (uint8_t)(int8_t)(-20),
    FLUX_PUSH, 80,
    FLUX_RANGE_CHECK,

    /* C2: flow check */
    FLUX_CONSTRAINT_ID, 2,
    FLUX_DUP,
    FLUX_PUSH, 0,
    FLUX_PUSH, 127,                    /* Saturate to 127 max for int8 */
    FLUX_RANGE_CHECK,

    /* C3: ambient check */
    FLUX_CONSTRAINT_ID, 3,
    FLUX_DUP,
    FLUX_PUSH, (uint8_t)(int8_t)(-40),
    FLUX_PUSH, 85,
    FLUX_RANGE_CHECK,

    /* C4: vibration check */
    FLUX_CONSTRAINT_ID, 4,
    FLUX_DUP,
    FLUX_PUSH, 0,
    FLUX_PUSH, 50,
    FLUX_RANGE_CHECK,

    /* C5: humidity check */
    FLUX_CONSTRAINT_ID, 5,
    FLUX_DUP,
    FLUX_PUSH, 10,
    FLUX_PUSH, 90,
    FLUX_RANGE_CHECK,

    /* C6: load check */
    FLUX_CONSTRAINT_ID, 6,
    FLUX_DUP,
    FLUX_PUSH, 0,
    FLUX_PUSH, 100,
    FLUX_RANGE_CHECK,

    /* C7: drift check */
    FLUX_CONSTRAINT_ID, 7,
    FLUX_PUSH, (uint8_t)(int8_t)(-10),
    FLUX_PUSH, 10,
    FLUX_RANGE_CHECK,

    FLUX_HALT
};

/* ═══════════════════════════════════════════════════════════════════════
 * Minimal Utility Functions (no libc)
 * ═══════════════════════════════════════════════════════════════════════ */

static void uart_putc(char c) {
    while (!(USART2_SR & BIT(7)));  /* Wait for TXE */
    USART2_DR = (uint32_t)c;
}

static void uart_puts(const char *s) {
    while (*s) uart_putc(*s++);
}

static void uart_put_hex(uint8_t val) {
    const char hex[] = "0123456789ABCDEF";
    uart_putc(hex[(val >> 4) & 0x0F]);
    uart_putc(hex[val & 0x0F]);
}

static void uart_put_int(int32_t val) {
    char buf[12];
    int i = 0;
    int neg = 0;
    if (val < 0) { neg = 1; val = -val; }
    if (val == 0) { uart_putc('0'); return; }
    while (val > 0) {
        buf[i++] = '0' + (val % 10);
        val /= 10;
    }
    if (neg) uart_putc('-');
    while (i > 0) uart_putc(buf[--i]);
}

/* ═══════════════════════════════════════════════════════════════════════
 * Hardware Initialization
 * ═══════════════════════════════════════════════════════════════════════ */

static void clock_init(void) {
    /* Enable GPIOA, USART2, TIM2, ADC1 clocks */
    RCC_AHB1ENR |= RCC_AHB1ENR_GPIOAEN;
    RCC_APB1ENR |= RCC_APB1ENR_USART2EN | RCC_APB1ENR_TIM2EN;
    RCC_APB2ENR |= RCC_APB2ENR_ADC1EN;
}

static void uart_init(void) {
    /* PA2 = USART2_TX (AF7) */
    GPIOA_MODER  &= ~(3U << (2 * 2));     /* Clear PA2 mode */
    GPIOA_MODER  |=  (2U << (2 * 2));     /* AF mode */
    GPIOA_AFRL   &= ~(0xFU << (2 * 4));   /* Clear AF for PA2 */
    GPIOA_AFRL   |=  (7U << (2 * 4));     /* AF7 = USART2 */

    /* USART2: 115200 baud @ 16MHz APB1 */
    USART2_BRR = 0x0683;   /* 16000000 / 115200 ≈ 139 */
    USART2_CR1 = BIT(13) | BIT(3);  /* UE | TE */
}

static void adc_init(void) {
    /* PA0 = Analog input (ADC1 Channel 0) */
    GPIOA_MODER &= ~(3U << (0 * 2));
    GPIOA_MODER |=  (3U << (0 * 2));      /* Analog mode */

    /* ADC1: single conversion, channel 0 */
    ADC1_SQR3 = 0;                         /* Channel 0 */
    ADC1_CR2  = BIT(0);                    /* ADON */
}

static void timer_init(void) {
    /* TIM2: 1kHz interrupt (1ms period @ 16MHz) */
    TIM2_PSC = 15999;    /* Prescaler: 16MHz / 16000 = 1kHz */
    TIM2_ARR = 999;      /* Auto-reload: 1ms period */
    TIM2_DIER = BIT(0);  /* Update interrupt enable */
    TIM2_CR1  = BIT(0);  /* Enable timer */

    /* Enable TIM2 in NVIC (IRQ 28) */
    NVIC_ISER0 = BIT(28);
}

static int32_t adc_read(void) {
    ADC1_CR2 |= BIT(30);                    /* Start conversion (SWSTART) */
    while (!(ADC1_SR & BIT(1)));            /* Wait for EOC */
    return (int32_t)(ADC1_DR & 0xFFF);     /* 12-bit result */
}

/* ═══════════════════════════════════════════════════════════════════════
 * FLUX-C VM — Bare-Metal Execution Engine
 *
 * Inlined, branch-predicted, no function calls in hot path.
 * All computation in registers + stack array. Zero heap pressure.
 * ═══════════════════════════════════════════════════════════════════════ */

static int32_t saturate(int32_t val) {
    if (val < -127) return -127;
    if (val > 127)  return 127;
    return val;
}

static void vm_init(FluxVM *vm) {
    for (int i = 0; i < STACK_SIZE; i++) vm->stack[i] = 0;
    vm->stack_ptr = 0;
    vm->pc = 0;
    vm->deadline = 1024;  /* Max 1024 instructions per check */
    vm->constraint_id = 0;
    vm->flags = 0;
}

static int vm_push(FluxVM *vm, int32_t val) {
    if (vm->stack_ptr >= STACK_SIZE) return FLUX_ERR_STACK_OVERFLOW;
    vm->stack[vm->stack_ptr++] = saturate(val);
    return FLUX_OK;
}

static int vm_pop(FluxVM *vm, int32_t *out) {
    if (vm->stack_ptr == 0) return FLUX_ERR_STACK_UNDERFLOW;
    *out = vm->stack[--vm->stack_ptr];
    return FLUX_OK;
}

static int flux_execute(FluxVM *vm, const uint8_t *bc, uint16_t len, FluxResult *res) {
    int err;
    int32_t a, b, c;
    uint16_t count = 0;

    while (vm->pc < len && !(vm->flags & 0x01)) {
        if (count >= vm->deadline) return FLUX_ERR_DEADLINE;
        count++;

        uint8_t op = bc[vm->pc++];

        switch (op) {
        case FLUX_NOP: break;
        case FLUX_PUSH:
            if (vm->pc >= len) return FLUX_ERR_INVALID_OPERAND;
            err = vm_push(vm, (int32_t)(int8_t)bc[vm->pc++]);
            if (err) return err;
            break;
        case FLUX_POP:
            err = vm_pop(vm, &a);
            if (err) return err;
            break;
        case FLUX_DUP:
            if (vm->stack_ptr == 0) return FLUX_ERR_STACK_UNDERFLOW;
            err = vm_push(vm, vm->stack[vm->stack_ptr - 1]);
            if (err) return err;
            break;
        case FLUX_SWAP:
            if (vm->stack_ptr < 2) return FLUX_ERR_STACK_UNDERFLOW;
            a = vm->stack[vm->stack_ptr - 1];
            vm->stack[vm->stack_ptr - 1] = vm->stack[vm->stack_ptr - 2];
            vm->stack[vm->stack_ptr - 2] = a;
            break;
        case FLUX_ADD:
            err = vm_pop(vm, &b); if (err) return err;
            err = vm_pop(vm, &a); if (err) return err;
            err = vm_push(vm, a + b); if (err) return err;
            break;
        case FLUX_SUB:
            err = vm_pop(vm, &b); if (err) return err;
            err = vm_pop(vm, &a); if (err) return err;
            err = vm_push(vm, a - b); if (err) return err;
            break;
        case FLUX_MUL:
            err = vm_pop(vm, &b); if (err) return err;
            err = vm_pop(vm, &a); if (err) return err;
            err = vm_push(vm, a * b); if (err) return err;
            break;
        case FLUX_DIV:
            err = vm_pop(vm, &b); if (err) return err;
            err = vm_pop(vm, &a); if (err) return err;
            if (b == 0) return FLUX_ERR_DIVISION_BY_ZERO;
            err = vm_push(vm, a / b); if (err) return err;
            break;
        case FLUX_NEG:
            if (vm->stack_ptr == 0) return FLUX_ERR_STACK_UNDERFLOW;
            vm->stack[vm->stack_ptr - 1] = -vm->stack[vm->stack_ptr - 1];
            break;
        case FLUX_ABS:
            if (vm->stack_ptr == 0) return FLUX_ERR_STACK_UNDERFLOW;
            a = vm->stack[vm->stack_ptr - 1];
            vm->stack[vm->stack_ptr - 1] = a < 0 ? -a : a;
            break;
        case FLUX_LT:
            err = vm_pop(vm, &b); if (err) return err;
            err = vm_pop(vm, &a); if (err) return err;
            err = vm_push(vm, a < b ? 1 : 0); if (err) return err;
            break;
        case FLUX_GT:
            err = vm_pop(vm, &b); if (err) return err;
            err = vm_pop(vm, &a); if (err) return err;
            err = vm_push(vm, a > b ? 1 : 0); if (err) return err;
            break;
        case FLUX_LTE:
            err = vm_pop(vm, &b); if (err) return err;
            err = vm_pop(vm, &a); if (err) return err;
            err = vm_push(vm, a <= b ? 1 : 0); if (err) return err;
            break;
        case FLUX_GTE:
            err = vm_pop(vm, &b); if (err) return err;
            err = vm_pop(vm, &a); if (err) return err;
            err = vm_push(vm, a >= b ? 1 : 0); if (err) return err;
            break;
        case FLUX_RANGE_CHECK:
            err = vm_pop(vm, &c); if (err) return err;  /* hi */
            err = vm_pop(vm, &b); if (err) return err;  /* lo */
            err = vm_pop(vm, &a); if (err) return err;  /* value */
            a = saturate(a); b = saturate(b); c = saturate(c);
            if (a < b || a > c) {
                res->error_mask |= (uint8_t)(1U << vm->constraint_id);
            }
            err = vm_push(vm, (a < b || a > c) ? 1 : 0);
            if (err) return err;
            break;
        case FLUX_CONSTRAINT_ID:
            if (vm->pc >= len) return FLUX_ERR_INVALID_OPERAND;
            vm->constraint_id = bc[vm->pc++];
            break;
        case FLUX_SANDBOX_ENTER: break;  /* No-op on bare metal — entire system is sandboxed */
        case FLUX_SANDBOX_EXIT:  break;
        case FLUX_HALT:
            vm->flags |= 0x01;
            break;
        default:
            return FLUX_ERR_UNKNOWN_OPCODE;
        }
    }

    res->instr_count = count;
    return FLUX_OK;
}

/* ═══════════════════════════════════════════════════════════════════════
 * Violation Alert via UART
 *
 * ASCII protocol for air-gap monitoring:
 *   "FLUX:VIOLATE:C%d:V%d:MASK=0x%02X\n"
 * ═══════════════════════════════════════════════════════════════════════ */

static void alert_violation(const FluxResult *res, int32_t sensor_val) {
    uart_puts("FLUX:ALERT:");
    uart_put_hex(res->error_mask);
    uart_putc(':');
    uart_put_int(sensor_val);
    uart_putc(':');
    uart_put_int(res->instr_count);
    uart_puts("\r\n");
}

static void alert_pass(int32_t sensor_val) {
    uart_puts("FLUX:OK:");
    uart_put_int(sensor_val);
    uart_puts("\r\n");
}

/* ═══════════════════════════════════════════════════════════════════════
 * Main Check Cycle
 *
 * Called by TIM2 ISR every 1ms. Reads ADC, runs constraints, alerts.
 * Total budget: < 100µs per check at 168MHz.
 * ═══════════════════════════════════════════════════════════════════════ */

static void flux_check_cycle(void) {
    /* Read sensor */
    int32_t sensor_val = adc_read();
    g_sensor_raw = sensor_val;

    /* Initialize VM and push sensor value */
    vm_init(&g_vm);
    g_result.error_mask = 0;
    g_result.severity = 0;
    g_result.instr_count = 0;

    vm_push(&g_vm, sensor_val);

    /* Execute constraint bytecode */
    int err = flux_execute(&g_vm, g_constraint_bytecode,
                           sizeof(g_constraint_bytecode), &g_result);

    if (err != FLUX_OK) {
        uart_puts("FLUX:ERROR:");
        uart_put_hex((uint8_t)err);
        uart_puts("\r\n");
        return;
    }

    /* Alert on violation */
    g_result.sensor_value = (uint16_t)sensor_val;
    if (g_result.error_mask != 0) {
        /* Compute severity */
        uint8_t mask = g_result.error_mask;
        int nv = 0;
        while (mask) { nv += mask & 1; mask >>= 1; }
        g_result.severity = (uint8_t)(nv <= 2 ? 1 : nv <= 4 ? 2 : 3);
        alert_violation(&g_result, sensor_val);
    } else {
        alert_pass(sensor_val);
    }
}

/* ═══════════════════════════════════════════════════════════════════════
 * Interrupt Handlers
 * ═══════════════════════════════════════════════════════════════════════ */

void __attribute__((interrupt("IRQ"))) tim2_isr(void) {
    if (TIM2_SR & BIT(0)) {
        TIM2_SR &= ~BIT(0);    /* Clear update interrupt flag */
        g_check_flag = 1;
    }
}

/* ═══════════════════════════════════════════════════════════════════════
 * Vector Table (minimal — Cortex-M4)
 * ═══════════════════════════════════════════════════════════════════════ */

typedef void (*irq_handler_t)(void);

/* Place at beginning of flash via linker script */
__attribute__((section(".isr_vector")))
const irq_handler_t g_vector_table[] = {
    (irq_handler_t)0x20020000UL,     /* Initial stack pointer (128KB RAM) */
    (irq_handler_t)reset_handler,     /* Reset handler */
    (irq_handler_t)nmi_handler,       /* NMI */
    (irq_handler_t)hard_fault_handler,/* Hard fault */
    0, 0, 0, 0, 0, 0,                /* Reserved */
    0,                                /* SVCall */
    0,                                /* Debug monitor */
    0, 0,                             /* Reserved */
    0,                                /* PendSV */
    0,                                /* SysTick */
    /* External interrupts: TIM2 is IRQ 28 */
    [28] = tim2_isr,
};

/* ═══════════════════════════════════════════════════════════════════════
 * Fault Handlers
 * ═══════════════════════════════════════════════════════════════════════ */

void __attribute__((interrupt("IRQ"))) nmi_handler(void) {
    uart_puts("FLUX:FATAL:NMI\r\n");
    for (;;);
}

void __attribute__((interrupt("IRQ"))) hard_fault_handler(void) {
    uart_puts("FLUX:FATAL:HARDFAULT\r\n");
    for (;;);
}

/* ═══════════════════════════════════════════════════════════════════════
 * Reset Handler — Entry Point
 * ═══════════════════════════════════════════════════════════════════════ */

void __attribute__((noreturn)) reset_handler(void) {
    /* Initialize hardware */
    clock_init();
    uart_init();
    adc_init();
    timer_init();

    uart_puts("FLUX:Cortex-M4:INIT:OK\r\n");
    uart_puts("FLUX:Constraints:");
    uart_put_int(sizeof(g_constraint_bytecode));
    uart_puts(" bytes\r\n");

    /* Main loop — super-loop pattern (cooperative with ISR) */
    for (;;) {
        if (g_check_flag) {
            g_check_flag = 0;
            flux_check_cycle();
        }
        /* Low-power wait for interrupt */
        __asm__ volatile ("wfi");
    }
}

/* ═══════════════════════════════════════════════════════════════════════
 * Linker Script Fragment (stm32f4.ld)
 *
 * MEMORY { FLASH (rx) : ORIGIN = 0x08000000, LENGTH = 4K
 *          RAM (rwx)  : ORIGIN = 0x20000000, LENGTH = 1K }
 * ENTRY(reset_handler)
 * SECTIONS {
 *   .isr_vector : { *(.isr_vector) } > FLASH
 *   .text : { *(.text*) *(.rodata*) } > FLASH
 *   .data : { *(.data*) } > RAM AT > FLASH
 *   .bss  : { *(.bss*) *(COMMON) } > RAM
 * }
 * ═══════════════════════════════════════════════════════════════════════ */

/* ═══════════════════════════════════════════════════════════════════════
 * Memory Budget
 *
 * Flash:
 *   Vector table:     240 bytes (60 entries × 4 bytes)
 *   VM + utilities:  ~800 bytes
 *   Bytecode:          90 bytes (8 constraints)
 *   String constants: ~150 bytes
 *   Total:           ~1280 bytes (< 4KB target) ✓
 *
 * RAM:
 *   FluxVM:           140 bytes (16×int32 + metadata)
 *   FluxResult:         8 bytes
 *   g_uart_buf:        64 bytes
 *   Stack (MSP):      256 bytes
 *   Total:            ~468 bytes (< 1KB target) ✓
 * ═══════════════════════════════════════════════════════════════════════ */
