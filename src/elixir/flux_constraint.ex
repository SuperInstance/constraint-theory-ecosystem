defmodule Flux.Constraint do
  @moduledoc """
  FLUX Constraint Engine — Elixir
  Pure INT8 saturated constraint checking. Zero dependencies.
  """

  @int8_min -127
  @int8_max 127

  @presets %{
    aviation: [
      %{lo: -55, hi: 70, name: "cabin_temp_C"},
      %{lo: 75, hi: 101, name: "cabin_pressure_kPa"},
      %{lo: 0, hi: 100, name: "fuel_flow_pct"},
      %{lo: 60, hi: 100, name: "hydraulic_pct"}
    ],
    medical: [
      %{lo: 36, hi: 38, name: "body_temp_C"},
      %{lo: 60, hi: 100, name: "heart_rate_bpm"},
      %{lo: 95, hi: 100, name: "spo2_pct"},
      %{lo: 80, hi: 120, name: "bp_systolic_mmHg"}
    ],
    maritime: [
      %{lo: -2, hi: 35, name: "sea_temp_C"},
      %{lo: 50, hi: 100, name: "hull_integrity_pct"},
      %{lo: 0, hi: 50, name: "wave_height_m"},
      %{lo: 0, hi: 80, name: "wind_speed_kn"}
    ],
    automotive: [
      %{lo: -40, hi: 60, name: "battery_temp_C"},
      %{lo: 0, hi: 100, name: "soc_pct"},
      %{lo: 0, hi: 100, name: "charge_rate_pct"},
      %{lo: 20, hi: 80, name: "cabin_temp_C"}
    ],
    energy: [
      %{lo: 49, hi: 51, name: "grid_freq_Hz_x10"},
      %{lo: 95, hi: 105, name: "voltage_pct"},
      %{lo: 0, hi: 80, name: "transformer_temp_C"},
      %{lo: 0, hi: 100, name: "line_load_pct"}
    ]
  }

  @doc "Clamp to saturated INT8 [-127, 127]"
  def saturate(val) when val < @int8_min, do: @int8_min
  def saturate(val) when val > @int8_max, do: @int8_max
  def saturate(val), do: val

  @doc "Create a checker from constraints list"
  def new(constraints) when is_list(constraints) and length(constraints) > 0 and length(constraints) <= 8 do
    constraints
    |> Enum.map(&%{&1 | lo: saturate(&1.lo), hi: saturate(&1.hi)})
  end

  @doc "Check a single value against constraints"
  def check(constraints, value) do
    val = saturate(value)

    {error_mask, violated_lo, violated_hi, violated_count} =
      constraints
      |> Enum.with_index()
      |> Enum.reduce({0, 0, 0, 0}, fn {c, i}, {em, vlo, vhi, vc} ->
        lo_fail = val < c.lo
        hi_fail = val > c.hi

        em2 = if lo_fail or hi_fail, do: em ||| Bitwise.bsl(1, i), else: em
        vlo2 = if lo_fail, do: vlo ||| Bitwise.bsl(1, i), else: vlo
        vhi2 = if hi_fail, do: vhi ||| Bitwise.bsl(1, i), else: vhi
        vc2 = if lo_fail or hi_fail, do: vc + 1, else: vc

        {em2, vlo2, vhi2, vc2}
      end)

    nc = length(constraints)
    severity = cond do
      violated_count == 0 -> :pass
      violated_count <= div(nc, 4) -> :caution
      violated_count <= div(nc, 2) -> :warning
      true -> :critical
    end

    %{
      error_mask: error_mask,
      severity: severity,
      violated_lo: violated_lo,
      violated_hi: violated_hi,
      violated_count: violated_count,
      passed: severity == :pass
    }
  end

  @doc "Check a batch of values"
  def check_batch(constraints, values) do
    results = Enum.map(values, &check(constraints, &1))
    stats = %{
      pass: Enum.count(results, & &1.severity == :pass),
      caution: Enum.count(results, & &1.severity == :caution),
      warning: Enum.count(results, & &1.severity == :warning),
      critical: Enum.count(results, & &1.severity == :critical)
    }
    {results, stats}
  end

  @doc "Load a preset by name"
  def from_preset(name) do
    Map.get(@presets, name) || raise "Unknown preset: #{name}. Available: #{Enum.join(Map.keys(@presets), ", ")}"
  end

  @doc "List available presets"
  def available_presets, do: Map.keys(@presets)

  @doc "Benchmark: returns {rate, ms}"
  def benchmark(constraints, iterations \\ 1_000_000) do
    {t0, _} = :erlang.statistics(:wall_clock)
    Enum.each(0..(iterations - 1), fn i ->
      check(constraints, rem(i, 254) - 127)
    end)
    {t1, _} = :erlang.statistics(:wall_clock)
    ms = t1 - t0
    rate = iterations * length(constraints) / (ms / 1000.0)
    {rate, ms * 1.0}
  end
end

# Inline tests (run with: elixir flux_constraint.ex)
# ExUnit would normally be used, but for zero-dep simplicity:
IO.puts("╔══════════════════════════════════════════════════════╗")
IO.puts("║  FLUX Constraint Engine — Elixir                     ║")
IO.puts("╚══════════════════════════════════════════════════════╝\n")

alias Flux.Constraint

# Test 1: Saturate
:ok = if Constraint.saturate(-128) == -127 and Constraint.saturate(128) == 127 and Constraint.saturate(0) == 0 do
  IO.puts("✓ saturate boundaries"); :ok
else
  raise "saturate failed"
end

# Test 2: Pass
fc = Constraint.new([%{lo: 0, hi: 100, name: "test"}])
r1 = Constraint.check(fc, 50)
:ok = if r1.passed do IO.puts("✓ single pass"); :ok else raise "should pass" end

# Test 3: Fail
r2 = Constraint.check(fc, 150)
:ok = if not r2.passed do IO.puts("✓ single fail"); :ok else raise "should fail" end

# Test 4: Critical
fc2 = Constraint.new([%{lo: 0, hi: 10, name: "a"}, %{lo: 0, hi: 10, name: "b"},
                       %{lo: 0, hi: 10, name: "c"}, %{lo: 0, hi: 10, name: "d"}])
r3 = Constraint.check(fc2, 50)
:ok = if r3.severity == :critical and r3.violated_count == 4 do
  IO.puts("✓ severity critical"); :ok
else
  raise "should be critical"
end

# Test 5: Preset
fc3 = Constraint.from_preset(:aviation)
:ok = if length(fc3) == 4 do IO.puts("✓ preset loading"); :ok else raise "4 constraints" end

# Test 6: Batch
{results, _stats} = Constraint.check_batch(fc, [-60, 0, 50, 100, 127])
:ok = if length(results) == 5 do IO.puts("✓ batch checking"); :ok else raise "5 results" end

# Benchmark
{rate, ms} = Constraint.benchmark(fc3)
IO.puts("\n  Benchmark: #{Float.round(rate / 1.0e6, 1)}M checks/sec (#{Float.round(ms, 1)}ms)")
IO.puts("\n  ✓ All tests pass")
