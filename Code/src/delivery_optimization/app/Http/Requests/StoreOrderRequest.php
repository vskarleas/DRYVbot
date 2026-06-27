<?php

namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;

class StoreOrderRequest extends FormRequest
{
    public function authorize(): bool
    {
        return $this->user()?->isPharmacist() ?? false;
    }

    /** @return array<string, mixed> */
    public function rules(): array
    {
        return [
            'arrival_room_id' => ['required', 'exists:rooms,id'],
            'expected_delivery_at' => ['required', 'date'],
            'is_critical' => ['sometimes', 'boolean'],
            'medication_ids' => ['required', 'array', 'min:1'],
            'medication_ids.*' => ['integer', 'exists:medications,id'],
            'notes' => ['nullable', 'string', 'max:1000'],
        ];
    }
}
