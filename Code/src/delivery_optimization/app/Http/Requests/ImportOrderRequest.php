<?php

namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;

class ImportOrderRequest extends FormRequest
{
    public function authorize(): bool
    {
        return $this->user()?->isPharmacist() ?? false;
    }

    /** @return array<string, mixed> */
    public function rules(): array
    {
        return [
            'file' => ['required', 'file', 'mimes:xlsx,xls,csv', 'max:10240'],
        ];
    }
}
