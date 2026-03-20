"use client";

import { useState } from "react";
import { fetchPredictions, type PredictionResponse } from "./api";

const BOATS = ["1x", "2x", "4x", "8+"] as const;
const SEXES = ["men", "women"] as const;
const WEIGHTS = ["openweight", "lightweight"] as const;
const DIRECTIONS = ["upstream", "downstream"] as const;

function deltaColor(delta: number): string {
  if (delta > 0.5) return "slow";
  if (delta < -0.5) return "fast";
  return "neutral";
}

function formatSplit(seconds: number): string {
  const safeSeconds = Math.max(0, seconds);
  const minutes = Math.floor(safeSeconds / 60);
  const secs = safeSeconds - minutes * 60;
  return `${minutes}:${secs.toFixed(2).padStart(5, "0")}`;
}

export default function Page() {
  const [boat, setBoat] = useState<(typeof BOATS)[number]>("1x");
  const [sex, setSex] = useState<(typeof SEXES)[number]>("men");
  const [weight, setWeight] = useState<(typeof WEIGHTS)[number]>("openweight");
  const [direction, setDirection] = useState<(typeof DIRECTIONS)[number]>("upstream");
  const [date, setDate] = useState<string>(new Date().toISOString().slice(0, 10));
  const [data, setData] = useState<PredictionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onPredict() {
    setLoading(true);
    setError(null);
    try {
      const payload = await fetchPredictions({
        boat_class: boat,
        sex,
        weight_class: weight,
        direction,
        date,
      });
      setData(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="container">
      <h1>Charles River Daily Split Predictor</h1>
      <section className="controls">
        <label>
          Boat
          <select value={boat} onChange={(e) => setBoat(e.target.value as (typeof BOATS)[number])}>
            {BOATS.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label>
          Sex
          <select value={sex} onChange={(e) => setSex(e.target.value as (typeof SEXES)[number])}>
            {SEXES.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label>
          Weight class
          <select
            value={weight}
            onChange={(e) => setWeight(e.target.value as (typeof WEIGHTS)[number])}
          >
            {WEIGHTS.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label>
          Direction
          <select
            value={direction}
            onChange={(e) => setDirection(e.target.value as (typeof DIRECTIONS)[number])}
          >
            {DIRECTIONS.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label>
          Date
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
        <button onClick={onPredict} disabled={loading}>
          {loading ? "Predicting..." : "Get Predictions"}
        </button>
      </section>

      {error && <p className="error">{error}</p>}

      {data && (
        <section>
          <p>
            Charles Speed Index: <strong>{data.meta.charles_speed_index}s</strong>
          </p>
          {data.hourly.map((hour) => (
            <div key={hour.timestamp} className="hour-block">
              <h3>{new Date(hour.timestamp).toLocaleString()}</h3>
              <p>
                Water Temp: <strong>{hour.water_temp.toFixed(1)}F</strong> | Flow Rate:{" "}
                <strong>{hour.flow_rate.toFixed(0)} cfs</strong> | Wind Speed:{" "}
                <strong>{hour.wind_speed.toFixed(1)} mph</strong>
              </p>
              <table>
                <thead>
                  <tr>
                    <th>Rate</th>
                    <th>Baseline</th>
                    <th>Adjusted</th>
                    <th>Delta</th>
                  </tr>
                </thead>
                <tbody>
                  {hour.rows.map((row) => (
                    <tr key={row.rate}>
                      <td>{row.rate}</td>
                      <td>{formatSplit(row.baseline)}</td>
                      <td>{formatSplit(row.adjusted)}</td>
                      <td className={deltaColor(row.delta)}>{row.delta.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </section>
      )}
    </main>
  );
}
