#!/usr/bin/env ruby
# Test Ruby implementation against golden vectors
require 'json'
require_relative '../src/ruby/flux_constraint'

vectors = JSON.parse(File.read(File.join(__dir__, 'golden_vectors.json')))
mismatches = 0

vectors.each do |v|
    cs = v['constraints'].map { |c| {lo: c['lo'], hi: c['hi'], name: ''} }
    fc = FluxChecker.new(cs)
    r = fc.check(v['value'])
    exp = v['expected']
    if r[:error_mask] != exp['error_mask'] || r[:passed] != exp['passed']
        mismatches += 1
        puts "MISMATCH ##{v['id']}" if mismatches <= 5
    end
end

puts "\nRuby: #{vectors.length} vectors, #{mismatches} mismatches"
exit(mismatches > 0 ? 1 : 0)
