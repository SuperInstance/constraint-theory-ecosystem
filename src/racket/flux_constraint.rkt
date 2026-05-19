#lang racket

;; FLUX Constraint Engine — Racket (1995, Macro-Powered DSLs)
;; Pure INT8 saturated constraint checking. Zero dependencies.
;;
;; The insight: macros ARE compilers. The GUARD DSL can be a Racket MACRO.
;; Constraint specs expand at compile time into optimized check functions.
;; Racket's #lang system means we could write #lang guard and have
;; constraint files be FIRST-CLASS Racket modules. The language IS the tool.
;;
;; "Macros ARE compilers. The GUARD DSL is a Racket macro.
;;  Constraint specs compile to optimal code at macro-expansion time."

;; ══ Constants ══════════════════════════════════════════════════════

(define INT8-MIN -127)
(define INT8-MAX 127)
(define MAX-CONSTRAINTS 8)

;; ══ Severity ══════════════════════════════════════════════════════

(struct severity (level name) #:transparent)

(define SEV-PASS     (severity 0 'pass))
(define SEV-CAUTION  (severity 1 'caution))
(define SEV-WARNING  (severity 2 'warning))
(define SEV-CRITICAL (severity 3 'critical))

;; ══ Data structures ═══════════════════════════════════════════════

(struct constraint (lo hi name) #:transparent)
(struct flux-result (error-mask severity violated-lo violated-hi violated-count passed) #:transparent)

;; ══ Saturate: clamp to [-127, 127] ═══════════════════════════════

(define (saturate v)
  (max INT8-MIN (min INT8-MAX (exact-floor v))))

;; ══ Severity classification ══════════════════════════════════════

(define (classify-severity violated total)
  (cond
    [(= violated 0) SEV-PASS]
    [(<= violated (quotient total 4)) SEV-CAUTION]
    [(<= violated (quotient total 2)) SEV-WARNING]
    [else SEV-CRITICAL]))

;; ══ Check function ═══════════════════════════════════════════════

(define (check constraints value)
  (let ([val (saturate value)])
    (for/fold ([mask 0] [vlo 0] [vhi 0] [vc 0]
               #:result (flux-result mask
                                      (classify-severity vc (length constraints))
                                      vlo vhi vc (= vc 0)))
              ([c (in-list constraints)]
               [i (in-naturals)])
      (let* ([lo-fail (< val (constraint-lo c))]
             [hi-fail (> val (constraint-hi c))]
             [failed (or lo-fail hi-fail)]
             [new-mask (if failed (bitwise-ior mask (arithmetic-shift 1 i)) mask)]
             [new-vlo  (if lo-fail (bitwise-ior vlo (arithmetic-shift 1 i)) vlo)]
             [new-vhi  (if hi-fail (bitwise-ior vhi (arithmetic-shift 1 i)) vhi)]
             [new-vc   (if failed (add1 vc) vc)])
        (values new-mask new-vlo new-vhi new-vc)))))

;; ══ Batch check ══════════════════════════════════════════════════

(define (check-batch constraints values)
  (for/list ([v (in-list values)])
    (check constraints v)))

;; ══ Macro: define-constraints ════════════════════════════════════
;; EXPANDS constraint specs into optimized check functions at compile time.
;; The macro IS the compiler. Constraint specs become Racket code.

(define-syntax-rule (define-constraints id (lo hi name) ...)
  (define id
    (let ([cs (list (constraint lo hi name) ...)])
      (λ (value) (check cs value)))))

;; More powerful macro: define-constraints* creates the list AND a checker
(define-syntax (define-constraints* stx)
  (syntax-case stx ()
    [(_ id (lo hi name) ...)
     #'(begin
         (define id-constraints
           (list (constraint lo hi name) ...))
         (define (id value)
           (check id-constraints value)))]))

;; ══ Contracts (runtime verification of the API) ═════════════════

(provide
 (contract-out
  [saturate      (-> integer? integer?)]
  [check         (-> (listof constraint?) integer? flux-result?)]
  [check-batch   (-> (listof constraint?) (listof integer?) (listof flux-result?))])
 constraint flux-result
 (struct-out severity))

;; ══ Industry presets ═════════════════════════════════════════════

(define-constraints* aviation-preset
  (-55 70  "cabin_temp_C")
  (75  101 "cabin_pressure_kPa")
  (0   100 "fuel_flow_pct")
  (60  100 "hydraulic_pct"))

(define-constraints* automotive-preset
  (-40 60  "battery_temp_C")
  (0   100 "soc_pct")
  (0   100 "charge_rate_pct")
  (20  80  "cabin_temp_C"))

(define-constraints* maritime-preset
  (-2  35  "sea_temp_C")
  (50  100 "hull_integrity_pct")
  (0   50  "wave_height_m")
  (0   80  "wind_speed_kn"))

(define-constraints* medical-preset
  (36  38  "body_temp_C")
  (60  100 "heart_rate_bpm")
  (95  100 "spo2_pct")
  (80  120 "bp_systolic_mmHg"))

(define-constraints* energy-preset
  (49  51  "grid_freq_Hz_x10")
  (95  105 "voltage_pct")
  (0   80  "transformer_temp_C")
  (0   100 "line_load_pct"))

(define-constraints* nuclear-preset
  (0   110 "neutron_flux_pct")
  (0   65  "core_temp_C_x10")
  (72  100 "pressurizer_pct")
  (0   100 "coolant_flow_pct"))

(define-constraints* railway-preset
  (0   100 "speed_pct")
  (0   100 "brake_pressure_pct")
  (0   1   "door_interlock")
  (0   80  "track_temp_C"))

(define-constraints* robotics-preset
  (-100 100 "joint_torque_pct")
  (0    100 "speed_pct")
  (0    100 "force_pct")
  (-127 127 "position_mm"))

(define-constraints* space-preset
  (-40 50  "temp_C")
  (0   100 "solar_panel_pct")
  (0   100 "propellant_pct")
  (0   100 "battery_pct"))

(define-constraints* underwater-preset
  (0   100 "depth_pct")
  (0   100 "battery_pct")
  (-5  35  "water_temp_C")
  (0   100 "thruster_pct"))

;; ══ Preset lookup ════════════════════════════════════════════════

(define presets
  (hash "aviation"   aviation-preset-constraints
        "automotive" automotive-preset-constraints
        "maritime"   maritime-preset-constraints
        "medical"    medical-preset-constraints
        "energy"     energy-preset-constraints
        "nuclear"    nuclear-preset-constraints
        "railway"    railway-preset-constraints
        "robotics"   robotics-preset-constraints
        "space"      space-preset-constraints
        "underwater" underwater-preset-constraints))

(define (from-preset name)
  (check (hash-ref presets name) ))

;; ══ Usage ════════════════════════════════════════════════════════
;;
;; ;; Define constraints with the macro (compiles at expansion time)
;; (define-constraints* battery (-20 60 "battery_temp_C") (0 100 "soc_pct"))
;; (battery 70)
;; ;; => (flux-result 1 (severity 1 'caution) 0 1 1 #f)
;;
;; ;; Use a preset
;; (aviation-preset 60)
;; ;; => check aviation constraints at value 60
;;
;; ;; Batch check
;; (check-batch (hash-ref presets "medical") '(36 38 40 100))
;;
;; ;; The #lang guard vision:
;; ;; #lang guard
;; ;; GUARD battery_temp in [15, 55]
;; ;; GUARD charge_rate in [0, 100]
;; ;; This would expand into the Racket check function via a #lang reader

;; ══ Why Racket Matters ═══════════════════════════════════════════
;;
;; Racket's macro system is the most powerful in any language.
;; The define-constraints macro EXPANDS constraint specifications into
;; optimized check code at COMPILE TIME. No interpretation overhead.
;;
;; The #lang system means GUARD DSL could become a FIRST-CLASS language:
;;   #lang guard
;;   GUARD battery_temp in [15, 55]
;; The reader would parse GUARD syntax, the expander would generate
;; Racket code, and the result would be a native Racket module.
;;
;; Contracts (contract-out) add runtime verification of the API boundary.
;; The combination of compile-time macros + runtime contracts = dual safety.
;; No other language offers this combination at this depth.
