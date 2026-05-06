// FLUX Constraint Engine — WebGPU/WGSL Shader
// Cross-vendor GPU constraint checking via WebGPU
// Runs on NVIDIA, AMD, Intel, Apple Silicon — any GPU with WebGPU support
//
// Usage: Load via WebGPU API, dispatch with n_sensors / 256 workgroups
// Input: bounds buffer (16 bytes/sensor), values buffer (1 byte/sensor)
// Output: results buffer (4 bytes/sensor)

struct FluxBounds {
    lo: array<i32, 8>,
    hi: array<i32, 8>,
}

struct FluxResult {
    error_mask: u32,
    severity: u32,
    violated_lo: u32,
    violated_hi: u32,
}

struct Params {
    n_sensors: u32,
    n_constraints: u32,
    pad0: u32,
    pad1: u32,
}

@group(0) @binding(0) var<uniform> params: Params;
@group(0) @binding(1) var<storage, read> bounds: array<FluxBounds>;
@group(0) @binding(2) var<storage, read> values: array<i32>;
@group(0) @binding(3) var<storage, read_write> results: array<FluxResult>;
@group(0) @binding(4) var<storage, read_write> stats: array<atomic<u32>>;

fn saturate(val: i32) -> i32 {
    return clamp(val, -127, 127);
}

@compute @workgroup_size(256)
fn flux_check(@builtin(global_invocation_id) gid: vec3<u32>) {
    let idx = gid.x;
    if (idx >= params.n_sensors) {
        return;
    }

    let val = saturate(values[idx]);
    let b = bounds[idx];

    var error_mask: u32 = 0u;
    var violated_lo: u32 = 0u;
    var violated_hi: u32 = 0u;
    var violated_count: u32 = 0u;

    for (var i: u32 = 0u; i < params.n_constraints; i = i + 1u) {
        let lo = saturate(b.lo[i]);
        let hi = saturate(b.hi[i]);

        let lo_fail = val < lo;
        let hi_fail = val > hi;

        if (lo_fail || hi_fail) {
            error_mask = error_mask | (1u << i);
            violated_count = violated_count + 1u;
        }
        if (lo_fail) {
            violated_lo = violated_lo | (1u << i);
        }
        if (hi_fail) {
            violated_hi = violated_hi | (1u << i);
        }
    }

    // Severity
    var severity: u32 = 0u;
    if (violated_count == 0u) {
        severity = 0u;
    } else if (violated_count <= params.n_constraints / 4u) {
        severity = 1u;
    } else if (violated_count <= params.n_constraints / 2u) {
        severity = 2u;
    } else {
        severity = 3u;
    }

    results[idx].error_mask = error_mask;
    results[idx].severity = severity;
    results[idx].violated_lo = violated_lo;
    results[idx].violated_hi = violated_hi;

    // Stats (4 severity buckets)
    atomicAdd(&stats[severity], 1u);
}
