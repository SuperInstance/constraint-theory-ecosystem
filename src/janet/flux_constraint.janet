# FLUX Constraint Engine — Janet (2019, Lisp/C Hybrid)
# Pure INT8 saturated constraint checking. Zero dependencies.
#
# The insight: Lisp's homoiconicity means constraints ARE data.
# Data IS code. A constraint spec is a Janet table that could have
# come from a config file, a PEG parser, or a REPL — it doesn't matter.
# Janet compiles to C, so the Lisp elegance runs at C speed.
# PEG parsing + C FFI = constraints as an embedded DSL.
#
# "Lisp's homoiconicity means constraints ARE data. Data IS code."

# ══ Constants ══════════════════════════════════════════════════════

(def INT8-MIN -127)
(def INT8-INT8-MAX 127)
(def MAX-CONSTRAINTS 8)

# ══ Saturate ══════════════════════════════════════════════════════

(defn saturate
  "Clamp value to saturated INT8 [-127, 127]"
  [val]
  (max INT8-MIN (min 127 val)))

# ══ Severity classification ══════════════════════════════════════

(defn classify-severity
  "Classify violation severity from count and total"
  [vc n]
  (cond
    (= vc 0) :pass
    (<= vc (int (/ n 4))) :caution
    (<= vc (int (/ n 2))) :warning
    :critical))

# ══ Core: check constraints against a value ══════════════════════

(defn flux-check
  "Check a value against a list of constraint tables.
   Each constraint: {:lo int :hi int :name string}
   Returns: {:error-mask :severity :violated-lo :violated-hi :violated-count :passed}"
  [constraints raw-val]
  (let [val (saturate raw-val)
        n (length constraints)]
    (var error-mask 0)
    (var violated-lo 0)
    (var violated-hi 0)
    (var violated-count 0)

    # Check each constraint, accumulate bit masks
    (loop [i :range [0 n]
           c :in constraints]
      (let [lo-fail (< val (c :lo))
            hi-fail (> val (c :hi))
            any-fail (or lo-fail hi-fail)
            bit (blshift 1 i)]
        (when any-fail
          (set error-mask (bor error-mask bit))
          (+= violated-count 1))
        (when lo-fail
          (set violated-lo (bor violated-lo bit)))
        (when hi-fail
          (set violated-hi (bor violated-hi bit)))))

    # Build result as immutable struct
    {:error-mask error-mask
     :severity (classify-severity violated-count n)
     :violated-lo violated-lo
     :violated-hi violated-hi
     :violated-count violated-count
     :passed (= violated-count 0)}))

# ══ Batch check ═══════════════════════════════════════════════════

(defn flux-check-batch
  "Check multiple values against constraints"
  [constraints values]
  (map (fn [v] (flux-check constraints v)) values))

# ══ Industry presets (Janet tables — data IS code) ════════════════

(def presets
  {:aviation
   [{:lo -55 :hi 70 :name "cabin_temp_C"}
    {:lo 75 :hi 101 :name "cabin_pressure_kPa"}
    {:lo 0 :hi 100 :name "fuel_flow_pct"}
    {:lo 60 :hi 100 :name "hydraulic_pct"}]

   :automotive
   [{:lo -40 :hi 60 :name "battery_temp_C"}
    {:lo 0 :hi 100 :name "soc_pct"}
    {:lo 0 :hi 100 :name "charge_rate_pct"}
    {:lo 20 :hi 80 :name "cabin_temp_C"}]

   :maritime
   [{:lo -2 :hi 35 :name "sea_temp_C"}
    {:lo 50 :hi 100 :name "hull_integrity_pct"}
    {:lo 0 :hi 50 :name "wave_height_m"}
    {:lo 0 :hi 80 :name "wind_speed_kn"}]

   :medical
   [{:lo 36 :hi 38 :name "body_temp_C"}
    {:lo 60 :hi 100 :name "heart_rate_bpm"}
    {:lo 95 :hi 100 :name "spo2_pct"}
    {:lo 80 :hi 120 :name "bp_systolic_mmHg"}]

   :energy
   [{:lo 49 :hi 51 :name "grid_freq_Hz_x10"}
    {:lo 95 :hi 105 :name "voltage_pct"}
    {:lo 0 :hi 80 :name "transformer_temp_C"}
    {:lo 0 :hi 100 :name "line_load_pct"}]

   :nuclear
   [{:lo 0 :hi 110 :name "neutron_flux_pct"}
    {:lo 0 :hi 65 :name "core_temp_C_x10"}
    {:lo 72 :hi 100 :name "pressurizer_pct"}
    {:lo 0 :hi 100 :name "coolant_flow_pct"}]

   :railway
   [{:lo 0 :hi 100 :name "speed_pct"}
    {:lo 0 :hi 100 :name "brake_pressure_pct"}
    {:lo 0 :hi 1 :name "door_interlock"}
    {:lo 0 :hi 80 :name "track_temp_C"}]

   :robotics
   [{:lo -100 :hi 100 :name "joint_torque_pct"}
    {:lo 0 :hi 100 :name "speed_pct"}
    {:lo 0 :hi 100 :name "force_pct"}
    {:lo -127 :hi 127 :name "position_mm"}]

   :space
   [{:lo -40 :hi 50 :name "temp_C"}
    {:lo 0 :hi 100 :name "solar_panel_pct"}
    {:lo 0 :hi 100 :name "propellant_pct"}
    {:lo 0 :hi 100 :name "battery_pct"}]

   :underwater
   [{:lo 0 :hi 100 :name "depth_pct"}
    {:lo 0 :hi 100 :name "battery_pct"}
    {:lo -5 :hi 35 :name "water_temp_C"}
    {:lo 0 :hi 100 :name "thruster_pct"}]})

(defn from-preset
  "Load a preset by keyword"
  [name]
  (if-let [p (presets name)]
    p
    (error (string "Unknown preset: " name))))

# ══ PEG Parser: GUARD DSL → Janet constraints ═══════════════════
# Janet's PEG module can parse GUARD DSL syntax into constraint tables.
# This is how Lisp's homoiconicity becomes a superpower:
# parse text → data → check. No intermediate objects needed.

(def guard-peg
  "PEG grammar for GUARD constraint syntax"
  ~{:constraint (* 'GUARD 's+ :name '(some (if-not (set " \t\n") 1)))
    :range (* 's* '[in' 's* '[ 's* :lo '- 's* :lo-val '(some (if-not (set " \t\n,]") 1))
             's* ', 's* :hi '- 's* :hi-val '(some (if-not (set " \t\n,]") 1)) 's* ']')})

# Sketch: parse GUARD text into constraint data
(defn parse-guard
  "Parse a GUARD DSL string into constraint tables (sketch)"
  [text]
  # In production: use peg/match with guard-peg
  # For now, return the principle: parse → data → check
  (printf "PEG parsing: %s" text)
  [])

# ══ Main ══════════════════════════════════════════════════════════

(defn main
  [& args]
  (print "═══ FLUX Constraint Engine — Janet (Lisp/C Hybrid) ═══")
  (print "")

  # Aviation example
  (let [cons (from-preset :aviation)]
    (printf "Aviation preset: %d constraints" (length cons))
    (each c cons
      (printf "  %s [%d, %d]" (c :name) (c :lo) (c :hi)))
    (print "")

    # Single checks
    (print "Examples:")
    (each val [-60 0 25 70 127]
      (let [r (flux-check cons val)]
        (printf "  val=%4d: %s mask=0x%02X passed=%s"
                val (r :severity) (r :error-mask) (r :passed))))
    (print "")

    # Batch
    (print "Batch [-60, 0, 25, 70, 127]:")
    (let [results (flux-check-batch cons [-60 0 25 70 127])]
      (each r results
        (printf "  %s mask=0x%02X" (r :severity) (r :error-mask))))))

# Lisp's homoiconicity means constraints ARE data. Data IS code.
# A Janet table from a config file IS the constraint spec.
# A PEG parse of GUARD DSL produces the same table.
# Janet compiles to C, so Lisp elegance runs at C speed.
