<?php

use App\Http\Controllers\Api\DtWebhookController;
use Illuminate\Support\Facades\Route;

Route::prefix('v1')->group(function () {
    // Digital Twin webhook endpoints (protected by API token via config)
    Route::post('dt/update', [DtWebhookController::class, 'update'])->name('api.dt.update');
    Route::post('dt/bulk-update', [DtWebhookController::class, 'bulkUpdate'])->name('api.dt.bulk-update');
});
