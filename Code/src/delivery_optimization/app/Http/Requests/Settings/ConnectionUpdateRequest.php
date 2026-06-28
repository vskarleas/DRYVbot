<?php

namespace App\Http\Requests\Settings;

use Illuminate\Foundation\Http\FormRequest;

class ConnectionUpdateRequest extends FormRequest
{
    /**
     * Determine if the user is authorized to make this request.
     */
    public function authorize(): bool
    {
        return $this->user() !== null;
    }

    /**
     * Get the validation rules that apply to the request.
     *
     * @return array<string, mixed>
     */
    public function rules(): array
    {
        return [
            'scheme' => ['required', 'string', 'in:ws,wss,tcp'],
            'host' => ['required', 'string', 'max:255', 'regex:/^[A-Za-z0-9._-]+$/'],
            'port' => ['required', 'integer', 'min:1', 'max:65535'],
        ];
    }

    /**
     * Get custom messages for validator errors.
     *
     * @return array<string, string>
     */
    public function messages(): array
    {
        return [
            'host.regex' => 'The host must be a valid IP address or hostname.',
        ];
    }

    /**
     * Compose the digital-twin socket address from the validated parts.
     */
    public function socketAddress(): string
    {
        return sprintf('%s://%s:%d', $this->string('scheme'), $this->string('host'), $this->integer('port'));
    }
}
