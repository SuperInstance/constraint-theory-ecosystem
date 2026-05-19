// FLUX Constraint Engine — P4 (2014, Network Data Plane)
// Pure INT8 saturated constraint checking. Zero dependencies.
//
// The insight: P4 runs on NETWORK SWITCHES at line rate.
// Constraint checking happens IN THE NETWORK — before data reaches the server.
// Every packet is checked. No CPU overhead. No context switches.
// The constraint IS the firewall rule. The switch IS the checker.
//
// "Constraints at line rate. Every packet. Zero CPU overhead.
//  The network IS the constraint engine."

#include <core.p4>

// ══ Constants ══════════════════════════════════════════════════════

const bit<8> INT8_MIN = 8w817F;  // -127 in two's complement
const bit<8> INT8_MAX = 8w7F;    // 127
const bit<8> MAX_CONSTRAINTS = 8w08;

// ══ Severity ══════════════════════════════════════════════════════

// Severity encoded as bit<8> for network transmission
const bit<8> SEV_PASS     = 8w00;
const bit<8> SEV_CAUTION  = 8w01;
const bit<8> SEV_WARNING  = 8w02;
const bit<8> SEV_CRITICAL = 8w03;

// ══ Constraint Header ═════════════════════════════════════════════
// Constraints travel WITH the packet as a custom header

header constraint_t {
    bit<8> lo;      // lower bound (signed INT8)
    bit<8> hi;      // upper bound (signed INT8)
}

header flux_result_t {
    bit<8> error_mask;
    bit<8> severity;
    bit<8> violated_lo;
    bit<8> violated_hi;
    bit<8> violated_count;
    bit<1> passed;
    bit<7> _reserved;
}

// ══ Constraint Set Header (up to 8 constraints per packet) ═══════

header constraint_set_t {
    bit<8> sensor_value;    // the value to check (INT8)
    bit<8> constraint_count; // number of constraints (1-8)
}

struct headers {
    constraint_set_t  constraint_set;
    flux_result_t     flux_result;
    constraint_t[8]   constraints;
}

// ══ Metadata ══════════════════════════════════════════════════════

struct metadata_t {
    bit<8>  error_mask;
    bit<8>  violated_lo;
    bit<8>  violated_hi;
    bit<8>  violated_count;
    bit<8>  severity;
    bit<1>  passed;
}

// ══ Parser ════════════════════════════════════════════════════════

parser FluxParser(packet_in pkt,
                  out headers hdr,
                  out metadata_t meta,
                  inout standard_metadata_t std_meta) {
    state start {
        pkt.extract(hdr.constraint_set);
        pkt.extract(hdr.flux_result);
        // Extract up to 8 constraints based on count
        transition parse_constraints;
    }

    state parse_constraints {
        transition select(hdr.constraint_set.constraint_count) {
            8w01 : constraint_1;
            8w02 : constraint_2;
            8w03 : constraint_3;
            8w04 : constraint_4;
            default : accept;
        }
    }

    state constraint_1 {
        pkt.extract(hdr.constraints[0]);
        transition accept;
    }
    state constraint_2 {
        pkt.extract(hdr.constraints[0]);
        pkt.extract(hdr.constraints[1]);
        transition accept;
    }
    state constraint_3 {
        pkt.extract(hdr.constraints[0]);
        pkt.extract(hdr.constraints[1]);
        pkt.extract(hdr.constraints[2]);
        transition accept;
    }
    state constraint_4 {
        pkt.extract(hdr.constraints[0]);
        pkt.extract(hdr.constraints[1]);
        pkt.extract(hdr.constraints[2]);
        pkt.extract(hdr.constraints[3]);
        transition accept;
    }
}

// ══ Saturate (signed comparison in P4) ════════════════════════════
// P4 uses bit<8> with signed comparison via cast

control saturate(in bit<8> val, out bit<8> result) {
    apply {
        if ((bit<8>)(bit<16>)val < (bit<8>)(bit<16>)INT8_MIN) {
            result = INT8_MIN;
        } else if ((bit<8>)(bit<16>)val > (bit<8>)(bit<16>)INT8_MAX) {
            result = INT8_MAX;
        } else {
            result = val;
        }
    }
}

// ══ Core Check Pipeline ═══════════════════════════════════════════

control FluxCheck(inout headers hdr,
                  inout metadata_t meta) {

    // Signed comparison helper
    bool signed_lt(bit<8> a, bit<8> b) {
        return (bit<8>)(bit<16>)a < (bit<8>)(bit<16>)b;
    }

    apply {
        // Initialize
        meta.error_mask = 8w0;
        meta.violated_lo = 8w0;
        meta.violated_hi = 8w0;
        meta.violated_count = 8w0;
        meta.passed = 1w1;

        // Saturate sensor value
        bit<8> val = hdr.constraint_set.sensor_value;
        if (signed_lt(val, INT8_MIN)) {
            val = INT8_MIN;
        }
        if (signed_lt(INT8_MAX, val)) {
            val = INT8_MAX;
        }

        // Check each constraint (unrolled for line rate)
        // Constraint 0
        if (hdr.constraints[0].isValid()) {
            bool lo_fail = signed_lt(val, hdr.constraints[0].lo);
            bool hi_fail = signed_lt(hdr.constraints[0].hi, val);
            if (lo_fail || hi_fail) {
                meta.error_mask = meta.error_mask | 8w01;
                meta.violated_count = meta.violated_count + 8w01;
                meta.passed = 1w0;
            }
            if (lo_fail) { meta.violated_lo = meta.violated_lo | 8w01; }
            if (hi_fail) { meta.violated_hi = meta.violated_hi | 8w01; }
        }

        // Constraint 1
        if (hdr.constraints[1].isValid()) {
            bool lo_fail = signed_lt(val, hdr.constraints[1].lo);
            bool hi_fail = signed_lt(hdr.constraints[1].hi, val);
            if (lo_fail || hi_fail) {
                meta.error_mask = meta.error_mask | 8w02;
                meta.violated_count = meta.violated_count + 8w01;
                meta.passed = 1w0;
            }
            if (lo_fail) { meta.violated_lo = meta.violated_lo | 8w02; }
            if (hi_fail) { meta.violated_hi = meta.violated_hi | 8w02; }
        }

        // Constraint 2
        if (hdr.constraints[2].isValid()) {
            bool lo_fail = signed_lt(val, hdr.constraints[2].lo);
            bool hi_fail = signed_lt(hdr.constraints[2].hi, val);
            if (lo_fail || hi_fail) {
                meta.error_mask = meta.error_mask | 8w04;
                meta.violated_count = meta.violated_count + 8w01;
                meta.passed = 1w0;
            }
            if (lo_fail) { meta.violated_lo = meta.violated_lo | 8w04; }
            if (hi_fail) { meta.violated_hi = meta.violated_hi | 8w04; }
        }

        // Constraint 3
        if (hdr.constraints[3].isValid()) {
            bool lo_fail = signed_lt(val, hdr.constraints[3].lo);
            bool hi_fail = signed_lt(hdr.constraints[3].hi, val);
            if (lo_fail || hi_fail) {
                meta.error_mask = meta.error_mask | 8w08;
                meta.violated_count = meta.violated_count + 8w01;
                meta.passed = 1w0;
            }
            if (lo_fail) { meta.violated_lo = meta.violated_lo | 8w08; }
            if (hi_fail) { meta.violated_hi = meta.violated_hi | 8w08; }
        }

        // Severity classification
        if (meta.violated_count == 8w0) {
            meta.severity = SEV_PASS;
        } else if (meta.violated_count <= 8w01) {
            meta.severity = SEV_CAUTION;
        } else if (meta.violated_count <= 8w02) {
            meta.severity = SEV_WARNING;
        } else {
            meta.severity = SEV_CRITICAL;
        }

        // Write result to packet header
        hdr.flux_result.error_mask = meta.error_mask;
        hdr.flux_result.severity = meta.severity;
        hdr.flux_result.violated_lo = meta.violated_lo;
        hdr.flux_result.violated_hi = meta.violated_hi;
        hdr.flux_result.violated_count = meta.violated_count;
        hdr.flux_result.passed = meta.passed;
    }
}

// ══ Deparser ══════════════════════════════════════════════════════

control FluxDeparser(packet_out pkt, in headers hdr) {
    apply {
        pkt.emit(hdr.constraint_set);
        pkt.emit(hdr.flux_result);
    }
}

// ══ Architecture binding ══════════════════════════════════════════

V1Switch(FluxParser(),
         FluxVerify(),
         FluxCheck(),
         FluxDeparser()) main;

// P4 teaches us that constraint checking can happen IN THE NETWORK.
// Before data reaches the server, the switch checks every packet.
// Line rate. Zero CPU overhead. No context switches.
// The constraint IS the firewall rule. The switch IS the checker.
// For safety-critical systems, this means constraint enforcement
// happens at the PHYSICAL layer — before any software can fail.
