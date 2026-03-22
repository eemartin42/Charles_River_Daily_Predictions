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
