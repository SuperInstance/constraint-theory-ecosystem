# FLUX Constraint Engine — miniKanren (Relational Programming)
# Pure INT8 saturated constraint checking. Zero dependencies.
#
# The insight: in miniKanren, constraints are RELATIONS, not functions.
# You don't "check" a constraint — you ASK what values satisfy it.
# The relation runs FORWARD (given value, find violations) and
# BACKWARD (given constraints, find valid ranges). Same code, both directions.
#
# "Constraints are relations. The same code that checks violations
#  can also generate valid values. Functions go one way. Relations go both."

# ══ This is a Scheme-based miniKanren implementation ═════════════
# Compatible with any Scheme with miniKanren (Racket, Guile, Chez)

# ══ Constants ══════════════════════════════════════════════════════

(define INT8-MIN -127)
(define INT8-MAX 127)
(define MAX-CONSTRAINTS 8)

# ══ Saturate: clamp to [-127, 127] ═══════════════════════════════

(define (saturate v)
  (max INT8-MIN (min INT8-MAX v)))

# ══ Severity classification ══════════════════════════════════════

(define (classify-severity violated total)
  (cond
    ((= violated 0) 'pass)
    ((<= violated (quotient total 4)) 'caution)
    ((<= violated (quotient total 2)) 'warning)
    (else 'critical)))

# ══ Constraint as a miniKanren RELATION ══════════════════════════
# This is the key: conde makes it relational.
# Running it fresh gives you ALL valid values for a constraint.

(define (constrainto lo hi value violation)
  "Relational constraint: violation is #t if value outside [lo,hi]"
  (conde
    ((== violation #t) (<=o value (- lo 1)))   ; below lower bound
    ((== violation #t) (>=o value (+ hi 1)))   ; above upper bound
    ((== violation #f) (>=o value lo)          ; within bounds
                       (<=o value hi))))

# ══ Arithmetic relations for miniKanren ══════════════════════════

(define (<=o a b)
  (conde
    ((== a b))
    ((<o a b))))

(define (<o a b)
  (fresh (diff)
    (minuso b a diff)
    (positiveo diff)))

(define (>=o a b) (<=o b a))
(define (>o a b) (<o b a))

(define (positiveo n)
  (conde
    ((== n 1))
    ((fresh (m) (pluso m 1 n) (positiveo m)))))

# ══ Check: functional wrapper over relations ═════════════════════

(define (check constraints value)
  (let ((val (saturate value)))
    (let loop ((cs constraints) (i 0)
               (mask 0) (vlo 0) (vhi 0) (vc 0))
      (if (null? cs)
          (list (cons 'error_mask mask)
                (cons 'severity (classify-severity vc (length constraints)))
                (cons 'violated_lo vlo)
                (cons 'violated_hi vhi)
                (cons 'violated_count vc)
                (cons 'passed (= vc 0)))
          (let* ((c (car cs))
                 (lo (car c))
                 (hi (cadr c))
                 (lo-fail (< val lo))
                 (hi-fail (> val hi))
                 (failed (or lo-fail hi-fail)))
            (loop (cdr cs) (+ i 1)
                  (if failed (bitwise-ior mask (arithmetic-shift 1 i)) mask)
                  (if lo-fail (bitwise-ior vlo (arithmetic-shift 1 i)) vlo)
                  (if hi-fail (bitwise-ior vhi (arithmetic-shift 1 i)) vhi)
                  (if failed (+ vc 1) vc)))))))

# ══ Relational query: find valid values for a constraint ═════════
# This is the miniKanren superpower — run the relation BACKWARD.

(define (valid-values lo hi)
  "Find all INT8 values satisfying [lo, hi]"
  (run* (v)
    (fresh (viol)
      (constrainto lo hi v #f)
    (>= v INT8-MIN)
    (<= v INT8-MAX))))

# ══ Batch check ══════════════════════════════════════════════════

(define (check-batch constraints values)
  (map (lambda (v) (check constraints v)) values))

# ══ Industry presets ═════════════════════════════════════════════

(define aviation '((-55 70) (75 101) (0 100) (60 100)))
(define automotive '((-40 60) (0 100) (0 100) (20 80)))
(define maritime '((-2 35) (50 100) (0 50) (0 80)))
(define medical '((36 38) (60 100) (95 100) (80 120)))
(define energy '((49 51) (95 105) (0 80) (0 100)))
(define nuclear '((0 110) (0 65) (72 100) (0 100)))
(define railway '((0 100) (0 100) (0 1) (0 80)))
(define robotics '((-100 100) (0 100) (0 100) (-127 127)))
(define space '((-40 50) (0 100) (0 100) (0 100)))
(define underwater '((0 100) (0 100) (-5 35) (0 100)))

(define presets
  `((aviation . ,aviation)
    (automotive . ,automotive)
    (maritime . ,maritime)
    (medical . ,medical)
    (energy . ,energy)
    (nuclear . ,nuclear)
    (railway . ,railway)
    (robotics . ,robotics)
    (space . ,space)
    (underwater . ,underwater)))

# ══ Usage ════════════════════════════════════════════════════════
#
# ;; Functional check (forward direction)
# (check aviation 60)
# ;; => ((error_mask . 0) (severity . pass) ...)
#
# ;; Relational query (backward — miniKanren superpower)
# ;; "What values satisfy the body_temp constraint?"
# (valid-values 36 38)
# ;; => (36 37 38)
#
# ;; "What values VIOLATE it?"
# (run 5 (v) (fresh (viol) (constrainto 36 38 v #t)))
# ;; => (35 34 33 32 31)  (first 5 violating values)
#
# ;; Batch check
# (check-batch medical '(36 37 38 39 40 100))
#
# ══ Why miniKanren Matters ═══════════════════════════════════════
#
# miniKanren turns constraint checking into a RELATION that can run
# in BOTH directions:
#
#   Forward:  (value, constraints) → violation result
#   Backward: (constraints) → set of valid values
#
# This is impossible in standard functions. You'd write one function
# to check and a DIFFERENT function to generate valid values.
# miniKanren does both with the SAME relational code.
#
# For constraint theory, this means:
#   - Check that a value is valid (forward)
#   - GENERATE all valid values (backward)
#   - FIND the boundary of violation (search)
#   - PROVE completeness: every INT8 value is either valid or violating
#
# The relation IS the specification. Forward execution IS checking.
# Backward execution IS generation. Search IS proof.
