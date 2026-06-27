<?php

namespace App\Imports;

use App\Enums\OrderStatus;
use App\Models\Order;
use App\Models\Room;
use Maatwebsite\Excel\Concerns\ToModel;
use Maatwebsite\Excel\Concerns\WithHeadingRow;
use Maatwebsite\Excel\Concerns\WithValidation;

class OrderImport implements ToModel, WithHeadingRow, WithValidation
{
    public function __construct(private readonly int $userId) {}

    public function model(array $row): ?Order
    {
        $arrivalRoom = Room::where('code', $row['salle'] ?? '')->first();

        if ($arrivalRoom === null) {
            return null;
        }

        return new Order([
            'created_by' => $this->userId,
            'arrival_room_id' => $arrivalRoom->id,
            'expected_delivery_at' => $row['date'],
            'content' => $row['contenu'] ?? null,
            'notes' => $row['notes'] ?? null,
            'status' => OrderStatus::Pending,
            'is_critical' => ($row['critique'] ?? 0) == 1,
        ]);
    }

    /** @return array<string, mixed> */
    public function rules(): array
    {
        return [
            'salle' => ['required', 'string'],
            'date' => ['required'],
        ];
    }
}
