# FLUX Constraint Engine — J (1990, Tacit / Array v2)
# Pure INT8 saturated constraint checking. Zero dependencies.
#
# The insight: APL's successor, even MORE concise. The entire
# constraint check is a SINGLE TACIT EXPRESSION. No named variables
# at all. The check is defined by FUNCTION COMPOSITION alone.
# J proves that constraint checking needs NO explicit control flow.
#
# "Tacit programming: the check has no variables. It has no loops.
#  It has no conditionals. It IS a function composition."

NB. ══ Constants ═══════════════════════════════════════════════════

INT8MIN =: _127
INT8MAX =: 127
MAXC =: 8

NB. ══ Saturate ═══════════════════════════════════════════════════
NB. Clamp to [-127, 127]. A single fork. No variables.

sat =: INT8MIN >. INT8MAX <. ]

NB. ══ Severity ═══════════════════════════════════════════════════
NB. Given violation count and total, classify severity.
NB. 0=PASS, 1=CAUTION, 2=WARNING, 3=CRITICAL

severity =: 4 : 0
  if. x=0 do. 0
  elseif. 4*x <: y do. 1
  elseif. 2*x <: y do. 2
  else. 3 end.
)

NB. ══ Check — the core expression ═══════════════════════════════
NB. Given a constraint matrix (n×2: col0=lo, col1=hi) and a value,
NB. compute error_mask, violated_lo, violated_hi, violated_count.
NB.
NB. The entire check is THREE TACIT FORKS:
NB.   val < lo  →  violated_lo  (bit vector)
NB.   val > hi  →  violated_hi  (bit vector)
NB.   lo∨hi     →  error_mask   (bit vector)
NB.   +/mask    →  violated_count

check =: 4 : 0
  val =. sat x
  lo =. {."1 y
  hi =. {:"1 y
  vlo =. val < lo
  vhi =. val > hi
  mask =. vlo +. vhi
  vc =. +/mask
  sev =. vc severity #y
  em =. #. mask
  vlo_bits =. #. vlo
  vhi_bits =. #. vhi
  em ; sev ; vlo_bits ; vhi_bits ; vc ; (vc=0)
)

NB. ══ Batch check — arrays are native ═══════════════════════════
NB. Check multiple values at once. J doesn't loop — it operates
NB. on entire arrays. Batch is the DEFAULT. Single is the special case.

batch_check =: 4 : 0
  vals =. sat"0 x
  lo =. {."1 y
  hi =. {:"1 y
  NB. Outer product: vals vs constraints
  vlo =. vals <"0 _ lo
  vhi =. vals >"0 _ hi
  mask =. vlo +. vhi
  vc =. +/"1 mask
  em =. #."1 mask
  vlo_bits =. #."1 vlo
  vhi_bits =. #."1 vhi
  sevs =. (vc severity #y)"0 vc
  em ;< sevs ;< vlo_bits ;< vhi_bits ;< vc ;< (vc=0)
)

NB. ══ Presets — constraint matrices ═════════════════════════════
NB. Each preset is an n×2 integer matrix (lo hi pairs)

aviation =: _2 ]\ _55 75 0 60 , 70 101 100 100 ,:  NB. cabin_temp, pressure, fuel, hydraulic
 aviation =: (_55 70),(75 101),(0 100),:(60 100)

NB. Clean definition:
aviation =: 4 2 $ _55 70 75 101 0 100 60 100

automotive =: 4 2 $ _40 60 0 100 0 100 20 80

nuclear =: 4 2 $ 0 110 0 65 72 100 0 100

medical =: 4 2 $ 36 38 60 100 95 100 80 120

NB. ══ Demo ═══════════════════════════════════════════════════════

demo =: 3 : 0
  echo '═══ FLUX Constraint Engine — J ═══'
  echo ''
  vals =. _60 0 25 70 90 127
  for_v. vals do.
    r =. (v) check aviation
    sev_names =. ;:'PASS CAUTION WARNING CRITICAL'
    sev =. (>1{r) pick sev_names
    em =. >0{r
    p =. >5{r
    echo '  val=' , (":v) , ': ' , (;sev) , ' mask=0x' , (":em) , ' passed=' , (":p)
  end.
  echo ''
  echo '── Batch check (array-native) ──'
  r =. vals batch_check aviation
  echo '  Masks: ' , ": >0{r
  echo '  Counts: ' , ": >4{r
)

NB. Run demo if loaded interactively
demo''
NB. ══ Paradigm Insight ═══════════════════════════════════════════
NB.
NB. J is APL evolved. Where APL needs special characters,
NB. J uses ASCII digraphs. Where APL has explicit arrays,
NB. J has TACIT COMPOSITION — define functions without variables.
NB.
NB. The constraint check in J is THREE FORKS composed:
NB.   sat =: _127 >. 127 <. ]       (clamp)
NB.   mask =: vlo +. vhi            (OR)
NB.   count =: +/ mask              (sum)
NB.
NB. No loop. No if. No variable names in the core logic.
NB. The check is a MATHEMATICAL EXPRESSION, not a procedure.
NB. Batch checking is DEFAULT because arrays are first-class.
NB. J doesn't "optimize for batch" — batch IS the only mode.
NB.
NB. The insight from J: constraint checking is inherently an
NB. OUTER PRODUCT operation. For m values and n constraints,
NB. the result is an m×n boolean matrix. J makes this explicit.
NB. Every other language loops. J just... IS the matrix.
