<?php

namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;

class UpdateOrderRequest extends FormRequest
{
    public function authorize(): bool
    {
        return $this->user()?->isPharmacist() ?? false;
    }

    /** @return array<string, mixed> */
    public function rules(): array
    {
        return [
            'departure_room_id' => ['sometimes', 'exists:rooms,id'],
            'arrival_room_id' => ['sometimes', 'exists:rooms,id'],
            'expected_delivery_at' => ['sometimes', 'date'],
            'content' => ['nullable', 'string', 'max:2000'],
            'notes' => ['nullable', 'string', 'max:1000'],
        ];
    }
}
