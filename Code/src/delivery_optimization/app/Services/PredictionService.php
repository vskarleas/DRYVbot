<?php

namespace App\Services;

use Illuminate\Support\Facades\Http;

class PredictionService
{
    private string $baseUrl;

    public function __construct()
    {
        $this->baseUrl = config('services.prediction.url');
    }

    /**
     * Get the predicted delivery time (in minutes) between two rooms.
     * Falls back to a default heuristic if the prediction service is unavailable.
     */
    public function predict(string $roomDepartureCode, string $roomArrivalCode, string $departureTime): float
    {
        try {
            $response = Http::timeout(3)->post("{$this->baseUrl}/predict", [
                'room_departure_id' => $roomDepartureCode,
                'room_arrival_id' => $roomArrivalCode,
                'departure_time' => $departureTime,
            ]);

            \Log::info('Prediction service response', [
                'status' => $response->status(),
                'body' => $response->body(),
            ]);

            if ($response->successful()) {
                $predictedDurationSeconds = $response->json('predicted_duration_s');

                if (is_numeric($predictedDurationSeconds) && (float) $predictedDurationSeconds > 0) {
                    return max(1, round((float) $predictedDurationSeconds / 60, 2)); // Convert to minutes and round to 2 decimal places
                }
            }
        } catch (\Throwable $e) {
            \Log::warning('Prediction service unavailable, using fallback', ['error' => $e->getMessage()]);
        }

        return $this->fallbackPrediction($roomDepartureCode, $roomArrivalCode);
    }

    /**
     * Simple heuristic fallback: 5 minutes base + up to 10 minutes based on room IDs.
     */
    private function fallbackPrediction(string $roomDepartureCode, string $roomArrivalCode): float
    {
        return 1.5;
    }
}
