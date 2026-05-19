#lang racket

;; FLUX Constraint Engine — Racket (1995, Macro-Heavy + Contracts)
;; Pure INT8 saturated constraint checking. Zero dependencies.
;;
;; The insight: Racket's macro system generates the constraint DSL at compile time.
;; Contracts enforce invariants at module boundaries.
;; The GUARD DSL becomes a native Racket language — no parser needed.
;;
;; "Macros generate code. Contracts enforce invariants.
;;  The constraint language IS the programming language."

(require racket/contract)

;; ══ Provide with contracts ════════════════════════════════════════
;; Contracts PROVE at runtime that inputs/outputs satisfy invariants.

(provide
 (contract-out
  [saturate (-> integer? (and/c integer? (between/c -127 127)))]
  [check-all (-> (listof constraint?) integer? flux-result?)]
  [load-preset (-> symbol? (listof constraint?))]
  [valid-values (-> (listof constraint?) (listof integer?))])
 Severity ConstraintDef FluxResult
 constraint? flux-result? severity?)

;; ══ Constants ═════════════════════════════════════════════════════

(define INT8-MIN -127)
(define INT8-MAX 127)

;; ══ Severity enum ═════════════════════════════════════════════════

(define Severity '(pass caution warning critical))

(define (severity? s) (member s Severity))

;; ══ Constraint definition ═════════════════════════════════════════

(struct ConstraintDef (lo hi name) #:transparent)

(define (constraint? x) (ConstraintDef? x))

;; Constructor with saturation baked in
(define (make-constraint lo hi name)
  (ConstraintDef (saturate lo) (saturate hi) name))

;; ══ FluxResult ════════════════════════════════════════════════════

(struct FluxResult (error-mask severity violated-lo violated-hi violated-count passed)
  #:transparent)

(define (flux-result? x) (FluxResult? x))

;; ══ Saturate: clamp to [-127, 127] ════════════════════════════════
;; Contract guarantees: input any integer, output is in [-127, 127]

(define (saturate v)
  (max INT8-MIN (min INT8-MAX v)))

;; ══ Severity classification ═══════════════════════════════════════

(define (classify-severity violated-count total)
  (cond [(= violated-count 0) 'pass]
        [(<= violated-count (quotient total 4)) 'caution]
        [(<= violated-count (quotient total 2)) 'warning]
        [else 'critical]))

;; ══ Core check ════════════════════════════════════════════════════

(define (check-all constraints value)
  (when (> (length constraints) 8)
    (error 'check-all "Maximum 8 constraints"))
  (let ([val (saturate value)])
    (for/fold ([error-mask 0]
               [violated-lo 0]
               [violated-hi 0]
               [violated-count 0]
               #:result (FluxResult error-mask
                                    (classify-severity violated-count (length constraints))
                                    violated-lo violated-hi violated-count
                                    (= violated-count 0)))
              ([c (in-list constraints)]
               [i (in-naturals)])
      (let* ([lo-fail (< val (ConstraintDef-lo c))]
             [hi-fail (> val (ConstraintDef-hi c))]
             [any-fail (or lo-fail hi-fail)])
        (values (if any-fail (bitwise-ior error-mask (arithmetic-shift 1 i)) error-mask)
                (if lo-fail (bitwise-ior violated-lo (arithmetic-shift 1 i)) violated-lo)
                (if hi-fail (bitwise-ior violated-hi (arithmetic-shift 1 i)) violated-hi)
                (+ violated-count (if any-fail 1 0)))))))

;; ══ Batch check ═══════════════════════════════════════════════════

(define (check-batch constraints values)
  (for/list ([v (in-list values)])
    (check-all constraints v)))

;; ══ Relational: find all valid values ═════════════════════════════
;; Racket is a Lisp — relations are natural here too

(define (valid-values constraints)
  (for/list ([v (in-range INT8-MIN (add1 INT8-MAX))]
             #:when (FluxResult-passed (check-all constraints v)))
    v))

;; ══ MACRO: GUARD constraint DSL ══════════════════════════════════
;; This is Racket's killer feature: define new syntax!

(define-syntax (GUARD stx)
  (syntax-case stx (in with)
    [(_ name in (lo hi))
     #'(make-constraint lo hi 'name)]
    [(_ name in (lo hi) with priority level)
     #'(make-constraint lo hi 'name)]
    [(_ name > val)
     #'(make-constraint (add1 val) INT8-MAX 'name)]
    [(_ name < val)
     #'(make-constraint INT8-MIN (sub1 val) 'name)]))

;; Macro-generated preset loading
(define-syntax (define-preset stx)
  (syntax-case stx ()
    [(_ name (guard-expr ...) ...)
     #'(define name (list guard-expr ... ...))]))

;; ══ Industry Presets ══════════════════════════════════════════════

(define (load-preset preset)
  (case preset
    [(aviation)
     (list (GUARD cabin_temp_C in (-55 70))
           (GUARD cabin_pressure_kPa in (75 101))
           (GUARD fuel_flow_pct in (0 100))
           (GUARD hydraulic_pct in (60 100)))]
    [(medical)
     (list (GUARD body_temp_C in (36 38))
           (GUARD heart_rate_bpm in (60 100))
           (GUARD spo2_pct in (95 100))
           (GUARD bp_systolic_mmHg in (80 120)))]
    [(nuclear)
     (list (GUARD neutron_flux_pct in (0 110))
           (GUARD core_temp_C_x10 in (0 65))
           (GUARD pressurizer_pct in (72 100))
           (GUARD coolant_flow_pct in (0 100)))]
    [(automotive)
     (list (GUARD battery_temp_C in (-40 60))
           (GUARD soc_pct in (0 100))
           (GUARD charge_rate_pct in (0 100))
           (GUARD cabin_temp_C in (20 80)))]
    [(maritime)
     (list (GUARD sea_temp_C in (-2 35))
           (GUARD hull_integrity_pct in (50 100))
           (GUARD wave_height_m in (0 50))
           (GUARD wind_speed_kn in (0 80)))]
    [(energy)
     (list (GUARD grid_freq_Hz_x10 in (49 51))
           (GUARD voltage_pct in (95 105))
           (GUARD transformer_temp_C in (0 80))
           (GUARD line_load_pct in (0 100)))]
    [(railway)
     (list (GUARD speed_pct in (0 100))
           (GUARD brake_pressure_pct in (0 100))
           (GUARD door_interlock in (0 1))
           (GUARD track_temp_C in (0 80)))]
    [(robotics)
     (list (GUARD joint_torque_pct in (-100 100))
           (GUARD speed_pct in (0 100))
           (GUARD force_pct in (0 100))
           (GUARD position_mm in (-127 127)))]
    [(space)
     (list (GUARD temp_C in (-40 50))
           (GUARD solar_panel_pct in (0 100))
           (GUARD propellant_pct in (0 100))
           (GUARD battery_pct in (0 100)))]
    [(underwater)
     (list (GUARD depth_pct in (0 100))
           (GUARD battery_pct in (0 100))
           (GUARD water_temp_C in (-5 35))
           (GUARD thruster_pct in (0 100)))]
    [else (error 'load-preset "Unknown preset: ~a" preset)]))

;; ══ Module self-test ══════════════════════════════════════════════

(module+ test
  (require rackunit)
  
  ;; Saturate tests
  (check-equal? (saturate 0) 0)
  (check-equal? (saturate 200) 127)
  (check-equal? (saturate -200) -127)
  
  ;; Aviation preset
  (define av (load-preset 'aviation))
  (define r1 (check-all av 25))
  (check-equal? (FluxResult-passed r1) #t)
  (check-equal? (FluxResult-severity r1) 'pass)
  
  ;; Out-of-range
  (define r2 (check-all av -60))
  (check-true (member (FluxResult-severity r2) '(warning critical)))
  
  ;; Contract violation test (commented — would raise error)
  ;; (saturate "not a number") → contract violation
  
  ;; All presets load
  (for ([p '(aviation medical nuclear automotive maritime energy
             railway robotics space underwater)])
    (check-true (list? (load-preset p)))))

;; ══ Main ══════════════════════════════════════════════════════════

(module+ main
  (displayln "═══ FLUX Constraint Engine — Racket (Macros + Contracts) ═══")
  
  ;; Use the GUARD macro — it's native Racket syntax!
  (define av (load-preset 'aviation))
  (displayln (format "  Aviation: ~a constraints loaded" (length av)))
  
  ;; Check values
  (for ([v '(-60 0 25 70 90 127)])
    (define r (check-all av v))
    (displayln (format "  val=~a: ~a mask=0x~x passed=~a"
                       v (FluxResult-severity r) (FluxResult-error-mask r) (FluxResult-passed r))))
  
  ;; Find valid values
  (define medical-cs (list (GUARD body_temp_C in (36 38))))
  (displayln (format "\n  Valid body temps: ~a" (valid-values medical-cs)))
  
  ;; Contract demonstration
  (displayln "\n  Contracts enforce:")
  (displayln "    - saturate always returns [-127, 127]")
  (displayln "    - check-all only accepts constraint lists")
  (displayln "    - load-preset only accepts known preset names")
  (displayln "    - Module boundaries are invariant boundaries"))

;; ══ Usage ══════════════════════════════════════════════════════════
;;
;; Load as module:
;;   (require "flux_constraint.rkt")
;;   (define fc (load-preset 'aviation))
;;   (check-all fc 60)
;;
;; Use GUARD macro:
;;   (GUARD battery_temp in (15 55))
;;   → Creates a ConstraintDef with saturation baked in
;;
;; Run tests:
;;   racket -t flux_constraint.rkt
;;
;; The GUARD macro IS the constraint DSL.
;; No external parser. No code generation.
;; The language extension IS the implementation.
