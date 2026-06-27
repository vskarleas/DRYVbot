<?php

use App\Models\AppSetting;
use App\Models\User;
use App\Services\DtConnectionSettings;

test('connection settings page is displayed', function () {
    $user = User::factory()->create();

    $this->actingAs($user)
        ->get(route('connection.edit'))
        ->assertOk();
});

test('connection settings require authentication', function () {
    $this->get(route('connection.edit'))->assertRedirect();
});

test('connection address can be updated and is persisted', function () {
    $user = User::factory()->create();

    $response = $this->actingAs($user)
        ->put(route('connection.update'), [
            'scheme' => 'ws',
            'host' => '192.168.1.42',
            'port' => 9090,
        ]);

    $response
        ->assertSessionHasNoErrors()
        ->assertRedirect(route('connection.edit'));

    expect(AppSetting::get(DtConnectionSettings::SETTING_KEY))
        ->toBe('ws://192.168.1.42:9090');

    expect(app(DtConnectionSettings::class)->address())
        ->toBe('ws://192.168.1.42:9090');
});

test('connection update validates its input', function () {
    $user = User::factory()->create();

    $this->actingAs($user)
        ->from(route('connection.edit'))
        ->put(route('connection.update'), [
            'scheme' => 'http',
            'host' => '',
            'port' => 70000,
        ])
        ->assertSessionHasErrors(['scheme', 'host', 'port']);
});

test('address falls back to config when no value has been saved', function () {
    config()->set('dt.socket.address', 'tcp://127.0.0.1:9000');

    $settings = app(DtConnectionSettings::class);

    expect($settings->address())->toBe('tcp://127.0.0.1:9000');
    expect($settings->current())->toMatchArray([
        'scheme' => 'tcp',
        'host' => '127.0.0.1',
        'port' => 9000,
    ]);
});

test('saved address takes precedence over config', function () {
    config()->set('dt.socket.address', 'tcp://127.0.0.1:9000');

    app(DtConnectionSettings::class)->update('ws', '10.0.0.5', 9090);

    expect(app(DtConnectionSettings::class)->address())->toBe('ws://10.0.0.5:9090');
});
