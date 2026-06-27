<?php

use Illuminate\Support\Facades\Broadcast;

// Public channels (no authentication required for reading)
Broadcast::channel('orders', function () {
    return true;
});

Broadcast::channel('delivery-plan', function () {
    return true;
});

Broadcast::channel('digital-twin', function () {
    return true;
});

Broadcast::channel('App.Models.User.{id}', function ($user, $id) {
    return (int) $user->id === (int) $id;
});
