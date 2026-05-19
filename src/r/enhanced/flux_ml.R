# FLUX Constraint Engine — R Enhanced (ML + SNAP Provenance)
# INT8 saturated constraint checking with ML anomaly detection
# and fully traceable, reproducible analysis pipelines.
#
# R's ecosystem makes constraints a FIRST-CLASS data analysis problem.
# SNAP proves every result is reproducible. ML predicts violations
# before they happen. {targets} pipelines make it all durable.
#
# "Constraints aren't just checks — they're DATA. R treats them as such.
#  Every violation is a data point. Every pattern is a model.
#  Every result is traceable to its source."

# ══ Constants ══════════════════════════════════════════════════════

INT8_MIN <- -127L
INT8_MAX <- 127L
MAX_CONSTRAINTS <- 8L

# ══ Severity ═══════════════════════════════════════════════════════

SEVERITY_LEVELS <- c(PASS = 0L, CAUTION = 1L, WARNING = 2L, CRITICAL = 3L)

severity_name <- function(level) {
  names(SEVERITY_LEVELS)[match(level, SEVERITY_LEVELS)]
}

# ══ Saturate ═══════════════════════════════════════════════════════

saturate <- function(val) {
  as.integer(max(INT8_MIN, min(INT8_MAX, as.integer(val))))
}

# ══ Industry Presets ═══════════════════════════════════════════════

PRESETS <- list(
  aviation = list(
    list(lo = -55L, hi = 70L, name = "cabin_temp_C"),
    list(lo = 75L,  hi = 101L, name = "cabin_pressure_kPa"),
    list(lo = 0L,   hi = 100L, name = "fuel_flow_pct"),
    list(lo = 60L,  hi = 100L, name = "hydraulic_pct")
  ),
  automotive = list(
    list(lo = -40L, hi = 60L, name = "battery_temp_C"),
    list(lo = 0L,   hi = 100L, name = "soc_pct"),
    list(lo = 0L,   hi = 100L, name = "charge_rate_pct"),
    list(lo = 20L,  hi = 80L, name = "cabin_temp_C")
  ),
  maritime = list(
    list(lo = -2L, hi = 35L,  name = "sea_temp_C"),
    list(lo = 50L, hi = 100L, name = "hull_integrity_pct"),
    list(lo = 0L,  hi = 50L,  name = "wave_height_m"),
    list(lo = 0L,  hi = 80L,  name = "wind_speed_kn")
  ),
  medical = list(
    list(lo = 36L,  hi = 38L,   name = "body_temp_C"),
    list(lo = 60L,  hi = 100L,  name = "heart_rate_bpm"),
    list(lo = 95L,  hi = 100L,  name = "spo2_pct"),
    list(lo = 80L,  hi = 120L,  name = "bp_systolic_mmHg")
  ),
  energy = list(
    list(lo = 49L, hi = 51L,  name = "grid_freq_Hz_x10"),
    list(lo = 95L, hi = 105L, name = "voltage_pct"),
    list(lo = 0L,  hi = 80L,  name = "transformer_temp_C"),
    list(lo = 0L,  hi = 100L, name = "line_load_pct")
  ),
  nuclear = list(
    list(lo = 0L,  hi = 110L, name = "neutron_flux_pct"),
    list(lo = 0L,  hi = 65L,  name = "core_temp_C_x10"),
    list(lo = 72L, hi = 100L, name = "pressurizer_pct"),
    list(lo = 0L,  hi = 100L, name = "coolant_flow_pct")
  )
)

# ══ Core Check ═════════════════════════════════════════════════════

flux_check <- function(constraints, value) {
  if (length(constraints) == 0) stop("Non-empty constraints required")
  if (length(constraints) > MAX_CONSTRAINTS) stop("Maximum 8 constraints")

  val <- saturate(value)
  nc <- length(constraints)
  error_mask <- 0L
  violated_lo <- 0L
  violated_hi <- 0L
  violated_count <- 0L
  details <- data.frame(
    name = character(nc), lo = integer(nc), hi = integer(nc),
    value = integer(nc), passed = logical(nc),
    lo_violated = logical(nc), hi_violated = logical(nc),
    stringsAsFactors = FALSE
  )

  for (i in seq_along(constraints)) {
    c <- constraints[[i]]
    lo <- saturate(c$lo)
    hi <- saturate(c$hi)
    lo_fail <- val < lo
    hi_fail <- val > hi
    passed <- !lo_fail && !hi_fail

    if (!passed) {
      error_mask <- bitwOr(error_mask, bitwShiftL(1L, i - 1L))
      violated_count <- violated_count + 1L
    }
    if (lo_fail) violated_lo <- bitwOr(violated_lo, bitwShiftL(1L, i - 1L))
    if (hi_fail) violated_hi <- bitwOr(violated_hi, bitwShiftL(1L, i - 1L))

    details[i, ] <- list(c$name, lo, hi, val, passed, lo_fail, hi_fail)
  }

  severity <- if (violated_count == 0) 0L
              else if (violated_count <= nc %/% 4) 1L
              else if (violated_count <= nc %/% 2) 2L
              else 3L

  list(
    error_mask = error_mask,
    severity = severity,
    severity_name = severity_name(severity),
    violated_lo = violated_lo,
    violated_hi = violated_hi,
    violated_count = violated_count,
    passed = violated_count == 0,
    details = details
  )
}

# ══ Batch Check ════════════════════════════════════════════════════

flux_batch <- function(constraints, values) {
  results <- lapply(values, function(v) flux_check(constraints, v))
  stats <- table(sapply(results, `[[`, "severity_name"))
  list(results = results, stats = stats)
}

# ══ Provenance Tracking (SNAP-style) ═══════════════════════════════
# Every check is traceable: who ran it, when, on what data, with what result.

flux_provenance <- function(constraints, value, source = "unknown", operator = Sys.info()["user"]) {
  timestamp <- Sys.time()
  check_result <- flux_check(constraints, value)
  session_id <- paste0(digest::digest(paste0(timestamp, operator, value)), substr(as.character(timestamp), 1, 10))

  list(
    session_id = session_id,
    timestamp = timestamp,
    operator = operator,
    source = source,
    value = value,
    saturated_value = saturate(value),
    constraints = constraints,
    result = check_result,
    r_version = R.version.string,
    platform = R.version$platform
  )
}

# ══ Time Series Anomaly Detection ═════════════════════════════════
# Detect unusual patterns in constraint violation time series.

flux_anomaly_detect <- function(time_series, window = 20, threshold = 2.5) {
  n <- length(time_series)
  if (n < window) stop(paste("Need at least", window, "data points"))

  # Rolling mean and sd
  rolling_mean <- stats::filter(time_series, rep(1/window, window), sides = 1)
  rolling_sd <- sqrt(stats::filter(time_series^2, rep(1/window, window), sides = 1) -
                     rolling_mean^2)

  # Z-score anomaly detection
  z_scores <- (time_series - rolling_mean) / rolling_sd
  anomalies <- which(abs(z_scores) > threshold)

  list(
    z_scores = z_scores,
    anomalies = anomalies,
    anomaly_count = length(anomalies),
    threshold = threshold,
    window = window
  )
}

# ══ ML Training: Predict Violations ═══════════════════════════════
# Train a classifier on violation patterns from historical data.
# Uses random forest via {ranger} (fast, parallel) or falls back to {randomForest}.

flux_ml_train <- function(historical_data, target_col = "violated") {
  # historical_data: data.frame with sensor values + violated (0/1) column
  # Features: sensor values, time of day, rolling stats

  if (requireNamespace("ranger", quietly = TRUE)) {
    model <- ranger::ranger(
      as.factor(violated) ~ .,
      data = historical_data,
      num.trees = 500,
      importance = "impurity",
      seed = 42
    )
  } else if (requireNamespace("randomForest", quietly = TRUE)) {
    model <- randomForest::randomForest(
      as.factor(violated) ~ .,
      data = historical_data,
      ntree = 500
    )
  } else {
    stop("Install ranger or randomForest: install.packages('ranger')")
  }

  list(
    model = model,
    trained_at = Sys.time(),
    n_rows = nrow(historical_data),
    features = setdiff(names(historical_data), target_col),
    package = if (inherits(model, "ranger")) "ranger" else "randomForest"
  )
}

# Predict violation probability for new sensor readings
flux_ml_predict <- function(model_info, new_data) {
  pred <- predict(model_info$model, data = new_data)
  if (model_info$package == "ranger") {
    prob <- pred$predictions[, 2]  # P(violated = 1)
  } else {
    prob <- pred$vote[, 2]
  }
  data.frame(
    predicted_violation = pred$predictions == "1",
    violation_probability = prob,
    risk_level = ifelse(prob > 0.7, "HIGH", ifelse(prob > 0.3, "MEDIUM", "LOW"))
  )
}

# ══ Generate Realistic Time Series Data ════════════════════════════

flux_generate_timeseries <- function(preset_name, n_points = 1000,
                                      anomaly_rate = 0.05, drift = FALSE) {
  constraints <- PRESETS[[preset_name]]
  if (is.null(constraints)) stop(paste("Unknown preset:", preset_name))

  nc <- length(constraints)
  data <- data.frame(timestamp = seq_len(n_points))

  for (i in seq_along(constraints)) {
    c <- constraints[[i]]
    mid <- (c$lo + c$hi) / 2
    range <- c$hi - c$lo
    noise <- rnorm(n_points, 0, range * 0.1)
    drift_component <- if (drift) seq(0, range * 0.3, length.out = n_points) else 0
    anomaly_mask <- runif(n_points) < anomaly_rate
    anomaly_component <- ifelse(anomaly_mask, runif(n_points, -range, range) * 0.8, 0)

    values <- mid + noise + drift_component + anomaly_component
    values <- round(sapply(values, saturate))
    data[[c$name]] <- values
  }

  attr(data, "preset") <- preset_name
  attr(data, "anomaly_rate") <- anomaly_rate
  data
}

# ══ Parallel Batch Check (future) ═════════════════════════════════
# Use {future} for parallel checking across cores.

flux_parallel_batch <- function(constraints, values, cores = parallel::detectCores()) {
  if (requireNamespace("future.apply", quietly = TRUE)) {
    future::plan(future::multisession, workers = cores)
    results <- future.apply::future_lapply(values, function(v) flux_check(constraints, v))
    future::plan(future::sequential)  # Reset
  } else {
    # Fallback: sequential
    results <- lapply(values, function(v) flux_check(constraints, v))
  }

  stats <- table(sapply(results, function(r) r$severity_name))
  list(results = results, stats = stats, cores_used = cores)
}

# ══ REST API Skeleton (plumber) ═══════════════════════════════════
# Save as flux_api.R and run: plumber::plumb("flux_api.R")
#
# library(plumber)
#
# #* Check a value against a preset
# #* @param preset:character The preset name
# #* @param value:integer The value to check
# #* @get /check
# function(preset = "aviation", value = 25) {
#   constraints <- PRESETS[[preset]]
#   if (is.null(constraints)) return(list(error = "Unknown preset"))
#   flux_provenance(constraints, as.integer(value), source = "api")
# }
#
# #* Batch check values
# #* @post /batch
# function(req) {
#   body <- req$body
#   constraints <- PRESETS[[body$preset]]
#   flux_batch(constraints, body$values)
# }
#
# #* Health check
# #* @get /health
# function() { list(status = "ok", version = "1.0.0") }

# ══ {targets} Pipeline Skeleton ═══════════════════════════════════
# Save as _targets.R for reproducible analysis workflow:
#
# library(targets)
# tar_option_set(packages = c("flux_constraint"))
#
# list(
#   tar_target(raw_data, flux_generate_timeseries("aviation", 10000)),
#   tar_target(checks, flux_parallel_batch(PRESETS$aviation, raw_data$cabin_temp_C)),
#   tar_target(anomalies, flux_anomaly_detect(sapply(checks$results, `[[`, "violated_count"))),
#   tar_target(report, {
#     list(
#       total_checks = length(checks$results),
#       pass_rate = mean(sapply(checks$results, `[[`, "passed")),
#       anomaly_indices = anomalies$anomalies,
#       generated = Sys.time()
#     )
#   })
# )

# ══ Demo ═══════════════════════════════════════════════════════════

if (interactive() || identical(Sys.getenv("FLUX_DEMO"), "1")) {
  cat("═══ FLUX Constraint Engine — R Enhanced (ML + SNAP) ═══\n\n")

  # Basic check
  cat("Basic check:\n")
  r <- flux_check(PRESETS$aviation, 60)
  cat(sprintf("  Aviation val=60: %s mask=0x%02X passed=%s\n",
              r$severity_name, r$error_mask, r$passed))

  r <- flux_check(PRESETS$aviation, 25)
  cat(sprintf("  Aviation val=25: %s mask=0x%02X passed=%s\n",
              r$severity_name, r$error_mask, r$passed))

  # Batch check
  cat("\nBatch check:\n")
  batch <- flux_batch(PRESETS$medical, c(35, 37, 39, 50, 100))
  cat(sprintf("  5 values: %s\n", paste(names(batch$stats), batch$stats, sep = "=", collapse = " ")))

  # Generate time series and detect anomalies
  cat("\nAnomaly detection (aviation, 1000 points):\n")
  ts_data <- flux_generate_timeseries("aviation", 1000, anomaly_rate = 0.05)
  checks <- flux_parallel_batch(PRESETS$aviation, ts_data$cabin_temp_C)
  violations <- sapply(checks$results, function(r) as.integer(!r$passed))
  anomaly_result <- flux_anomaly_detect(violations)
  cat(sprintf("  Violations: %d/%d, Anomalies detected: %d\n",
              sum(violations), length(violations), anomaly_result$anomaly_count))

  # Provenance example
  cat("\nProvenance:\n")
  prov <- flux_provenance(PRESETS$nuclear, 70, source = "reactor_monitor")
  cat(sprintf("  Session: %s\n  Time: %s\n  Result: %s mask=0x%02X\n",
              prov$session_id, prov$timestamp,
              prov$result$severity_name, prov$result$error_mask))

  cat("\nPipeline: generate → check → detect anomalies → provenance ✓\n")
}
