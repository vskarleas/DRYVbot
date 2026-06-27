<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Support\Facades\Cache;

/**
 * Simple persisted key-value store for application-level settings that need to
 * be editable at runtime (e.g. from the settings UI) rather than only via .env.
 *
 * @property int $id
 * @property string $key
 * @property string|null $value
 * @property \Illuminate\Support\Carbon|null $created_at
 * @property \Illuminate\Support\Carbon|null $updated_at
 */
#[Fillable(['key', 'value'])]
class AppSetting extends Model
{
    private const CACHE_PREFIX = 'app_setting:';

    /**
     * Read a setting value, falling back to $default when it has never been set.
     * The value is cached so hot paths (e.g. the long-running socket workers)
     * do not hit the database on every read.
     */
    public static function get(string $key, ?string $default = null): ?string
    {
        $value = Cache::rememberForever(
            self::CACHE_PREFIX.$key,
            static fn (): ?string => self::query()->where('key', $key)->value('value'),
        );

        return $value ?? $default;
    }

    /**
     * Persist a setting value and refresh its cached copy.
     */
    public static function put(string $key, ?string $value): void
    {
        self::query()->updateOrCreate(['key' => $key], ['value' => $value]);

        Cache::forever(self::CACHE_PREFIX.$key, $value);
    }
}
