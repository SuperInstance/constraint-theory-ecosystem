# FLUX Constraint Engine — R
# Pure INT8 saturated constraint checking. Zero dependencies.

saturate <- function(val) max(-127L, min(127L, as.integer(val)))

check <- function(constraints, value) {
  val <- saturate(value)
  error_mask <- 0L
  violated_lo <- 0L
  violated_hi <- 0L
  violated_count <- 0L

  for (i in seq_along(constraints)) {
    c <- constraints[[i]]
    lo <- saturate(c$lo)
    hi <- saturate(c$hi)
    lo_fail <- val < lo
    hi_fail <- val > hi
    if (lo_fail || hi_fail) {
      error_mask <- bitwOr(error_mask, bitwShiftL(1L, i - 1L))
      violated_count <- violated_count + 1L
    }
    if (lo_fail) violated_lo <- bitwOr(violated_lo, bitwShiftL(1L, i - 1L))
    if (hi_fail) violated_hi <- bitwOr(violated_hi, bitwShiftL(1L, i - 1L))
  }

  nc <- length(constraints)
  severity <- if (violated_count == 0) 0L
              else if (violated_count <= nc %/% 4) 1L
              else if (violated_count <= nc %/% 2) 2L
              else 3L

  list(
    error_mask = error_mask,
    severity = severity,
    violated_lo = violated_lo,
    violated_hi = violated_hi,
    violated_count = violated_count,
    passed = violated_count == 0
  )
}

check_batch <- function(constraints, values) {
  results <- lapply(values, function(v) check(constraints, v))
  stats <- list(
    pass = sum(sapply(results, function(r) r$severity == 0L)),
    caution = sum(sapply(results, function(r) r$severity == 1L)),
    warning = sum(sapply(results, function(r) r$severity == 2L)),
    critical = sum(sapply(results, function(r) r$severity == 3L))
  )
  list(results = results, stats = stats)
}

benchmark_flux <- function(constraints, iterations = 1000000L) {
  t0 <- proc.time()
  for (i in seq_len(iterations)) {
    check(constraints, (i %% 254L) - 127L)
  }
  elapsed <- (proc.time() - t0)[["elapsed"]]
  rate <- iterations * length(constraints) / elapsed
  list(rate = rate, ms = elapsed * 1000)
}

PRESETS <- list(
  aviation = list(
    list(lo = -55, hi = 70, name = "cabin_temp_C"),
    list(lo = 75, hi = 101, name = "cabin_pressure_kPa"),
    list(lo = 0, hi = 100, name = "fuel_flow_pct"),
    list(lo = 60, hi = 100, name = "hydraulic_pct")
  ),
  medical = list(
    list(lo = 36, hi = 38, name = "body_temp_C"),
    list(lo = 60, hi = 100, name = "heart_rate_bpm"),
    list(lo = 95, hi = 100, name = "spo2_pct"),
    list(lo = 80, hi = 120, name = "bp_systolic_mmHg")
  ),
  maritime = list(
    list(lo = -2, hi = 35, name = "sea_temp_C"),
    list(lo = 50, hi = 100, name = "hull_integrity_pct"),
    list(lo = 0, hi = 50, name = "wave_height_m"),
    list(lo = 0, hi = 80, name = "wind_speed_kn")
  ),
  automotive = list(
    list(lo = -40, hi = 60, name = "battery_temp_C"),
    list(lo = 0, hi = 100, name = "soc_pct"),
    list(lo = 0, hi = 100, name = "charge_rate_pct"),
    list(lo = 20, hi = 80, name = "cabin_temp_C")
  ),
  energy = list(
    list(lo = 49, hi = 51, name = "grid_freq_Hz_x10"),
    list(lo = 95, hi = 105, name = "voltage_pct"),
    list(lo = 0, hi = 80, name = "transformer_temp_C"),
    list(lo = 0, hi = 100, name = "line_load_pct")
  )
)

from_preset <- function(name) {
  if (is.null(PRESETS[[name]])) stop(paste("Unknown preset:", name))
  PRESETS[[name]]
}

# Self-test
if (sys.nframe() == 0L) {
  cat("FLUX Constraint Engine — R\n")
  cat("==========================\n")

  stopifnot(saturate(-128L) == -127L, saturate(128L) == 127L)
  cat("  saturate: OK\n")

  cs <- list(list(lo = 0, hi = 100))
  stopifnot(check(cs, 50L)$passed)
  stopifnot(!check(cs, 150L)$passed)
  cat("  check: OK\n")

  cs4 <- rep(list(list(lo = 0, hi = 10)), 4)
  r <- check(cs4, 50L)
  stopifnot(r$severity == 3L, r$violated_count == 4L)
  cat("  severity: OK\n")

  cs3 <- from_preset("aviation")
  stopifnot(length(cs3) == 4)
  cat("  presets: OK\n")

  b <- benchmark_flux(cs3)
  cat(sprintf("  Benchmark: %.1fM checks/sec (%.1fms)\n", b$rate / 1e6, b$ms))
  cat("  All tests pass\n")
}
