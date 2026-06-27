<?php

namespace App\Models;

use Database\Factories\RoomFactory;
use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Support\Carbon;

/**
 * @property int $id
 * @property string $name
 * @property string $code
 * @property string|null $building
 * @property string|null $floor
 * @property string|null $description
 * @property bool $is_active
 * @property Carbon|null $created_at
 * @property Carbon|null $updated_at
 */
#[Fillable(['name', 'code', 'x', 'y', 'orientation_w', 'aliases', 'building', 'floor', 'description', 'is_active'])]
class Room extends Model
{
    /** @use HasFactory<RoomFactory> */
    use HasFactory;

    /** @return HasMany<Order, $this> */
    public function departureOrders(): HasMany
    {
        return $this->hasMany(Order::class, 'departure_room_id');
    }

    /** @return HasMany<Order, $this> */
    public function arrivalOrders(): HasMany
    {
        return $this->hasMany(Order::class, 'arrival_room_id');
    }

    protected function casts(): array
    {
        return [
            'is_active' => 'boolean',
            'x' => 'float',
            'y' => 'float',
            'orientation_w' => 'float',
            'aliases' => 'array',
        ];
    }
}
