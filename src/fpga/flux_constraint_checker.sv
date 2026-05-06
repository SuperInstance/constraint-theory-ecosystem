// FLUX Constraint Checker — SystemVerilog (FPGA)
// Target: Xilinx Zynq UltraScale+ (DO-254 DAL A path)
// 
// Checks 8 INT8 constraints per sensor in a single clock cycle.
// Latency: 3 cycles from input to result.
// Throughput: 1 sensor per cycle at 250MHz = 250M sensors/sec.
//
// Portability: Also synthesizes on Intel Cyclone 10GX, Lattice ECP5.
//
// (c) 2026 SuperInstance — Apache 2.0

module flux_constraint_checker #(
    parameter N_CONSTRAINTS = 8,
    parameter INT8_MIN = -127,
    parameter INT8_MAX = 127
)(
    input  logic                   clk,
    input  logic                   rst_n,
    
    // Sensor input (one per cycle)
    input  logic signed [7:0]      sensor_val,
    input  logic                   sensor_valid,
    
    // Bounds (loaded once, held constant)
    input  logic signed [7:0]      bound_lo [N_CONSTRAINTS],
    input  logic signed [7:0]      bound_hi [N_CONSTRAINTS],
    input  logic                   bounds_loaded,
    
    // Result output (3 cycle latency)
    output logic [N_CONSTRAINTS-1:0] error_mask,
    output logic [1:0]               severity,
    output logic [N_CONSTRAINTS-1:0]  violated_lo,
    output logic [N_CONSTRAINTS-1:0]  violated_hi,
    output logic                     result_valid,
    
    // Statistics (accumulated)
    output logic [31:0]              stat_pass,
    output logic [31:0]              stat_caution,
    output logic [31:0]              stat_warning,
    output logic [31:0]              stat_critical
);

    // ═══════════════════════════════════════════════════════
    // Pipeline Stage 1: Saturate input
    // ═══════════════════════════════════════════════════════
    
    logic signed [7:0] sat_val;
    logic              stage1_valid;
    
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sat_val      <= 8'sd0;
            stage1_valid <= 1'b0;
        end else if (sensor_valid) begin
            // Saturate to [-127, 127]
            if (sensor_val < INT8_MIN)
                sat_val <= INT8_MIN;
            else if (sensor_val > INT8_MAX)
                sat_val <= INT8_MAX;
            else
                sat_val <= sensor_val;
            stage1_valid <= 1'b1;
        end else begin
            stage1_valid <= 1'b0;
        end
    end

    // ═══════════════════════════════════════════════════════
    // Pipeline Stage 2: Evaluate all constraints (combinational)
    // ═══════════════════════════════════════════════════════
    
    logic [N_CONSTRAINTS-1:0] cmp_lo_fail;
    logic [N_CONSTRAINTS-1:0] cmp_hi_fail;
    logic [N_CONSTRAINTS-1:0] cmp_error;
    logic        stage2_valid;
    
    genvar i;
    generate
        for (i = 0; i < N_CONSTRAINTS; i = i + 1) begin : constraint_check
            // Saturate bounds
            logic signed [7:0] sat_lo, sat_hi;
            
            always @(*) begin
                if (bound_lo[i] < INT8_MIN)
                    sat_lo = INT8_MIN;
                else if (bound_lo[i] > INT8_MAX)
                    sat_lo = INT8_MAX;
                else
                    sat_lo = bound_lo[i];
                    
                if (bound_hi[i] < INT8_MIN)
                    sat_hi = INT8_MIN;
                else if (bound_hi[i] > INT8_MAX)
                    sat_hi = INT8_MAX;
                else
                    sat_hi = bound_hi[i];
            end
            
            // Compare (registered)
            always_ff @(posedge clk or negedge rst_n) begin
                if (!rst_n) begin
                    cmp_lo_fail[i] <= 1'b0;
                    cmp_hi_fail[i] <= 1'b0;
                    cmp_error[i]   <= 1'b0;
                end else if (stage1_valid && bounds_loaded) begin
                    cmp_lo_fail[i] <= (sat_val < sat_lo);
                    cmp_hi_fail[i] <= (sat_val > sat_hi);
                    cmp_error[i]   <= (sat_val < sat_lo) || (sat_val > sat_hi);
                end
            end
        end
    endgenerate
    
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            stage2_valid <= 1'b0;
        else
            stage2_valid <= stage1_valid && bounds_loaded;
    end

    // ═══════════════════════════════════════════════════════
    // Pipeline Stage 3: Compute severity and output
    // ═══════════════════════════════════════════════════════
    
    logic [3:0] violated_count;
    
    // Count violated constraints (popcount)
    always @(*) begin
        violated_count = 0;
        for (int j = 0; j < N_CONSTRAINTS; j++) begin
            if (cmp_error[j]) violated_count = violated_count + 1;
        end
    end
    
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            error_mask   <= '0;
            severity     <= 2'd0;
            violated_lo  <= '0;
            violated_hi  <= '0;
            result_valid <= 1'b0;
        end else if (stage2_valid) begin
            error_mask  <= cmp_error;
            violated_lo <= cmp_lo_fail;
            violated_hi <= cmp_hi_fail;
            
            // Severity logic
            if (violated_count == 0)
                severity <= 2'd0;  // PASS
            else if (violated_count <= N_CONSTRAINTS / 4)
                severity <= 2'd1;  // CAUTION
            else if (violated_count <= N_CONSTRAINTS / 2)
                severity <= 2'd2;  // WARNING
            else
                severity <= 2'd3;  // CRITICAL
            
            result_valid <= 1'b1;
            
            // Update statistics
            case (severity)
                2'd0: stat_pass     <= stat_pass + 1;
                2'd1: stat_caution  <= stat_caution + 1;
                2'd2: stat_warning  <= stat_warning + 1;
                2'd3: stat_critical <= stat_critical + 1;
            endcase
        end else begin
            result_valid <= 1'b0;
        end
    end

endmodule
