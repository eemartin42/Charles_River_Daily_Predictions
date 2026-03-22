"use client";

import type { CSSProperties } from "react";
import { useMemo, useState } from "react";
import { GoogleMap, InfoWindow, Marker, Polyline, useJsApiLoader } from "@react-google-maps/api";

import type { MapSegment } from "../app/api";

export type { MapSegment };

const mapContainerStyle: CSSProperties = {
  width: "100%",
  height: "420px",
  borderRadius: "8px",
};

/** Smoothing window in vertex steps (must match backend intent for display). */
const HEADING_SMOOTH_WINDOW = 4;
/** Show one wind arrow every N segments to reduce clutter. */
const WIND_ARROW_EVERY = 4;

/** Geographic bearing p1→p2 (deg from north, clockwise); lng scaled by cos(mean lat). */
function computeHeadingGeographic(p1: google.maps.LatLngLiteral, p2: google.maps.LatLngLiteral): number {
  const lat1 = (p1.lat * Math.PI) / 180;
  const lat2 = (p2.lat * Math.PI) / 180;
  const dLat = lat2 - lat1;
  const dLng = ((p2.lng - p1.lng) * Math.PI) / 180;
  const x = dLng * Math.cos((lat1 + lat2) / 2);
  const y = dLat;
  return (((Math.atan2(x, y) * 180) / Math.PI) + 360) % 360;
}

/** Chord heading at vertex i using symmetric window (visual / parity with backend smoothing). */
function computeSmoothedHeading(
  path: google.maps.LatLngLiteral[],
  i: number,
  window: number
): number {
  if (path.length < 2) return 0;
  const start = path[Math.max(0, i - window)];
  const end = path[Math.min(path.length - 1, i + window)];
  return computeHeadingGeographic(start, end);
}

function buildVertexPathFromSegments(segments: MapSegment[]): google.maps.LatLngLiteral[] {
  const out: google.maps.LatLngLiteral[] = [];
  for (const seg of segments) {
    for (const p of seg.path) {
      const last = out[out.length - 1];
      if (
        last &&
        Math.abs(last.lat - p.lat) < 1e-9 &&
        Math.abs(last.lng - p.lng) < 1e-9
      ) {
        continue;
      }
      out.push({ lat: p.lat, lng: p.lng });
    }
  }
  return out;
}

/** Positive delta = slower (red); negative = faster (green). */
function deltaToColor(delta: number, minD: number, maxD: number): string {
  if (!Number.isFinite(delta)) return "#64748b";
  if (maxD <= minD) return "#64748b";
  const t = (delta - minD) / (maxD - minD);
  const r = Math.round(255 * t);
  const g = Math.round(255 * (1 - t));
  return `rgb(${r},${g},72)`;
}

/** Blend delta heat color with direction accent so upstream vs downstream are visually distinct. */
function deltaColorWithDirection(
  delta: number,
  minD: number,
  maxD: number,
  direction: "upstream" | "downstream",
  mix = 0.22
): string {
  const base = deltaToColor(delta, minD, maxD);
  const m = base.match(/rgb\((\d+),(\d+),(\d+)\)/);
  if (!m) return base;
  const r0 = Number(m[1]);
  const g0 = Number(m[2]);
  const b0 = Number(m[3]);
  const accent =
    direction === "upstream"
      ? [37, 99, 235] // blue
      : [234, 88, 12]; // orange
  const r = Math.round(r0 * (1 - mix) + accent[0] * mix);
  const g = Math.round(g0 * (1 - mix) + accent[1] * mix);
  const b = Math.round(b0 * (1 - mix) + accent[2] * mix);
  return `rgb(${r},${g},${b})`;
}

function formatSplitSeconds(seconds: number): string {
  const s = Math.max(0, seconds);
  const m = Math.floor(s / 60);
  const sec = s - m * 60;
  return `${m}:${sec.toFixed(2).padStart(5, "0")}`;
}

/** Wind from (met) → toward (downwind), for arrow rotation. */
function windToDirectionDeg(windFromDeg: number): number {
  return ((windFromDeg + 180) % 360 + 360) % 360;
}

function clamp(n: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, n));
}

type Props = {
  segments: MapSegment[];
  windSpeedMph: number;
  windDirDeg: number;
  windCompass?: string;
  mapRate: number;
  apiKey: string;
  direction: "upstream" | "downstream";
  /** Fired with backend segment_index when user clicks a river segment polyline. */
  onSegmentSelect?: (segmentIndex: number) => void;
};

export default function RiverMap({
  segments,
  windSpeedMph,
  windDirDeg,
  windCompass,
  mapRate,
  apiKey,
  direction,
  onSegmentSelect,
}: Props) {
  const [activeIdx, setActiveIdx] = useState<number | null>(null);
  const [hoverArrowSegIdx, setHoverArrowSegIdx] = useState<number | null>(null);

  const { isLoaded, loadError } = useJsApiLoader({
    id: "charles-river-map",
    googleMapsApiKey: apiKey,
    libraries: ["geometry"],
  });

  const vertexPath = useMemo(() => buildVertexPathFromSegments(segments), [segments]);

  /** Spherical heading when Maps geometry is ready; else geographic fallback. */
  const headingAtSegmentStart = (segIndex: number): number => {
    if (vertexPath.length < 2) return 0;
    if (typeof window !== "undefined" && window.google?.maps?.geometry?.spherical) {
      const a = Math.max(0, segIndex - HEADING_SMOOTH_WINDOW);
      const b = Math.min(vertexPath.length - 1, segIndex + HEADING_SMOOTH_WINDOW);
      const p1 = vertexPath[a];
      const p2 = vertexPath[b];
      return window.google.maps.geometry.spherical.computeHeading(
        new window.google.maps.LatLng(p1.lat, p1.lng),
        new window.google.maps.LatLng(p2.lat, p2.lng)
      );
    }
    return computeSmoothedHeading(vertexPath, segIndex, HEADING_SMOOTH_WINDOW);
  };

  const center = useMemo(() => {
    if (!segments.length) return { lat: 42.36, lng: -71.08 };
    const mid = segments[Math.floor(segments.length / 2)];
    return { lat: mid.mid_lat, lng: mid.mid_lng };
  }, [segments]);

  const { minD, maxD } = useMemo(() => {
    if (!segments.length) return { minD: 0, maxD: 0 };
    const ds = segments.map((s) => s.delta);
    return { minD: Math.min(...ds), maxD: Math.max(...ds) };
  }, [segments]);

  const windToDeg = windToDirectionDeg(windDirDeg);
  const arrowScale = clamp(windSpeedMph / 15, 0.5, 2.0);

  if (!apiKey) {
    return (
      <div className="map-placeholder">
        Set <code>NEXT_PUBLIC_GOOGLE_MAPS_API_KEY</code> to show the river map.
      </div>
    );
  }

  if (loadError) {
    return <div className="map-placeholder">Could not load Google Maps.</div>;
  }

  if (!isLoaded) {
    return <div className="map-placeholder">Loading map…</div>;
  }

  if (!segments.length) {
    return <div className="map-placeholder">No segment data for this hour.</div>;
  }

  const g = window.google.maps;
  const arrowPath = g.SymbolPath.FORWARD_CLOSED_ARROW;

  return (
    <div className="map-wrap">
      <p className="map-caption">
        Map stroke rate: <strong>{mapRate}</strong> spm — <strong>{direction}</strong>: track tint{" "}
        {direction === "upstream" ? "(blue blend)" : "(orange blend)"} on top of red/green = slower/faster vs
        baseline. Arrows: <strong>wind toward</strong> (downwind); hover an arrow for split + wind.{" "}
        <strong>Click a segment</strong> to show stroke-rate tables for that location. One arrow every{" "}
        {WIND_ARROW_EVERY} segments.
      </p>
      <GoogleMap mapContainerStyle={mapContainerStyle} center={center} zoom={13}>
        {segments.map((seg, i) => (
          <Polyline
            key={seg.segment_index}
            path={seg.path}
            options={{
              strokeColor: deltaColorWithDirection(seg.delta, minD, maxD, direction),
              strokeWeight: 5,
              strokeOpacity: 0.92,
              clickable: true,
            }}
            onClick={() => {
              setHoverArrowSegIdx(null);
              setActiveIdx(i);
              onSegmentSelect?.(seg.segment_index);
            }}
          />
        ))}
        {segments.map((seg, i) =>
          i % WIND_ARROW_EVERY === 0 ? (
            <Marker
              key={`wind-${seg.segment_index}`}
              position={{ lat: seg.mid_lat, lng: seg.mid_lng }}
              onMouseOver={() => setHoverArrowSegIdx(i)}
              onMouseOut={() => setHoverArrowSegIdx((prev) => (prev === i ? null : prev))}
              icon={{
                path: arrowPath,
                scale: 3 * arrowScale,
                strokeColor: "#1d4ed8",
                fillColor: "#60a5fa",
                fillOpacity: 0.95,
                strokeWeight: 1,
                rotation: windToDeg,
              }}
            />
          ) : null
        )}
        {(() => {
          const showIdx = hoverArrowSegIdx ?? activeIdx;
          const seg = showIdx != null ? segments[showIdx] : null;
          if (!seg || showIdx == null) return null;
          const isHover = hoverArrowSegIdx != null;
          return (
            <InfoWindow
              position={{
                lat: seg.mid_lat,
                lng: seg.mid_lng,
              }}
              onCloseClick={() => {
                setActiveIdx(null);
                setHoverArrowSegIdx(null);
              }}
              options={{ disableAutoPan: isHover }}
            >
              <div className="map-info">
                {isHover ? (
                  <>
                    <strong>Wind arrow — segment {seg.segment_index}</strong>
                    <br />
                    Predicted split: <strong>{formatSplitSeconds(seg.adjusted_split)}</strong> / 500m
                    <br />
                    Δ vs baseline: {seg.delta >= 0 ? "+" : ""}
                    {seg.delta.toFixed(2)} s
                    <br />
                    Wind: <strong>{windSpeedMph.toFixed(1)} mph</strong>
                    {windCompass != null && windCompass !== "" ? (
                      <>
                        {" "}
                        from <strong>{windCompass}</strong>
                      </>
                    ) : null}{" "}
                    ({windDirDeg.toFixed(0)}° from N, meteorological)
                    <br />
                    <span className="map-info-muted">Hover leaves this tip; click a colored segment for full detail.</span>
                  </>
                ) : (
                  <>
                    <strong>Segment {seg.segment_index}</strong>
                    <br />
                    River heading (smoothed display): {headingAtSegmentStart(showIdx).toFixed(1)}° | API:{" "}
                    {seg.heading_deg.toFixed(1)}°
                    <br />
                    Headwind: {seg.headwind_mps.toFixed(2)} m/s | Cross: {seg.crosswind_mps.toFixed(2)} m/s
                    <br />
                    Baseline: {formatSplitSeconds(seg.baseline_split)} | Adjusted:{" "}
                    {formatSplitSeconds(seg.adjusted_split)}
                    <br />
                    Δ: {seg.delta >= 0 ? "+" : ""}
                    {seg.delta.toFixed(2)} s
                  </>
                )}
              </div>
            </InfoWindow>
          );
        })()}
      </GoogleMap>
    </div>
  );
}
