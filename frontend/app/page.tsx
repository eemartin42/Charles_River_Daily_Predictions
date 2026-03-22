"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { fetchPredictions, type PredictionResponse } from "./api";

const RiverMap = dynamic(() => import("../components/RiverMap"), { ssr: false });

const BOATS = ["1x", "2x", "4x", "8+"] as const;
const SEXES = ["men", "women"] as const;
const WEIGHTS = ["openweight", "lightweight"] as const;
const DIRECTIONS = ["upstream", "downstream"] as const;
const MAP_RATES = [18, 20, 22, 24, 26, 28, 30, 32, 34, 36] as const;

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

function formatWindGust(gust: number | null | undefined): string {
  if (gust != null && Number.isFinite(gust)) {
    return `${gust.toFixed(1)} mph`;
  }
  return "Not reported (NWS hourly grid often omits gusts)";
}

export default function Page() {
  const [boat, setBoat] = useState<(typeof BOATS)[number]>("1x");
  const [sex, setSex] = useState<(typeof SEXES)[number]>("men");
  const [weight, setWeight] = useState<(typeof WEIGHTS)[number]>("openweight");
  const [direction, setDirection] = useState<(typeof DIRECTIONS)[number]>("upstream");
  const [date, setDate] = useState<string>(new Date().toISOString().slice(0, 10));
  const [mapRate, setMapRate] = useState<(typeof MAP_RATES)[number]>(24);
  const [data, setData] = useState<PredictionResponse | null>(null);
  const [selectedHourIndex, setSelectedHourIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (data?.hourly?.length) {
      setSelectedHourIndex(0);
    }
  }, [data]);

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
        map_rate: String(mapRate),
      });
      setData(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  const selectedHour = data?.hourly?.[selectedHourIndex];
  const mapsKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY ?? "";

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
        <label>
          Map stroke rate
          <select
            value={mapRate}
            onChange={(e) => setMapRate(Number(e.target.value) as (typeof MAP_RATES)[number])}
          >
            {MAP_RATES.map((r) => (
              <option key={r} value={r}>
                {r} spm
              </option>
            ))}
          </select>
        </label>
        <button onClick={onPredict} disabled={loading}>
          {loading ? "Predicting..." : "Get Predictions"}
        </button>
      </section>

      {error && <p className="error">{error}</p>}

      {data && selectedHour && (
        <section className="map-section">
          <h2>River map — {new Date(selectedHour.timestamp).toLocaleString()}</h2>
          <RiverMap
            segments={selectedHour.segments ?? []}
            windSpeedMph={selectedHour.wind_speed}
            windDirDeg={selectedHour.wind_dir}
            mapRate={data.meta.map_rate ?? mapRate}
            apiKey={mapsKey}
          />
        </section>
      )}

      {data && (
        <section>
          <p>
            Charles Speed Index: <strong>{data.meta.charles_speed_index}s</strong>
            {data.meta.map_rate != null && (
              <>
                {" "}
                | Map rate: <strong>{data.meta.map_rate} spm</strong>
              </>
            )}
          </p>
          <p className="hint">Click an hour block to sync the map above.</p>
          {data.hourly.map((hour, i) => (
            <div
              key={hour.timestamp}
              className={`hour-block ${i === selectedHourIndex ? "hour-selected" : ""}`}
              onClick={() => setSelectedHourIndex(i)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setSelectedHourIndex(i);
                }
              }}
              role="button"
              tabIndex={0}
            >
              <h3>{new Date(hour.timestamp).toLocaleString()}</h3>
              <p className="hour-conditions">
                Water Temp: <strong>{hour.water_temp.toFixed(1)}°F</strong> | Flow:{" "}
                <strong>{hour.flow_rate.toFixed(0)} cfs</strong>
                <br />
                Wind: <strong>{hour.wind_speed.toFixed(1)} mph</strong> from{" "}
                <strong>{hour.wind_compass ?? "?"}</strong> (
                <strong>{Number(hour.wind_dir ?? 0).toFixed(0)}°</strong> from N)
                <br />
                Gusts: <strong>{formatWindGust(hour.wind_gust_mph)}</strong>
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
