export type MapSegment = {
  segment_index: number;
  mid_lat: number;
  mid_lng: number;
  path: { lat: number; lng: number }[];
  heading_deg: number;
  headwind_mps: number;
  crosswind_mps: number;
  baseline_split: number;
  adjusted_split: number;
  delta: number;
};

export type PredictionResponse = {
  meta: {
    date: string;
    boat_class: string;
    sex: string;
    weight_class: string;
    direction: string;
    map_rate: number;
    charles_speed_index: number;
  };
  hourly: Array<{
    timestamp: string;
    wind_speed: number;
    wind_compass: string;
    wind_dir: number;
    wind_gust_mph: number | null;
    flow_rate: number;
    water_temp: number;
    map_rate: number;
    segments: MapSegment[];
    rows: Array<{
      rate: number;
      baseline: number;
      adjusted: number;
      delta: number;
    }>;
  }>;
};

export async function fetchPredictions(params: {
  boat_class: string;
  sex: string;
  weight_class: string;
  direction: string;
  date: string;
  map_rate: string;
}): Promise<PredictionResponse> {
  const query = new URLSearchParams(params).toString();
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  const response = await fetch(`${baseUrl}/predictions?${query}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Failed to fetch predictions");
  }
  return response.json();
}

export type SegmentRateRow = {
  rate: number;
  baseline: number;
  adjusted: number;
  delta: number;
};

export type SegmentRatesResponse = {
  segment_index: number;
  headwind_mps: number;
  crosswind_mps: number;
  tailwind_mps: number;
  rows: SegmentRateRow[];
  wind_speed: number;
  wind_dir: number;
  wind_compass: string | null | undefined;
};

export async function fetchSegmentRateRows(params: {
  boat_class: string;
  sex: string;
  weight_class: string;
  direction: string;
  date: string;
  hour_timestamp: string;
  segment_index: number;
}): Promise<SegmentRatesResponse> {
  const q = new URLSearchParams({
    boat_class: params.boat_class,
    sex: params.sex,
    weight_class: params.weight_class,
    direction: params.direction,
    date: params.date,
    hour_timestamp: params.hour_timestamp,
    segment_index: String(params.segment_index),
  });
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  const response = await fetch(`${baseUrl}/predictions/segment-rates?${q}`, { cache: "no-store" });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to fetch segment rates");
  }
  return response.json();
}
