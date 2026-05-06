/**
 * FLUX WebGPU Host — Cross-vendor GPU constraint checking
 * 
 * Loads the WGSL shader and dispatches constraint checking
 * on any GPU (NVIDIA, AMD, Intel, Apple Silicon) via WebGPU.
 * 
 * Usage:
 *   const engine = await FluxWebGPU.create(constraints);
 *   const result = await engine.check(sensorValues);
 *   console.log(result.stats);
 */

export class FluxWebGPU {
  constructor(device, pipeline, bindGroupLayout, constraints) {
    this.device = device;
    this.pipeline = pipeline;
    this.bindGroupLayout = bindGroupLayout;
    this.constraints = constraints;
    this.n_constraints = constraints.length;
  }

  static async create(constraints) {
    if (!navigator.gpu) {
      throw new Error('WebGPU not supported in this browser');
    }

    const adapter = await navigator.gpu.requestAdapter();
    if (!adapter) {
      throw new Error('No WebGPU adapter found');
    }

    const device = await adapter.requestDevice();
    const shaderCode = FLUX_WGSL_SHADER; // Embedded or loaded

    const shaderModule = device.createShaderModule({ code: shaderCode });

    // Bind group layout
    const bindGroupLayout = device.createBindGroupLayout({
      entries: [
        { binding: 0, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'uniform' } },
        { binding: 1, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'read-only-storage' } },
        { binding: 2, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'read-only-storage' } },
        { binding: 3, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'storage' } },
        { binding: 4, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'storage' } },
      ],
    });

    const pipeline = device.createComputePipeline({
      layout: device.createPipelineLayout({ bindGroupLayouts: [bindGroupLayout] }),
      compute: { module: shaderModule, entryPoint: 'flux_check' },
    });

    return new FluxWebGPU(device, pipeline, bindGroupLayout, constraints);
  }

  async check(values) {
    const n = values.length;
    const workgroupCount = Math.ceil(n / 256);

    // Create buffers
    const paramsBuffer = this.device.createBuffer({
      size: 16, usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
    });
    this.device.queue.writeBuffer(paramsBuffer, 0, new Uint32Array([n, this.n_constraints, 0, 0]));

    // Bounds buffer: 8 × i32 lo + 8 × i32 hi = 64 bytes per sensor
    const boundsData = new Int32Array(n * 16);
    for (let s = 0; s < n; s++) {
      for (let c = 0; c < 8; c++) {
        const con = this.constraints[c] || { lo: -127, hi: 127 };
        boundsData[s * 16 + c] = Math.max(-127, Math.min(127, con.lo));
        boundsData[s * 16 + 8 + c] = Math.max(-127, Math.min(127, con.hi));
      }
    }
    const boundsBuffer = this.device.createBuffer({
      size: boundsData.byteLength, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
    });
    this.device.queue.writeBuffer(boundsBuffer, 0, boundsData);

    // Values buffer
    const valuesData = new Int32Array(values.map(v => Math.max(-127, Math.min(127, v | 0))));
    const valuesBuffer = this.device.createBuffer({
      size: valuesData.byteLength, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
    });
    this.device.queue.writeBuffer(valuesBuffer, 0, valuesData);

    // Results buffer: 4 × u32 per sensor
    const resultsBuffer = this.device.createBuffer({
      size: n * 16, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC,
    });

    // Stats buffer: 4 × u32
    const statsBuffer = this.device.createBuffer({
      size: 16, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC,
    });

    // Read buffers
    const resultsRead = this.device.createBuffer({
      size: n * 16, usage: GPUBufferUsage.MAP_READ | GPUBufferUsage.COPY_DST,
    });
    const statsRead = this.device.createBuffer({
      size: 16, usage: GPUBufferUsage.MAP_READ | GPUBufferUsage.COPY_DST,
    });

    // Bind group
    const bindGroup = this.device.createBindGroup({
      layout: this.bindGroupLayout,
      entries: [
        { binding: 0, resource: { buffer: paramsBuffer } },
        { binding: 1, resource: { buffer: boundsBuffer } },
        { binding: 2, resource: { buffer: valuesBuffer } },
        { binding: 3, resource: { buffer: resultsBuffer } },
        { binding: 4, resource: { buffer: statsBuffer } },
      ],
    });

    // Dispatch
    const encoder = this.device.createCommandEncoder();
    const pass = encoder.beginComputePass();
    pass.setPipeline(this.pipeline);
    pass.setBindGroup(0, bindGroup);
    pass.dispatchWorkgroups(workgroupCount);
    pass.end();

    encoder.copyBufferToBuffer(resultsBuffer, 0, resultsRead, 0, n * 16);
    encoder.copyBufferToBuffer(statsBuffer, 0, statsRead, 0, 16);

    this.device.queue.submit([encoder.finish()]);

    // Read results
    await resultsRead.mapAsync(GPUMapMode.READ);
    await statsRead.mapAsync(GPUMapMode.READ);

    const results = new Uint32Array(resultsRead.getMappedRange().slice(0));
    const stats = new Uint32Array(statsRead.getMappedRange().slice(0));

    resultsRead.unmap();
    statsRead.unmap();

    // Cleanup
    [paramsBuffer, boundsBuffer, valuesBuffer, resultsBuffer, statsBuffer, resultsRead, statsRead]
      .forEach(b => b.destroy());

    return {
      stats: {
        pass: stats[0],
        caution: stats[1],
        warning: stats[2],
        critical: stats[3],
      },
      sensors: n,
      constraints: this.n_constraints,
    };
  }

  destroy() {
    this.device.destroy();
  }
}
