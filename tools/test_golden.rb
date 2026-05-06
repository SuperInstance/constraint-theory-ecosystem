require 'json'
require_relative '../src/ruby/flux_constraint'

vectors = JSON.parse(File.read(File.join(__dir__, 'golden_vectors.json')))
mismatches = 0

vectors.each do |v|
  rules = v['constraints'].map { |c| Flux::FluxRule.new("c", c['lo'], c['hi'], Flux::CAUTION, Flux::WARNING, Flux::CRITICAL) }
  fc = Flux::ConstraintChecker.new(rules)
  r = fc.check(v['value'])
  exp = v['expected']
  # Ruby FluxResult: Struct with passed, severity, violations
  if r.passed != exp['passed']
    mismatches += 1
    puts "MISMATCH ##{v['id']}: value=#{v['value']} got passed=#{r.passed} expected=#{exp['passed']}" if mismatches <= 5
  end
end

puts "\nRuby: #{vectors.length} vectors, #{mismatches} mismatches"
exit(mismatches > 0 ? 1 : 0)
