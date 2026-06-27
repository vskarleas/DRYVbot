<?php

namespace App\Http\Controllers\Settings;

use App\Http\Controllers\Controller;
use App\Http\Requests\Settings\DtConnectionUpdateRequest;
use App\Services\DtConnectionSettings;
use Illuminate\Http\RedirectResponse;
use Illuminate\Support\Facades\Cache;
use Inertia\Inertia;
use Inertia\Response;

class DtConnectionController extends Controller
{
    public function __construct(private readonly DtConnectionSettings $settings) {}

    /**
     * Show the digital twin connection settings page.
     */
    public function edit(): Response
    {
        $lastStatus = Cache::get('dt:last_status_payload');

        return Inertia::render('settings/connection', [
            'connection' => $this->settings->current(),
            'lastStatus' => is_array($lastStatus) ? $lastStatus : null,
        ]);
    }

    /**
     * Update the ROS machine address the socket workers connect to.
     */
    public function update(DtConnectionUpdateRequest $request): RedirectResponse
    {
        $validated = $request->validated();

        $this->settings->update(
            (string) $validated['scheme'],
            (string) $validated['host'],
            (int) $validated['port'],
        );

        Inertia::flash('toast', ['type' => 'success', 'message' => __('Digital twin connection updated.')]);

        return to_route('connection.edit');
    }
}
