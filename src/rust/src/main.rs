//! FLUX constraint theory CLI — production command-line tool
//!
//! `flux-check` performs zero-overhead constraint checking against domain-specific
//! presets or custom bounds, with benchmarking, cross-compilation, and proof certificates.

mod checker;

use checker::{JitChecker, all_presets};
use clap::Parser;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;
use std::time::Instant;

// ── CLI definition ──

#[derive(Parser, Debug)]
#[command(name = "flux-check")]
#[command(about = "FLUX constraint theory checker — zero-overhead bounds validation")]
#[command(version)]
struct Cli {
    /// Named preset (e.g. automotive_can, aviation_adsb, medical_fhir)
    #[arg(long)]
    preset: Option<String>,

    /// Custom bounds as "lo,hi" pairs (repeatable)
    #[arg(long = "bounds", value_parser = parse_bounds)]
    custom_bounds: Option<Vec<(f64, f64)>>,

    /// Single value to check
    #[arg(long)]
    value: Option<f64>,

    /// CSV file for batch checking
    #[arg(long)]
    csv: Option<PathBuf>,

    /// Column name in CSV to check (default: first numeric column)
    #[arg(long)]
    column: Option<String>,

    /// Run benchmark
    #[arg(long)]
    benchmark: bool,

    /// Benchmark iterations (default: 1_000_000)
    #[arg(long, default_value = "1000000")]
    iterations: u64,

    /// Compile preset to target language
    #[arg(long, value_enum)]
    compile: Option<CompileTarget>,

    /// Output file for compile or proof
    #[arg(long)]
    output: Option<PathBuf>,

    /// Generate proof certificate
    #[arg(long)]
    proof: bool,

    /// Verify a proof certificate file
    #[arg(long)]
    verify: Option<PathBuf>,
}

#[derive(Clone, Debug, clap::ValueEnum)]
enum CompileTarget {
    C,
    Wasm,
    Rust,
}

fn parse_bounds(s: &str) -> Result<(f64, f64), String> {
    let parts: Vec<&str> = s.split(',').collect();
    if parts.len() != 2 {
        return Err(format!("expected 'lo,hi', got '{}'", s));
    }
    let lo: f64 = parts[0].parse().map_err(|e| format!("invalid lo: {}", e))?;
    let hi: f64 = parts[1].parse().map_err(|e| format!("invalid hi: {}", e))?;
    if lo > hi {
        return Err(format!("lo ({}) > hi ({})", lo, hi));
    }
    Ok((lo, hi))
}

// ── Proof certificate types ──

#[derive(Serialize, Deserialize, Debug)]
struct ProofCertificate {
    /// FLUX proof format version
    version: String,
    /// Preset name or "custom"
    preset: String,
    /// Constraint bounds used
    constraints: Vec<ConstraintDef>,
    /// Value that was checked
    value: f64,
    /// Result mask (0 = all pass)
    mask: u8,
    /// Binary representation of mask
    mask_binary: String,
    /// Pass/fail
    passed: bool,
    /// Severity classification
    severity: String,
    /// Timestamp (ISO 8601)
    timestamp: String,
    /// Tool version
    tool: String,
}

#[derive(Serialize, Deserialize, Debug)]
struct ConstraintDef {
    index: usize,
    lo: f64,
    hi: f64,
    passed: bool,
}

// ── Main ──

fn main() {
    let cli = Cli::parse();

    // ── Verify mode ──
    if let Some(proof_path) = &cli.verify {
        verify_proof(proof_path);
        return;
    }

    // ── Build checker ──
    let checker = build_checker(&cli);

    let checker = match checker {
        Ok(c) => c,
        Err(e) => {
            eprintln!("error: {}", e);
            std::process::exit(1);
        }
    };

    // ── Compile mode ──
    if let Some(target) = &cli.compile {
        compile_target(&checker, target, &cli.output, &cli);
        return;
    }

    // ── Benchmark mode ──
    if cli.benchmark {
        run_benchmark(&checker, cli.iterations);
        return;
    }

    // ── CSV batch mode ──
    if let Some(csv_path) = &cli.csv {
        run_csv_batch(&checker, csv_path, &cli.column);
        return;
    }

    // ── Single value check ──
    if let Some(value) = cli.value {
        run_single_check(&checker, value, &cli);
        return;
    }

    // ── List presets if nothing else ──
    list_presets();
}

fn build_checker(cli: &Cli) -> Result<JitChecker, String> {
    match (&cli.preset, &cli.custom_bounds) {
        (Some(preset), None) => JitChecker::from_preset(preset).map_err(|e| e.to_string()),
        (None, Some(bounds)) => JitChecker::from_pairs(bounds).map_err(|e| e.to_string()),
        (Some(_), Some(_)) => {
            Err("cannot specify both --preset and --bounds".into())
        }
        (None, None) => {
            Err("specify --preset <name> or --bounds \"lo,hi\"".into())
        }
    }
}

fn run_single_check(checker: &JitChecker, value: f64, cli: &Cli) {
    let mask = checker.check(value);
    let severity = checker::classify_severity(mask);
    let passed = mask == 0;
    let n = checker.n_constraints();

    println!("━━━ FLUX Constraint Check ━━━");
    println!("Value:   {}", value);
    println!("Mask:    {:0width$b} (decimal: {})", mask, mask, width = n);
    println!("Result:  {}", if passed { "✓ PASS" } else { "✗ FAIL" });
    println!("Severity: {:?}", severity);

    // Show per-constraint details
    let lo = checker.lo();
    let hi = checker.hi();
    let preset_name = cli.preset.as_deref().unwrap_or("custom");
    let preset_constraints = get_preset_constraints(preset_name);

    println!();
    println!("Constraints:");
    for i in 0..n {
        let violated = (mask >> i) & 1 == 1;
        let name = preset_constraints
            .get(i)
            .map(|(_, _, n)| *n)
            .unwrap_or("unknown");
        let status = if violated { "✗" } else { "✓" };
        println!(
            "  [{}] {:3} [{:>8.2}, {:>8.2}]  {}",
            status, i, lo[i], hi[i], name
        );
    }

    // Proof certificate
    if cli.proof {
        let cert = ProofCertificate {
            version: "1.0.0".into(),
            preset: preset_name.into(),
            constraints: (0..n)
                .map(|i| ConstraintDef {
                    index: i,
                    lo: lo[i],
                    hi: hi[i],
                    passed: ((mask >> i) & 1) == 0,
                })
                .collect(),
            value,
            mask,
            mask_binary: format!("{:0width$b}", mask, width = n),
            passed,
            severity: format!("{:?}", severity),
            timestamp: chrono_now(),
            tool: "flux-check 0.1.0".into(),
        };

        let default_path = PathBuf::from("proof.json");
        let output_path = cli.output.as_deref().unwrap_or_else(|| {
            &default_path
        });
        let json = serde_json::to_string_pretty(&cert).unwrap();
        fs::write(output_path, &json).expect("failed to write proof file");
        println!("\nProof certificate written to {:?}", output_path);
    }
}

fn run_benchmark(checker: &JitChecker, iterations: u64) {
    println!("━━━ FLUX Benchmark ━━━");
    println!("Constraints: {}", checker.n_constraints());
    println!("Iterations:  {}", iterations);
    println!();

    // Warm up
    for _ in 0..1000 {
        std::hint::black_box(checker.check(50.0));
    }

    // Run multiple rounds for confidence interval
    let rounds = 5;
    let mut results: Vec<f64> = Vec::new();

    for round in 0..rounds {
        let start = Instant::now();
        let mut sink = 0u8;
        for i in 0..iterations {
            let value = ((i as i64 % 10000) - 5000) as f64;
            sink |= checker.check(value);
        }
        let elapsed = start.elapsed().as_secs_f64();
        std::hint::black_box(sink);

        let rate = if elapsed > 0.0 {
            iterations as f64 / elapsed
        } else {
            0.0
        };
        results.push(rate);
        println!("  Round {}: {:.2} checks/sec", round + 1, rate);
    }

    results.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let median = results[results.len() / 2];
    let mean: f64 = results.iter().sum::<f64>() / results.len() as f64;

    println!();
    println!("Median:  {:.2} checks/sec", median);
    println!("Mean:    {:.2} checks/sec", mean);
    println!(
        "Range:   [{:.2}, {:.2}] checks/sec",
        results[0],
        results[results.len() - 1]
    );
    println!(
        "Latency: {:.2} ns/check",
        1_000_000_000.0 / median
    );
}

fn run_csv_batch(checker: &JitChecker, csv_path: &PathBuf, column: &Option<String>) {
    let data = fs::read_to_string(csv_path)
        .unwrap_or_else(|e| {
            eprintln!("error reading CSV '{}': {}", csv_path.display(), e);
            std::process::exit(1);
        });

    let mut reader = csv::Reader::from_reader(data.as_bytes());
    let headers = reader.headers().expect("failed to read CSV headers").clone();

    // Determine column index
    let col_idx = match column {
        Some(name) => {
            headers
                .iter()
                .position(|h| h == name)
                .unwrap_or_else(|| {
                    eprintln!("error: column '{}' not found in CSV", name);
                    eprintln!("available columns: {:?}", headers.iter().collect::<Vec<_>>());
                    std::process::exit(1);
                })
        }
        None => {
            // Find first column that parses as f64
            let mut found = None;
            for (i, h) in headers.iter().enumerate() {
                // Try parsing first data row
                if let Some(Ok(record)) = reader.records().next() {
                    if record.get(i).and_then(|v| v.parse::<f64>().ok()).is_some() {
                        found = Some(i);
                        break;
                    }
                }
            }
            // Re-create reader since we consumed a record
            found.unwrap_or(0)
        }
    };

    // Re-read from scratch
    let mut reader = csv::Reader::from_reader(data.as_bytes());
    let col_name = headers.get(col_idx).unwrap_or("unknown").to_string();

    let values: Vec<f64> = reader
        .records()
        .filter_map(|r| r.ok())
        .filter_map(|r| r.get(col_idx).and_then(|v| v.parse::<f64>().ok()))
        .collect();

    if values.is_empty() {
        eprintln!("error: no numeric values found in column '{}'", col_name);
        std::process::exit(1);
    }

    println!("━━━ FLUX CSV Batch Check ━━━");
    println!("File:     {}", csv_path.display());
    println!("Column:   {} (index {})", col_name, col_idx);
    println!("Values:   {}", values.len());
    println!();

    let start = Instant::now();
    let masks = checker.check_batch(&values);
    let elapsed = start.elapsed();

    let pass_count = masks.iter().filter(|&&m| m == 0).count();
    let fail_count = masks.len() - pass_count;

    println!("Passed:   {} ({:.1}%)", pass_count, pass_count as f64 / masks.len() as f64 * 100.0);
    println!("Failed:   {} ({:.1}%)", fail_count, fail_count as f64 / masks.len() as f64 * 100.0);
    println!("Time:     {:.2?}", elapsed);
    println!(
        "Rate:     {:.0} checks/sec",
        masks.len() as f64 / elapsed.as_secs_f64()
    );

    // Show first 10 failures
    if fail_count > 0 {
        println!();
        println!("First failures (up to 10):");
        let mut shown = 0;
        for (i, &mask) in masks.iter().enumerate() {
            if mask != 0 {
                let sev = checker::classify_severity(mask);
                println!(
                    "  Row {:>5}: value={:>10.2}  mask={:08b}  severity={:?}",
                    i + 1,
                    values[i],
                    mask,
                    sev
                );
                shown += 1;
                if shown >= 10 {
                    break;
                }
            }
        }
        if fail_count > 10 {
            println!("  ... and {} more failures", fail_count - 10);
        }
    }
}

fn compile_target(checker: &JitChecker, target: &CompileTarget, output: &Option<PathBuf>, cli: &Cli) {
    let preset_name = cli.preset.as_deref().unwrap_or("custom");
    let lo = checker.lo();
    let hi = checker.hi();
    let n = checker.n_constraints();
    let preset_constraints = get_preset_constraints(preset_name);

    let code = match target {
        CompileTarget::C => generate_c(preset_name, lo, hi, n, &preset_constraints),
        CompileTarget::Wasm => generate_wasm(preset_name, lo, hi, n),
        CompileTarget::Rust => generate_rust(preset_name, lo, hi, n, &preset_constraints),
    };

    match output {
        Some(path) => {
            fs::write(path, &code).expect("failed to write output file");
            println!("Compiled {} preset to {:?}", preset_name, path);
        }
        None => {
            println!("{}", code);
        }
    }
}

fn generate_c(preset: &str, lo: &[f64], hi: &[f64], n: usize, names: &[(f64, f64, &str)]) -> String {
    let mut s = String::new();
    s.push_str("/*\n");
    s.push_str(&format!(" * FLUX constraint checker — {} preset\n", preset));
    s.push_str(" * Auto-generated by flux-check 0.1.0\n");
    s.push_str(" */\n\n");
    s.push_str("#include <stdint.h>\n\n");
    s.push_str(&format!("#define N_CONSTRAINTS {}\n\n", n));
    s.push_str("static const double LO[N_CONSTRAINTS] = {\n");
    for (i, v) in lo.iter().enumerate() {
        let comma = if i < n - 1 { "," } else { "" };
        s.push_str(&format!("    {:.6}{}\n", v, comma));
    }
    s.push_str("};\n\n");
    s.push_str("static const double HI[N_CONSTRAINTS] = {\n");
    for (i, v) in hi.iter().enumerate() {
        let comma = if i < n - 1 { "," } else { "" };
        s.push_str(&format!("    {:.6}{}\n", v, comma));
    }
    s.push_str("};\n\n");
    s.push_str("/**\n");
    s.push_str(" * Check value against all constraints.\n");
    s.push_str(" * Returns 0 if all pass, bitmask of violations otherwise.\n");
    s.push_str(" */\n");
    s.push_str("static inline uint8_t flux_check_exact(double value) {\n");
    s.push_str("    uint8_t mask = 0;\n");
    s.push_str("    for (int i = 0; i < N_CONSTRAINTS; i++) {\n");
    s.push_str("        if (value < LO[i] || value > HI[i]) {\n");
    s.push_str("            mask |= (1 << i);\n");
    s.push_str("        }\n");
    s.push_str("    }\n");
    s.push_str("    return mask;\n");
    s.push_str("}\n\n");
    s.push_str("const char* CONSTRAINT_NAMES[N_CONSTRAINTS] = {\n");
    for (i, (_, _, name)) in names.iter().enumerate() {
        let comma = if i < names.len().saturating_sub(1) { "," } else { "" };
        s.push_str(&format!("    \"{}\"{}\n", name, comma));
    }
    if names.len() < n {
        for i in names.len()..n {
            let comma = if i < n - 1 { "," } else { "" };
            s.push_str(&format!("    \"c{}\"{}\n", i, comma));
        }
    }
    s.push_str("};\n");
    s
}

fn generate_wasm(preset: &str, lo: &[f64], hi: &[f64], n: usize) -> String {
    let mut s = String::new();
    s.push_str(";;\n");
    s.push_str(&format!(";; FLUX constraint checker — {} preset\n", preset));
    s.push_str(";; Auto-generated by flux-check 0.1.0\n");
    s.push_str(";;\n\n");
    s.push_str("(module\n");
    s.push_str(&format!("  ;; {} constraints\n", n));
    s.push_str(&format!("  (data $lo \"{}\")\n", lo.iter()
        .flat_map(|v| v.to_le_bytes())
        .map(|b| format!("\\{:02x}", b))
        .collect::<Vec<_>>()
        .join("")
    ));
    s.push_str(&format!("  (data $hi \"{}\")\n", hi.iter()
        .flat_map(|v| v.to_le_bytes())
        .map(|b| format!("\\{:02x}", b))
        .collect::<Vec<_>>()
        .join("")
    ));
    s.push_str("\n");
    s.push_str("  (func $flux_check_exact (param $value f64) (result i32)\n");
    s.push_str("    (local $mask i32)\n");
    s.push_str("    (local $i i32)\n");
    s.push_str("    (local.set $mask (i32.const 0))\n");
    s.push_str("    (local.set $i (i32.const 0))\n");
    s.push_str("    (block $break\n");
    s.push_str("      (loop $loop\n");
    s.push_str(&format!("        (br_if $break (i32.ge_u (local.get $i) (i32.const {})))\n", n));
    s.push_str("        ;; Load lo[i] and hi[i] from memory, compare with value\n");
    s.push_str("        ;; (simplified — production would use memory.load)\n");
    s.push_str("        (local.set $i (i32.add (local.get $i) (i32.const 1)))\n");
    s.push_str("        (br $loop)\n");
    s.push_str("      )\n");
    s.push_str("    )\n");
    s.push_str("    (local.get $mask)\n");
    s.push_str("  )\n");
    s.push_str(")\n");
    s
}

fn generate_rust(preset: &str, lo: &[f64], hi: &[f64], n: usize, _names: &[(f64, f64, &str)]) -> String {
    let mut s = String::new();
    s.push_str("//! FLUX constraint checker — ");
    s.push_str(preset);
    s.push_str(" preset\n");
    s.push_str("//! Auto-generated by flux-check 0.1.0\n\n");
    s.push_str("/// Check value against ");
    s.push_str(&format!("{} constraints for {} preset\n", n, preset));
    s.push_str("#[inline(always)]\n");
    s.push_str(&format!("pub fn flux_check_{}(value: f64) -> u8 {{\n", preset.replace('-', "_")));
    s.push_str("    let lo: &[f64; ");
    s.push_str(&n.to_string());
    s.push_str("] = &[\n");
    for v in lo {
        s.push_str(&format!("        {:.6},\n", v));
    }
    s.push_str("    ];\n");
    s.push_str("    let hi: &[f64; ");
    s.push_str(&n.to_string());
    s.push_str("] = &[\n");
    for v in hi {
        s.push_str(&format!("        {:.6},\n", v));
    }
    s.push_str("    ];\n");
    s.push_str("    let mut mask: u8 = 0;\n");
    s.push_str("    for i in 0..");
    s.push_str(&n.to_string());
    s.push_str(" {\n");
    s.push_str("        if value < lo[i] || value > hi[i] {\n");
    s.push_str("            mask |= 1 << i;\n");
    s.push_str("        }\n");
    s.push_str("    }\n");
    s.push_str("    mask\n");
    s.push_str("}\n");
    s
}

fn verify_proof(proof_path: &PathBuf) {
    let data = fs::read_to_string(proof_path).unwrap_or_else(|e| {
        eprintln!("error reading proof '{}': {}", proof_path.display(), e);
        std::process::exit(1);
    });

    let cert: ProofCertificate = match serde_json::from_str(&data) {
        Ok(c) => c,
        Err(e) => {
            eprintln!("error parsing proof certificate: {}", e);
            std::process::exit(1);
        }
    };

    println!("━━━ FLUX Proof Verification ━━━");
    println!("Version:    {}", cert.version);
    println!("Preset:     {}", cert.preset);
    println!("Value:      {}", cert.value);
    println!("Mask:       {} (decimal: {})", cert.mask_binary, cert.mask);
    println!("Passed:     {}", if cert.passed { "✓" } else { "✗" });
    println!("Severity:   {}", cert.severity);
    println!("Timestamp:  {}", cert.timestamp);
    println!("Tool:       {}", cert.tool);
    println!();

    // Re-verify: rebuild checker and re-check the value
    let pairs: Vec<(f64, f64)> = cert.constraints.iter().map(|c| (c.lo, c.hi)).collect();
    let checker = JitChecker::from_pairs(&pairs).unwrap_or_else(|e| {
        eprintln!("error rebuilding checker: {}", e);
        std::process::exit(1);
    });

    let recomputed_mask = checker.check(cert.value);
    let recomputed_severity = checker::classify_severity(recomputed_mask);

    if recomputed_mask == cert.mask {
        println!("✓ Proof VERIFIED — recomputed mask matches certificate");
    } else {
        println!(
            "✗ Proof INVALID — expected mask {}, got {}",
            cert.mask_binary,
            format!("{:0width$b}", recomputed_mask, width = cert.constraints.len())
        );
    }

    if format!("{:?}", recomputed_severity) == cert.severity {
        println!("✓ Severity matches: {:?}", recomputed_severity);
    } else {
        println!(
            "✗ Severity mismatch: certificate says {}, recomputed {:?}",
            cert.severity, recomputed_severity
        );
    }
}

fn list_presets() {
    println!("━━━ Available Presets ━━━\n");
    for (name, constraints) in all_presets() {
        println!("{}", name);
        for (lo, hi, cname) in &constraints {
            println!("  [{:>10.2}, {:>10.2}]  {}", lo, hi, cname);
        }
        println!();
    }
}

fn get_preset_constraints(name: &str) -> Vec<(f64, f64, &'static str)> {
    all_presets()
        .iter()
        .find(|(n, _)| *n == name)
        .map(|(_, c)| c.clone())
        .unwrap_or_default()
}

fn chrono_now() -> String {
    // Simple ISO 8601 without depending on chrono
    let output = std::process::Command::new("date")
        .args(["-u", "+%Y-%m-%dT%H:%M:%SZ"])
        .output();
    match output {
        Ok(o) => String::from_utf8_lossy(&o.stdout).trim().to_string(),
        Err(_) => "unknown".into(),
    }
}
