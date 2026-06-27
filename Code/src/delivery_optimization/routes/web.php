<?php

use App\Http\Controllers\Api\DtWebhookController;
use App\Http\Controllers\DashboardController;
use App\Http\Controllers\DeliveryPlanController;
use App\Http\Controllers\OrderController;
use App\Http\Controllers\RoomController;
use Illuminate\Support\Facades\Route;

Route::post('/api/dt/webhook', [DtWebhookController::class, 'receive'])
    ->name('dt.webhook');

Route::get('/', function () {
    return redirect()->route('dashboard');
})->name('home');

Route::middleware(['auth', 'verified'])->group(function () {
    Route::get('/dashboard', [DashboardController::class, 'index'])->name('dashboard');

    Route::get('/orders', [OrderController::class, 'index'])->name('orders.index');
    Route::get('/orders/create', [OrderController::class, 'create'])->name('orders.create');
    Route::get('/orders/{order}', [OrderController::class, 'show'])->name('orders.show');

    Route::middleware('role:pharmacist')->group(function () {
        Route::post('/orders', [OrderController::class, 'store'])->name('orders.store');
        Route::post('/orders/initialize-planning', [OrderController::class, 'initializePlanning'])->name('orders.initialize-planning');
        Route::post('/orders/import/excel', [OrderController::class, 'importExcel'])->name('orders.import.excel');
        Route::post('/orders/import/ocr', [OrderController::class, 'importOcr'])->name('orders.import.ocr');
    });

    Route::middleware('role:manager')->group(function () {
        Route::post('/orders/{order}/deliver', [OrderController::class, 'deliver'])->name('orders.deliver');
        Route::post('/orders/{order}/cancel', [OrderController::class, 'cancel'])->name('orders.cancel');
        Route::post('/orders/{order}/dispatch-remote-socket', [OrderController::class, 'dispatchRemoteSocket'])->name('orders.dispatch-remote-socket');
        Route::get('/delivery-plan', [DeliveryPlanController::class, 'index'])->name('delivery-plan.index');
        Route::post('/delivery-plan/replan', [DeliveryPlanController::class, 'replan'])->name('delivery-plan.replan');
        Route::apiResource('rooms', RoomController::class)->except('show');
    });
});

require __DIR__.'/settings.php';
