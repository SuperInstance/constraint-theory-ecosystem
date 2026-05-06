;; FLUX Constraint Engine — Clojure
;; Pure INT8 saturated constraint checking. Zero dependencies.

(ns flux-constraint)

(def int8-min -127)
(def int8-max 127)

(defn saturate [v]
  (max int8-min (min int8-max (int v))))

(defn check [constraints value]
  (let [val (saturate value)
        nc (count constraints)
        [em vlo vhi vc]
        (reduce (fn [[em vlo vhi vc] [i c]]
                  (let [lo (saturate (:lo c))
                        hi (saturate (:hi c))
                        lo-fail (< val lo)
                        hi-fail (> val hi)
                        bit (bit-shift-left 1 i)]
                    [(if (or lo-fail hi-fail) (bit-or em bit) em)
                     (if lo-fail (bit-or vlo bit) vlo)
                     (if hi-fail (bit-or vhi bit) vhi)
                     (if (or lo-fail hi-fail) (inc vc) vc)]))
                [0 0 0 0]
                (map-indexed vector constraints))
        sev (cond (zero? vc) :pass
                  (<= vc (quot nc 4)) :caution
                  (<= vc (quot nc 2)) :warning
                  :else :critical)]
    {:error-mask em
     :severity sev
     :violated-lo vlo
     :violated-hi vhi
     :violated-count vc
     :passed (zero? vc)}))

(defn check-batch [constraints values]
  (let [results (mapv #(check constraints %) values)
        counts (frequencies (map :severity results))]
    {:results results
     :stats {:pass (get counts :pass 0)
             :caution (get counts :caution 0)
             :warning (get counts :warning 0)
             :critical (get counts :critical 0)}}))

(def presets
  {"aviation" [{:lo -55 :hi 70 :name "cabin_temp_C"}
               {:lo 75 :hi 101 :name "cabin_pressure_kPa"}
               {:lo 0 :hi 100 :name "fuel_flow_pct"}
               {:lo 60 :hi 100 :name "hydraulic_pct"}]
   "medical"  [{:lo 36 :hi 38 :name "body_temp_C"}
               {:lo 60 :hi 100 :name "heart_rate_bpm"}
               {:lo 95 :hi 100 :name "spo2_pct"}
               {:lo 80 :hi 120 :name "bp_systolic_mmHg"}]
   "maritime" [{:lo -2 :hi 35 :name "sea_temp_C"}
               {:lo 50 :hi 100 :name "hull_integrity_pct"}
               {:lo 0 :hi 50 :name "wave_height_m"}
               {:lo 0 :hi 80 :name "wind_speed_kn"}]
   "automotive" [{:lo -40 :hi 60 :name "battery_temp_C"}
                 {:lo 0 :hi 100 :name "soc_pct"}
                 {:lo 0 :hi 100 :name "charge_rate_pct"}
                 {:lo 20 :hi 80 :name "cabin_temp_C"}]
   "energy" [{:lo 49 :hi 51 :name "grid_freq_Hz_x10"}
             {:lo 95 :hi 105 :name "voltage_pct"}
             {:lo 0 :hi 80 :name "transformer_temp_C"}
             {:lo 0 :hi 100 :name "line_load_pct"}]})

(defn from-preset [name]
  (or (get presets name)
      (throw (ex-info (str "Unknown preset: " name) {:name name}))))

;; Self-test
(when (= *file* (System/getProperty "babashka.file"))
  (println "FLUX Constraint Engine — Clojure")
  (println "===============================")
  (assert (= -127 (saturate -128)))
  (assert (= 127 (saturate 128)))
  (println "  saturate: OK")
  (let [fc [{:lo 0 :hi 100 :name "test"}]]
    (assert (:passed (check fc 50)))
    (assert (not (:passed (check fc 150))))
    (println "  check: OK"))
  (let [fc4 (repeat 4 {:lo 0 :hi 10 :name "x"})
        r (check fc4 50)]
    (assert (= :critical (:severity r)))
    (assert (= 4 (:violated-count r)))
    (println "  severity: OK"))
  (assert (= 4 (count (from-preset "aviation"))))
  (println "  presets: OK")
  (println "  All tests pass"))
