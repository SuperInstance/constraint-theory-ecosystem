{-# LANGUAGE RecordWildCards #-}
-- |
-- FLUX Constraint Engine — Haskell
-- Pure functional INT8 saturated constraint checking
-- Zero dependencies (base only)
--
-- Usage:
--   import Flux.Constraint
--   let checker = mkChecker [Constraint 0 100 "temp", Constraint (-50) 50 "pressure"]
--   let result = check checker 70
--   print (severity result)

module Flux.Constraint
  ( -- * Types
    Constraint (..)
  , FluxResult (..)
  , Severity (..)
  , FluxChecker
    -- * Construction
  , mkChecker
  , fromPreset
  , availablePresets
    -- * Operations
  , check
  , checkBatch
  , saturate
    -- * Benchmark
  , benchmark
  ) where

import Data.List (intercalate)
import Data.Time.Clock (getCurrentTime, diffUTCTime)
import Data.Bits (popCount, (.|.), shiftL)

-- | INT8 saturation bounds
int8Min, int8Max :: Int
int8Min = -127
int8Max = 127

-- | Clamp to saturated INT8 [-127, 127]
saturate :: Int -> Int
saturate = max int8Min . min int8Max

-- | Severity levels
data Severity = Pass | Caution | Warning | Critical
  deriving (Eq, Show, Ord, Enum, Bounded)

-- | A single constraint definition
data Constraint = Constraint
  { cLo   :: Int
  , cHi   :: Int
  , cName :: String
  } deriving (Show, Eq)

-- | Result of a constraint check
data FluxResult = FluxResult
  { errorMask    :: Int
  , severity     :: Severity
  , violatedLo   :: Int
  , violatedHi   :: Int
  , violatedCnt  :: Int
  , passed       :: Bool
  , resultDetails :: [(String, Int, Int, Bool)]
  } deriving (Show, Eq)

-- | A constraint checker holding up to 8 constraints
newtype FluxChecker = FluxChecker [Constraint]
  deriving (Show, Eq)

-- | Create a checker from a list of constraints
mkChecker :: [Constraint] -> Either String FluxChecker
mkChecker [] = Left "FluxChecker requires non-empty constraints"
mkChecker cs
  | length cs > 8 = Left "Maximum 8 constraints (INT8 × 8 flat bounds)"
  | otherwise = Right $ FluxChecker (map saturateConstraint cs)
  where
    saturateConstraint c@Constraint{..} = c { cLo = saturate cLo, cHi = saturate cHi }

-- | Check a single value
check :: FluxChecker -> Int -> FluxResult
check (FluxChecker cs) rawVal = FluxResult{..}
  where
    val = saturate rawVal
    nc = length cs

    go :: Int -> Int -> Int -> Int -> Int -> [(String, Int, Int, Bool)]
       -> Int -> [(Constraint, Int)] -> FluxResult
    go em vlo vhi vc dets _ [] = FluxResult
      { errorMask = em
      , severity = severityFromCount vc nc
      , violatedLo = vlo
      , violatedHi = vhi
      , violatedCnt = vc
      , passed = vc == 0
      , resultDetails = reverse dets
      }
    go em vlo vhi vc dets bit (c:rest) =
      let lo = cLo c
          hi = cHi c
          loFail = val < lo
          hiFail = val > hi
          ok = not loFail && not hiFail
          em' = if ok then em else em .|. shiftL 1 bit
          vlo' = if loFail then vlo .|. shiftL 1 bit else vlo
          vhi' = if hiFail then vhi .|. shiftL 1 bit else vhi
          vc' = if ok then vc else vc + 1
          dets' = (cName c, lo, hi, ok) : dets
      in go em' vlo' vhi' vc' dets' (bit + 1) rest

    FluxResult{..} = go 0 0 0 0 [] 0 (zip cs [0..])

severityFromCount :: Int -> Int -> Severity
severityFromCount 0 _ = Pass
severityFromCount vc nc
  | vc <= nc `div` 4 = Caution
  | vc <= nc `div` 2 = Warning
  | otherwise        = Critical

-- | Check a batch of values
checkBatch :: FluxChecker -> [Int] -> [FluxResult]
checkBatch checker = map (check checker)

-- | Industry presets
presets :: [(String, [Constraint])]
presets =
  [ ("aviation",
      [ Constraint (-55) 70 "cabin_temp_C"
      , Constraint 75 101 "cabin_pressure_kPa"
      , Constraint 0 100 "fuel_flow_pct"
      , Constraint 60 100 "hydraulic_pct"
      ])
  , ("medical",
      [ Constraint 36 38 "body_temp_C"
      , Constraint 60 100 "heart_rate_bpm"
      , Constraint 95 100 "spo2_pct"
      , Constraint 80 120 "bp_systolic_mmHg"
      ])
  , ("maritime",
      [ Constraint (-2) 35 "sea_temp_C"
      , Constraint 50 100 "hull_integrity_pct"
      , Constraint 0 50 "wave_height_m"
      , Constraint 0 80 "wind_speed_kn"
      ])
  , ("automotive",
      [ Constraint (-40) 60 "battery_temp_C"
      , Constraint 0 100 "soc_pct"
      , Constraint 0 100 "charge_rate_pct"
      , Constraint 20 80 "cabin_temp_C"
      ])
  , ("energy",
      [ Constraint 49 51 "grid_freq_Hz_x10"
      , Constraint 95 105 "voltage_pct"
      , Constraint 0 80 "transformer_temp_C"
      , Constraint 0 100 "line_load_pct"
      ])
  ]

-- | Load a preset by name
fromPreset :: String -> Either String FluxChecker
fromPreset name = case lookup name presets of
  Nothing -> Left $ "Unknown preset: " ++ name ++ ". Available: " ++ intercalate ", " (map fst presets)
  Just cs -> mkChecker cs

-- | List available presets
availablePresets :: [String]
availablePresets = map fst presets

-- | Benchmark: check N values and report rate
benchmark :: FluxChecker -> Int -> IO (Double, Double)
benchmark checker n = do
  let values = map ((`mod` 254) . subtract 127) [0..n-1]
  t0 <- getCurrentTime
  let !_ = checkBatch checker values
  t1 <- getCurrentTime
  let elapsed = realToFrac (diffUTCTime t1 t0) :: Double
      nc = length (case checker of FluxChecker cs -> cs)
      rate = fromIntegral (n * nc) / elapsed
  return (rate, elapsed)
