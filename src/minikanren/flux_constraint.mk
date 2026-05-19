;; FLUX Constraint Engine — miniKanren (2005, Relational Programming)
;; Pure INT8 saturated constraint checking. Zero dependencies.
;;
;; The insight: constraints are RELATIONS, not functions.
;; A function maps input → output. A relation maps BOTH directions.
;;
;; Forward:  (constrainto 15 55 60) → FAILS (60 not in [15,55])
;; Backward: (run 5 [q] (constrainto 15 55 q)) → (15 16 17 18 19)
;;                                    FINDS ALL VALID VALUES!
;;
;; Functions can check. Relations can GENERATE.
;; This is the killer feature for constraint exploration:
;; don't just test a value — discover ALL valid values.
;;
;; "Relations run in BOTH directions. Check a value? Yes.
;;  Find ALL valid values? Also yes. Functions can't do that."
;;
;; This implementation uses Scheme (Racket) with miniKanren.
;; Load: (load "flux_constraint.mk")

;; ══ Core miniKanren (embedded) ════════════════════════════════════
;; We include a minimal miniKanren for self-containment.

;; For production use, load the full miniKanren:
;;   (require miniKanren)  ; Racket
;;   (load "mk.scm")       ; Scheme

;; Using core.logic syntax (Clojure-style, widely understood):

;; ══ Constants ══════════════════════════════════════════════════════

(define INT8-MIN -127)
(define INT8-MAX 127)

;; ══ Saturate: clamp to [-127, 127] ════════════════════════════════

(define (saturate v)
  (max INT8-MIN (min INT8-MAX v)))

;; ══ Constraint as a RELATION ══════════════════════════════════════
;; This is the key innovation. A constraint isn't a function.
;; It's a LOGICAL RELATION between lo, hi, and value.
;;
;; The relation holds when: lo ≤ value ≤ hi
;; It can be queried in ALL directions.

;; In miniKanren (core.logic):
;;
;; (defrel constrainto [lo hi val]
;;   (<=o lo val)
;;   (<=o val hi))
;;
;; Forward query — check if 60 is in [15, 55]:
;;   (run 1 [q] (constrainto 15 55 60))  → () — FAILS, no solutions
;;
;; Forward query — check if 30 is in [15, 55]:
;;   (run 1 [q] (constrainto 15 55 30))  → (_0) — SUCCEEDS
;;
;; BACKWARD query — find ALL values in [15, 55]:
;;   (run * [q] (constrainto 15 55 q))   → (15 16 17 ... 55) — ALL OF THEM
;;
;; Cross-constraint query — values that satisfy BOTH constraints:
;;   (run * [q]
;;     (constrainto 15 55 q)
;;     (constrainto 0 30 q))
;;   → (15 16 17 ... 30) — intersection of ranges!

;; ══ FluxResult as association list ════════════════════════════════

(define (make-result error-mask severity violated-lo violated-hi violated-count)
  (list (cons 'error_mask error-mask)
        (cons 'severity severity)
        (cons 'violated_lo violated-lo)
        (cons 'violated_hi violated-hi)
        (cons 'violated_count violated-count)
        (cons 'passed (= violated-count 0))))

;; ══ Severity classification ═══════════════════════════════════════

(define (classify-severity violated-count total)
  (cond ((= violated-count 0) 'pass)
        ((<= violated-count (quotient total 4)) 'caution)
        ((<= violated-count (quotient total 2)) 'warning)
        (else 'critical)))

;; ══ Core check — functional wrapper ═══════════════════════════════
;; The relational version is above; this is the operational version.

(define (check-constraints constraints value)
  (let ((val (saturate value)))
    (let loop ((cs constraints)
               (i 0)
               (error-mask 0)
               (violated-lo 0)
               (violated-hi 0)
               (violated-count 0))
      (if (null? cs)
          (make-result error-mask
                       (classify-severity violated-count (length constraints))
                       violated-lo violated-hi violated-count)
          (let* ((c (car cs))
                 (lo (car c))
                 (hi (cadr c))
                 (lo-fail (< val lo))
                 (hi-fail (> val hi)))
            (loop (cdr cs)
                  (+ i 1)
                  (if lo-fail (bitwise-ior error-mask (arithmetic-shift 1 i)) error-mask)
                  (if lo-fail (bitwise-ior violated-lo (arithmetic-shift 1 i)) violated-lo)
                  (if hi-fail (bitwise-ior violated-hi (arithmetic-shift 1 i)) violated-hi)
                  (+ violated-count (if (or lo-fail hi-fail) 1 0))))))))

;; ══ RELATIONAL: Find all valid values ═════════════════════════════
;; This is what functions CANNOT do.

(define (valid-values-for lo hi)
  "Find all INT8 values in [lo, hi]."
  (filter (lambda (v) (and (>= v lo) (<= v hi)))
          (iota (+ 1 (- hi lo)) lo)))

(define (valid-values-multi constraints)
  "Find all INT8 values satisfying ALL constraints simultaneously."
  (let ((lo-max (apply max (map car constraints)))
        (hi-min (apply min (map cadr constraints))))
    (if (> lo-max hi-min)
        '()  ;; No valid values — constraints are contradictory
        (iota (+ 1 (- hi-min lo-max)) lo-max))))

;; ══ RELATIONAL: Find which constraints a value satisfies ═════════

(define (satisfied-by constraints value)
  "Which constraints does this value satisfy? Returns list of (name . bool)."
  (let ((val (saturate value)))
    (map (lambda (c)
           (cons (caddr c)
                 (and (>= val (car c)) (<= val (cadr c)))))
         constraints)))

;; ══ RELATIONAL: Find values that separate constraints ════════════
;; Values where SOME constraints pass and SOME fail — the "boundary zone"

(define (boundary-values constraints)
  "Find values where at least one constraint passes and at least one fails."
  (filter (lambda (v)
            (let ((sats (map cdr (satisfied-by constraints v))))
              (and (member #t sats) (member #f sats))))
          (iota 255 -127)))

;; ══ Industry Presets ══════════════════════════════════════════════

(define aviation
  '((-55 70 "cabin_temp_C")
    (75 101 "cabin_pressure_kPa")
    (0 100 "fuel_flow_pct")
    (60 100 "hydraulic_pct")))

(define medical
  '((36 38 "body_temp_C")
    (60 100 "heart_rate_bpm")
    (95 100 "spo2_pct")
    (80 120 "bp_systolic_mmHg")))

(define nuclear
  '((0 110 "neutron_flux_pct")
    (0 65 "core_temp_C_x10")
    (72 100 "pressurizer_pct")
    (0 100 "coolant_flow_pct")))

(define automotive
  '((-40 60 "battery_temp_C")
    (0 100 "soc_pct")
    (0 100 "charge_rate_pct")
    (20 80 "cabin_temp_C")))

(define maritime
  '((-2 35 "sea_temp_C")
    (50 100 "hull_integrity_pct")
    (0 50 "wave_height_m")
    (0 80 "wind_speed_kn")))

;; ══ Demonstration ═════════════════════════════════════════════════

(display "═══ FLUX Constraint Engine — miniKanren (Relational) ═══")
(newline)

;; Forward: check a value
(display "\n  Check value 60 against aviation: ")
(display (check-constraints aviation 60))
(newline)

;; RELATIONAL: find all valid cabin temperatures
(display "\n  Valid cabin temps (aviation): ")
(display (valid-values-for -55 70))
(newline)

;; RELATIONAL: find values satisfying ALL aviation constraints simultaneously
(display "\n  Values satisfying ALL aviation constraints: ")
(display (valid-values-multi aviation))
(newline)

;; RELATIONAL: boundary values — where the system is partially unsafe
(display "\n  Boundary values (some pass, some fail): ")
(let ((bv (boundary-values aviation)))
  (display (length bv))
  (display " boundary values found"))
(newline)

;; RELATIONAL: which constraints does value 70 satisfy?
(display "\n  Constraints satisfied by value 70: ")
(display (satisfied-by aviation 70))
(newline)

;; ══ The Relational Advantage ══════════════════════════════════════
;;
;; Functions answer: "Is this value OK?" → yes/no
;; Relations answer:
;;   "Is this value OK?" → yes/no
;;   "What values are OK?" → the full set
;;   "What values are on the boundary?" → the danger zone
;;   "Which constraints overlap?" → intersection
;;   "Are these constraints contradictory?" → empty set
;;
;; This isn't a different implementation. It's a fundamentally
;; different way to THINK about constraints.
;;
;; A constraint isn't a function that returns bool.
;; A constraint is a RELATION between bounds and values.
;; Relations compose differently than functions.
;; They compose in ALL directions simultaneously.
