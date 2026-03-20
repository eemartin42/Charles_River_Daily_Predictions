export type PredictionResponse = {
  meta: {
    date: string;
    boat_class: string;
    sex: string;
    weight_class: string;
    direction: string;
    charles_speed_index: number;
  };
  hourly: Array<{
    timestamp: string;
    wind_speed: number;
    flow_rate: number;
    water_temp: number;
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
}): Promise<PredictionResponse> {
  const query = new URLSearchParams(params).toString();
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  const response = await fetch(`${baseUrl}/predictions?${query}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Failed to fetch predictions");
  }
  return response.json();
}
