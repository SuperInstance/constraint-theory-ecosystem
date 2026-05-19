-- FLUX Constraint Engine — Elm (2012, Reactive/Functional)
-- Pure INT8 saturated constraint checking. Zero dependencies.
--
-- The insight: Elm's Architecture (TEA) is built around signals and updates.
-- Constraints are SIGNALS that the view reacts to. No runtime exceptions.
-- The compiler GUARANTEES every case is handled. Every violation is rendered.
-- Constraint checking in Elm is inherently REACTIVE — the UI updates
-- automatically when values change.
--
-- "The Architecture IS the constraint. The view REACTS to violations.
--  No runtime exceptions. The compiler proves every case is handled."

module FluxConstraint exposing
    ( Severity(..)
    , Constraint
    , FluxResult
    , saturate
    , check
    , checkBatch
    , classifySeverity
    , aviation
    , automotive
    , nuclear
    , maritime
    , medical
    )

import List


-- ══ Constants ══════════════════════════════════════════════════════

int8Min : Int
int8Min =
    -127


int8Max : Int
int8Max =
    127


maxConstraints : Int
maxConstraints =
    8


-- ══ Severity ══════════════════════════════════════════════════════

type Severity
    = Pass
    | Caution
    | Warning
    | Critical


severityToString : Severity -> String
severityToString sev =
    case sev of
        Pass -> "PASS"
        Caution -> "CAUTION"
        Warning -> "WARNING"
        Critical -> "CRITICAL"


-- ══ Constraint ════════════════════════════════════════════════════

type alias Constraint =
    { lo : Int
    , hi : Int
    , name : String
    }


-- ══ FluxResult ═══════════════════════════════════════════════════

type alias FluxResult =
    { errorMask : Int
    , severity : Severity
    , violatedLo : Int
    , violatedHi : Int
    , violatedCount : Int
    , passed : Bool
    }


-- ══ Saturate ══════════════════════════════════════════════════════

saturate : Int -> Int
saturate val =
    Basics.max int8Min (Basics.min int8Max val)


-- ══ Severity classification ══════════════════════════════════════

classifySeverity : Int -> Int -> Severity
classifySeverity vc n =
    if vc == 0 then
        Pass
    else if n > 0 && vc <= n // 4 then
        Caution
    else if n > 0 && vc <= n // 2 then
        Warning
    else
        Critical


-- ══ Core check ═══════════════════════════════════════════════════

check : List Constraint -> Int -> FluxResult
check constraints rawVal =
    let
        val =
            saturate rawVal

        n =
            List.length constraints

        step : Int -> Constraint -> ( Int, Int, Int, Int ) -> ( Int, Int, Int, Int )
        step idx c ( em, vlo, vhi, vc ) =
            let
                loFail =
                    val < c.lo

                hiFail =
                    val > c.hi

                anyFail =
                    loFail || hiFail

                bit =
                    1 << idx
            in
            ( if anyFail then Bitwise.or em bit else em
            , if loFail then Bitwise.or vlo bit else vlo
            , if hiFail then Bitwise.or vhi bit else vhi
            , if anyFail then vc + 1 else vc
            )

        ( finalEm, finalVlo, finalVhi, finalVc ) =
            constraints
                |> List.indexedMap (\i c -> ( i, c ))
                |> List.foldl (\( i, c ) acc -> step i c acc) ( 0, 0, 0, 0 )
    in
    { errorMask = finalEm
    , severity = classifySeverity finalVc n
    , violatedLo = finalVlo
    , violatedHi = finalVhi
    , violatedCount = finalVc
    , passed = finalVc == 0
    }


-- ══ Batch check ══════════════════════════════════════════════════

checkBatch : List Constraint -> List Int -> List FluxResult
checkBatch constraints values =
    List.map (\v -> check constraints v) values


-- ══ Industry Presets ══════════════════════════════════════════════

aviation : List Constraint
aviation =
    [ { lo = -55, hi = 70, name = "cabin_temp_C" }
    , { lo = 75, hi = 101, name = "cabin_pressure_kPa" }
    , { lo = 0, hi = 100, name = "fuel_flow_pct" }
    , { lo = 60, hi = 100, name = "hydraulic_pct" }
    ]

automotive : List Constraint
automotive =
    [ { lo = -40, hi = 60, name = "battery_temp_C" }
    , { lo = 0, hi = 100, name = "soc_pct" }
    , { lo = 0, hi = 100, name = "charge_rate_pct" }
    , { lo = 20, hi = 80, name = "cabin_temp_C" }
    ]

nuclear : List Constraint
nuclear =
    [ { lo = 0, hi = 110, name = "neutron_flux_pct" }
    , { lo = 0, hi = 65, name = "core_temp_C_x10" }
    , { lo = 72, hi = 100, name = "pressurizer_pct" }
    , { lo = 0, hi = 100, name = "coolant_flow_pct" }
    ]

maritime : List Constraint
maritime =
    [ { lo = -2, hi = 35, name = "sea_temp_C" }
    , { lo = 50, hi = 100, name = "hull_integrity_pct" }
    , { lo = 0, hi = 50, name = "wave_height_m" }
    , { lo = 0, hi = 80, name = "wind_speed_kn" }
    ]

medical : List Constraint
medical =
    [ { lo = 36, hi = 38, name = "body_temp_C" }
    , { lo = 60, hi = 100, name = "heart_rate_bpm" }
    , { lo = 95, hi = 100, name = "spo2_pct" }
    , { lo = 80, hi = 120, name = "bp_systolic_mmHg" }
    ]


-- ══ Usage Example ════════════════════════════════════════════════
--
-- In a TEA app, constraints are part of the Model:
--
--   type alias Model =
--       { sensorValue : Int
--       , constraints : List Constraint
--       , result : FluxResult
--       }
--
--   update : Msg -> Model -> ( Model, Cmd Msg )
--   update msg model =
--       case msg of
--           SensorReading val ->
--               ( { model
--                   | sensorValue = val
--                   , result = check model.constraints val
--                 }
--               , Cmd.none
--               )
--
--   view : Model -> Html Msg
--   view model =
--       let
--           color = if model.result.passed then "green" else "red"
--       in
--       div []
--           [ h1 [] [ text ("Sensor: " ++ String.fromInt model.sensorValue) ]
--           , p [ style "color" color ]
--               [ text (severityToString model.result.severity) ]
--           ]
--
-- The view REACTS to the constraint result. No manual DOM updates.
-- No runtime exceptions — Elm's compiler guarantees it.
