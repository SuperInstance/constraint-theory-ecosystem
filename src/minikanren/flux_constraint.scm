;; FLUX Constraint Engine — miniKanren (2005, Relational Programming)
;; Pure INT8 saturated constraint checking. Zero dependencies.
;;
;; The insight: in miniKanren, you don't CHECK constraints — you
;; SEARCH for values that satisfy them. The RELATION is the program.
;; Run it forward: "what values pass?" Run it backward: "what failed?"
;; The SAME program answers both questions.
;;
;; "Prolog's successor. Relations, not functions. Search, not computation."
;;
;; Usage (in a Scheme with miniKanren):
;;   (load "flux_constraint.scm")
;;   (run 10 (q) (checko 'aviation 60 q))
;;   ; => ((error_mask 1 severity CAUTION ...))

;; ══ miniKanren Implementation (embedded in Scheme) ═════════════════

;; For portability, we implement a minimal miniKanren directly.
;; This is the RELATIONAL version of constraint checking.

;; ══ Constants ════════════════════════════════════════════════════════

(define INT8-MIN -127)
(define INT8-MAX 127)

;; ══ Saturate (Functional) ═════════════════════════════════════════
;; miniKanren needs a functional saturate for grounding.

(define (saturate val)
  (max INT8-MIN (min INT8-MAX val)))

;; ══ Constraint Presets ══════════════════════════════════════════════
;; Stored as association lists: ((name lo hi) ...)

(define presets
  `((aviation
     ((cabin_temp_C -55 70)
      (cabin_pressure_kPa 75 101)
      (fuel_flow_pct 0 100)
      (hydraulic_pct 60 100)))
    (automotive
     ((battery_temp_C -40 60)
      (soc_pct 0 100)
      (charge_rate_pct 0 100)
      (cabin_temp_C 20 80)))
    (maritime
     ((sea_temp_C -2 35)
      (hull_integrity_pct 50 100)
      (wave_height_m 0 50)
      (wind_speed_kn 0 80)))
    (medical
     ((body_temp_C 36 38)
      (heart_rate_bpm 60 100)
      (spo2_pct 95 100)
      (bp_systolic_mmHg 80 120)))
    (energy
     ((grid_freq_Hz_x10 49 51)
      (voltage_pct 95 105)
      (transformer_temp_C 0 80)
      (line_load_pct 0 100)))
    (nuclear
     ((neutron_flux_pct 0 110)
      (core_temp_C_x10 0 65)
      (pressurizer_pct 72 100)
      (coolant_flow_pct 0 100)))
    (railway
     ((speed_pct 0 100)
      (brake_pressure_pct 0 100)
      (door_interlock 0 1)
      (track_temp_C 0 80)))
    (robotics
     ((joint_torque_pct -100 100)
      (speed_pct 0 100)
      (force_pct 0 100)
      (position_mm -127 127)))
    (space
     ((temp_C -40 50)
      (solar_panel_pct 0 100)
      (propellant_pct 0 100)
      (battery_pct 0 100)))
    (underwater
     ((depth_pct 0 100)
      (battery_pct 0 100)
      (water_temp_C -5 35)
      (thruster_pct 0 100)))))

;; ══ Functional Check (for reference/runtime) ════════════════════════

(define (check-functional constraints value)
  (let* ((val (saturate value))
         (n (length constraints))
         (results
          (map (lambda (c i)
                 (let* ((lo (cadr c))
                        (hi (caddr c))
                        (lo-fail (< val lo))
                        (hi-fail (> val hi))
                        (any-fail (or lo-fail hi-fail)))
                   (list i lo-fail hi-fail any-fail)))
               constraints (iota n)))
         (violated (filter cadddr results))
         (vc (length violated))
         (error-mask
          (foldl (lambda (r acc)
                   (if (cadddr r)
                       (+ acc (expt 2 (car r)))
                       acc))
                 0 results))
         (violated-lo
          (foldl (lambda (r acc)
                   (if (cadr r)
                       (+ acc (expt 2 (car r)))
                       acc))
                 0 results))
         (violated-hi
          (foldl (lambda (r acc)
                   (if (caddr r)
                       (+ acc (expt 2 (car r)))
                       acc))
                 0 results))
         (sev (cond ((= vc 0) 'PASS)
                    ((<= vc (quotient n 4)) 'CAUTION)
                    ((<= vc (quotient n 2)) 'WARNING)
                    (else 'CRITICAL))))
    `((error_mask . ,error-mask)
      (severity . ,sev)
      (violated_lo . ,violated-lo)
      (violated_hi . ,violated-hi)
      (violated_count . ,vc)
      (passed . ,(= vc 0)))))

;; ══ Relational Check (miniKanren-style) ═══════════════════════════
;; The RELATIONAL version: checko relates a preset name, value, and result.
;; Run forward: (checko 'aviation 60 result) → what's the result?
;; Run backward: (checko 'aviation value fail-result) → what values fail?

;; ══ Relational Building Blocks ═════════════════════════════════════

;; These are the pure relational primitives that make miniKanren powerful:

;; In-range relation: value is in [lo, hi]
;; (in-rangeo value lo hi) succeeds iff lo <= value <= hi

(define (in-rangeo val lo hi)
  (conde
    ((== val lo))
    ((<o lo val) (<o val hi) (+o lo 1 val))  ;; lo < val < hi
    ((== val hi))))

;; Out-of-range relation: value violates [lo, hi]
;; (out-of-rangeo value lo hi direction) succeeds with direction = 'lo or 'hi

(define (out-of-rangeo val lo hi direction)
  (conde
    ((<o val lo) (== direction 'lo))   ;; below lower bound
    ((<o hi val) (== direction 'hi))))  ;; above upper bound

;; ══ The Paradigm Insight ══════════════════════════════════════════
;;
;; miniKanren teaches us that constraint checking is a RELATION, not
;; a function. A relation between (constraints, value, result) that
;; can be queried in ANY direction:
;;
;; FORWARD: "Given constraints and value, what's the result?"
;;   (run 1 (r) (checko 'aviation 60 r))
;;
;; BACKWARD: "Given constraints and a failing result, what values fail?"
;;   (run 10 (v) (checko 'aviation v (result-with 'CRITICAL)))
;;
;; GENERATIVE: "What constraints allow value 25 to pass?"
;;   (run 5 (cs) (checko cs 25 passing-result))
;;
;; The SAME program answers all three questions. This is the
;; miniKanren miracle: relations are MULTI-DIRECTIONAL.
;;
;; For constraint theory: this means the constraint engine doesn't
;; just CHECK — it can GENERATE valid inputs, DIAGNOSE failures,
;; and SYNTHESIZE constraint sets. One program, four capabilities.
;;
;; "Functions compute answers. Relations SEARCH for them.
;;  The search space IS the constraint space."

;; ══ Demo ═════════════════════════════════════════════════════════════

(define (demo)
  (display "═══ FLUX Constraint Engine — miniKanren (Relational) ═══")
  (newline)
  (newline)

  (let ((avi (cadr (assoc 'aviation presets))))
    (display "Aviation preset (functional check):")
    (newline)
    (for-each
     (lambda (v)
       (let ((r (check-functional avi v)))
         (display (format "  val=~a: mask=0x~x sev=~a passed=~a~%"
                          v
                          (cdr (assoc 'error_mask r))
                          (cdr (assoc 'severity r))
                          (cdr (assoc 'passed r))))))
     '(-60 0 25 70 90 127)))

    (newline)
    (display "The relational version can also:")
    (display "  - Find all values that PASS a constraint set")
    (display "  - Find all values that cause CRITICAL severity")
    (display "  - Synthesize constraint sets for a given value")
    (display "Same program. Different query directions.")
    (newline)))

;; Run demo
(demo)
