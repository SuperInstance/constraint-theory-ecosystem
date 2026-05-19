;; FLUX Constraint Engine — Fennel (2016, Lisp→Lua)
;; Pure INT8 saturated constraint checking. Zero dependencies.
;;
;; The insight: Fennel compiles to Lua. Lua runs EVERYWHERE —
;; game engines (LÖVE, Roblox), Redis, Nginx, Neovim, WoW.
;; Constraint checking as a Fennel library means constraints in
;; your game loop, your web server, your editor, your database.
;; Lisp macros = constraint DSL at compile time.
;;
;; "Compiles to Lua. Lua runs everywhere. Constraints run everywhere.
;;  Lisp macros make the GUARD DSL a compile-time construct."

;; ══ Constants ══════════════════════════════════════════════════════

(local INT8-MIN -127)
(local INT8-MAX 127)
(local MAX-CONSTRAINTS 8)

;; ══ Severity ══════════════════════════════════════════════════════

(local severity-names {:pass "PASS" :caution "CAUTION" :warning "WARNING" :critical "CRITICAL"})

(fn classify-severity [vc n]
  "Classify violation count into severity level."
  (if (= vc 0) :pass
      (and (> n 0) (<= vc (// n 4))) :caution
      (and (> n 0) (<= vc (// n 2))) :warning
      :critical))

;; ══ Saturate ══════════════════════════════════════════════════════

(fn saturate [val]
  "Clamp to saturated INT8 [-127, 127]"
  (math.max INT8-MIN (math.min INT8-MAX val)))

;; ══ Constraint ════════════════════════════════════════════════════

(fn make-constraint [lo hi name]
  "Create a constraint table with saturated bounds."
  {:lo (saturate lo) :hi (saturate hi) :name (or name "")})

;; ══ FluxResult ═══════════════════════════════════════════════════

(fn make-result []
  "Create an empty result table."
  {:error-mask 0 :severity :pass :violated-lo 0 :violated-hi 0
   :violated-count 0 :passed true})

;; ══ Core check ═══════════════════════════════════════════════════

(fn check [constraints raw-val]
  "Check a value against a list of constraints."
  (let [val (saturate raw-val)
        n (length constraints)
        result (make-result)]
    (each [i c (ipairs constraints)]
      (let [lo-fail (< val c.lo)
            hi-fail (> val c.hi)
            any-fail (or lo-fail hi-fail)
            bit (bit.lshift 1 (- i 1))]
        (when any-fail
          (set result.error-mask (bit.bor result.error-mask bit))
          (set result.violated-count (+ result.violated-count 1))
          (set result.passed false))
        (when lo-fail
          (set result.violated-lo (bit.bor result.violated-lo bit)))
        (when hi-fail
          (set result.violated-hi (bit.bor result.violated-hi bit)))))
    (set result.severity (classify-severity result.violated-count n))
    result))

;; ══ Batch check ══════════════════════════════════════════════════

(fn check-batch [constraints values]
  "Check multiple values against constraints."
  (icollect [_ v (ipairs values)] (check constraints v)))

;; ══ Macro: GUARD constraint DSL ═══════════════════════════════════
;; Lisp macros make GUARD syntax native at COMPILE TIME

(macro guard [name relation val1 val2]
  "GUARD DSL macro — compiles to constraint tables at macro expansion time."
  (if (= relation :in)
      `(make-constraint ,val1 ,val2 ,(tostring name))
      (= relation :>)
      `(make-constraint ,val2 INT8-MAX ,(tostring name))
      (= relation :<)
      `(make-constraint INT8-MIN ,val2 ,(tostring name))
      `(error "Unknown GUARD relation")))

;; ══ Industry Presets ══════════════════════════════════════════════

(local aviation
  [(make-constraint -55 70 "cabin_temp_C")
   (make-constraint 75 101 "cabin_pressure_kPa")
   (make-constraint 0 100 "fuel_flow_pct")
   (make-constraint 60 100 "hydraulic_pct")])

(local automotive
  [(make-constraint -40 60 "battery_temp_C")
   (make-constraint 0 100 "soc_pct")
   (make-constraint 0 100 "charge_rate_pct")
   (make-constraint 20 80 "cabin_temp_C")])

(local nuclear
  [(make-constraint 0 110 "neutron_flux_pct")
   (make-constraint 0 65 "core_temp_C_x10")
   (make-constraint 72 100 "pressurizer_pct")
   (make-constraint 0 100 "coolant_flow_pct")])

(local medical
  [(make-constraint 36 38 "body_temp_C")
   (make-constraint 60 100 "heart_rate_bpm")
   (make-constraint 95 100 "spo2_pct")
   (make-constraint 80 120 "bp_systolic_mmHg")])

(local maritime
  [(make-constraint -2 35 "sea_temp_C")
   (make-constraint 50 100 "hull_integrity_pct")
   (make-constraint 0 50 "wave_height_m")
   (make-constraint 0 80 "wind_speed_kn")])

(local energy
  [(make-constraint 49 51 "grid_freq_Hz_x10")
   (make-constraint 95 105 "voltage_pct")
   (make-constraint 0 80 "transformer_temp_C")
   (make-constraint 0 100 "line_load_pct")])

(local railway
  [(make-constraint 0 100 "speed_pct")
   (make-constraint 0 100 "brake_pressure_pct")
   (make-constraint 0 1 "door_interlock")
   (make-constraint 0 80 "track_temp_C")])

(local robotics
  [(make-constraint -100 100 "joint_torque_pct")
   (make-constraint 0 100 "speed_pct")
   (make-constraint 0 100 "force_pct")
   (make-constraint -127 127 "position_mm")])

(local space
  [(make-constraint -40 50 "temp_C")
   (make-constraint 0 100 "solar_panel_pct")
   (make-constraint 0 100 "propellant_pct")
   (make-constraint 0 100 "battery_pct")])

(local underwater
  [(make-constraint 0 100 "depth_pct")
   (make-constraint 0 100 "battery_pct")
   (make-constraint -5 35 "water_temp_C")
   (make-constraint 0 100 "thruster_pct")])

;; ══ Preset lookup ═════════════════════════════════════════════════

(local presets
  {:aviation aviation :automotive automotive :nuclear nuclear
   :medical medical :maritime maritime :energy energy
   :railway railway :robotics robotics :space space :underwater underwater})

(fn from-preset [name]
  "Load an industry preset by name."
  (or (. presets name)
      (error (.. "Unknown preset: " name))))

;; ══ Main ══════════════════════════════════════════════════════════

(print "═══ FLUX Constraint Engine — Fennel (Lisp→Lua) ═══")
(print "")

(let [r1 (check aviation 60)]
  (print (.. "  Aviation val=60:  " (. severity-names r1.severity)
             " mask=0x" (string.format "%02X" r1.error-mask)
             " passed=" (tostring r1.passed))))

(let [r2 (check aviation 25)]
  (print (.. "  Aviation val=25:  " (. severity-names r2.severity)
             " passed=" (tostring r2.passed))))

(let [r3 (check nuclear 127)]
  (print (.. "  Nuclear val=127:  " (. severity-names r3.severity)
             " mask=0x" (string.format "%02X" r3.error-mask))))

;; Using the GUARD macro (compile-time DSL!)
(let [custom [(guard battery_temp in 15 55)
              (guard charge_rate in 0 100)]]
  (print "")
  (print "  GUARD macro constraints:")
  (each [_ c (ipairs custom)]
    (print (.. "    " c.name ": [" c.lo ", " c.hi "]")))
  (let [r (check custom 60)]
    (print (.. "  Custom val=60: " (. severity-names r.severity)
               " passed=" (tostring r.passed)))))

(print "")
(print "Fennel compiles to Lua. Lua runs everywhere:")
(print "  Game engines (LÖVE, Roblox), Redis, Nginx, Neovim, WoW")
(print "Constraints everywhere, because Lua is everywhere.")

;; Fennel teaches us that Lisp macros make DSLs COMPILE-TIME constructs.
;; The GUARD macro expands at compile time — no runtime parsing needed.
;; Combined with Lua's ubiquity, constraint checking becomes available
;; in every system that already runs Lua. No new runtime required.
;; The cost of adoption is zero because the infrastructure already exists.

{:check check :check-batch check-batch :saturate saturate
 :make-constraint make-constraint :from-preset from-preset
 :guard guard
 :aviation aviation :automotive automotive :nuclear nuclear
 :medical medical :maritime maritime :energy energy
 :railway railway :robotics robotics :space space :underwater underwater}
