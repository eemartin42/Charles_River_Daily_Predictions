"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import {
  fetchPredictions,
  fetchSegmentRateRows,
  type PredictionResponse,
  type SegmentRatesResponse,
} from "./api";

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
  const [selectedSegmentIndex, setSelectedSegmentIndex] = useState<number | null>(null);
  const [segmentRates, setSegmentRates] = useState<SegmentRatesResponse | null>(null);
  const [segmentRatesLoading, setSegmentRatesLoading] = useState(false);
  const [segmentRatesError, setSegmentRatesError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (data?.hourly?.length) {
      setSelectedHourIndex(0);
      setSelectedSegmentIndex(null);
    }
  }, [data]);

  useEffect(() => {
    setSelectedSegmentIndex(null);
  }, [boat, sex, weight, direction, date, mapRate]);

  const selectedHour = data?.hourly?.[selectedHourIndex];

  useEffect(() => {
    if (!data || selectedSegmentIndex == null || !selectedHour) {
      setSegmentRates(null);
      setSegmentRatesError(null);
      setSegmentRatesLoading(false);
      return;
    }
    let cancelled = false;
    setSegmentRatesLoading(true);
    setSegmentRatesError(null);
    fetchSegmentRateRows({
      boat_class: boat,
      sex,
      weight_class: weight,
      direction,
      date,
      hour_timestamp: selectedHour.timestamp,
      segment_index: selectedSegmentIndex,
    })
      .then((r) => {
        if (!cancelled) {
          setSegmentRates(r);
          setSegmentRatesLoading(false);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setSegmentRatesError(e instanceof Error ? e.message : "Failed to load segment rates");
          setSegmentRates(null);
          setSegmentRatesLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [
    data,
    selectedSegmentIndex,
    selectedHourIndex,
    boat,
    sex,
    weight,
    direction,
    date,
    selectedHour?.timestamp,
  ]);

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
            windCompass={selectedHour.wind_compass ?? undefined}
            mapRate={data.meta.map_rate ?? mapRate}
            apiKey={mapsKey}
            direction={direction}
            onSegmentSelect={(segmentIndex) => setSelectedSegmentIndex(segmentIndex)}
          />
          {selectedSegmentIndex != null && (
            <p className="hint map-segment-hint">
              Tables below show rates for <strong>segment {selectedSegmentIndex}</strong> (local wind along that
              reach).{" "}
              <button type="button" className="link-button" onClick={() => setSelectedSegmentIndex(null)}>
                Whole-river tables
              </button>
            </p>
          )}
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
            {selectedSegmentIndex != null && (
              <>
                {" "}
                | Segment table uses wind along the selected reach (differs from whole-river aggregate).
              </>
            )}
          </p>
          <p className="hint">Click an hour block to sync the map above. Click a map segment to show rates for that location.</p>
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
              {i === selectedHourIndex && selectedSegmentIndex != null ? (
                segmentRatesLoading ? (
                  <p className="hour-conditions">Loading segment rate table…</p>
                ) : segmentRatesError ? (
                  <p className="error">{segmentRatesError}</p>
                ) : segmentRates ? (
                  <>
                    <p className="hour-conditions segment-table-note">
                      <strong>Segment {segmentRates.segment_index}</strong> — wind decomposed along this segment’s
                      heading. Headwind {segmentRates.headwind_mps.toFixed(2)} m/s · cross{" "}
                      {segmentRates.crosswind_mps.toFixed(2)} m/s · tail {segmentRates.tailwind_mps.toFixed(2)}{" "}
                      m/s. Hourly wind above matches the map hover ({segmentRates.wind_speed.toFixed(1)} mph from{" "}
                      {segmentRates.wind_compass ?? "?"}, {segmentRates.wind_dir.toFixed(0)}°).
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
                        {segmentRates.rows.map((row) => (
                          <tr key={row.rate}>
                            <td>{row.rate}</td>
                            <td>{formatSplit(row.baseline)}</td>
                            <td>{formatSplit(row.adjusted)}</td>
                            <td className={deltaColor(row.delta)}>{row.delta.toFixed(2)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </>
                ) : null
              ) : (
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
              )}
            </div>
          ))}
        </section>
      )}
    </main>
  );
}
