<?php

namespace App\Models;

use App\Enums\OrderStatus;
use Database\Factories\OrderFactory;
use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Support\Carbon;
use Illuminate\Support\Str;

/**
 * @property int $id
 * @property string $reference
 * @property int $created_by
 * @property int|null $departure_room_id
 * @property int $arrival_room_id
 * @property Carbon $expected_delivery_at
 * @property OrderStatus $status
 * @property bool $is_critical
 * @property int|null $planned_sequence
 * @property string|null $content
 * @property string|null $notes
 * @property string|null $dt_salle_id_depart
 * @property string|null $dt_salle_id_arrivee
 * @property Carbon|null $dt_date_depart
 * @property Carbon|null $dt_date_arrivee
 * @property int|null $dt_duree_annee
 * @property int|null $dt_duree_mois
 * @property int|null $dt_duree_jour
 * @property int|null $dt_duree_heure
 * @property int|null $dt_duree_minute
 * @property int|null $cancelled_by
 * @property string|null $cancellation_reason
 * @property Carbon|null $cancelled_at
 * @property Carbon|null $delivered_at
 * @property Carbon|null $created_at
 * @property Carbon|null $updated_at
 */
#[Fillable([
    'reference', 'created_by', 'departure_room_id', 'arrival_room_id',
    'expected_delivery_at', 'status', 'is_critical', 'planned_sequence', 'content',
    'notes', 'dt_salle_id_depart', 'dt_salle_id_arrivee',
    'cancelled_by', 'cancellation_reason', 'cancelled_at', 'delivered_at',
])]
class Order extends Model
{
    /** @use HasFactory<OrderFactory> */
    use HasFactory;

    protected static function booted(): void
    {
        static::creating(function (Order $order): void {
            if (empty($order->reference)) {
                $order->reference = 'ORD-'.strtoupper(Str::random(8));
            }
        });
    }

    protected function casts(): array
    {
        return [
            'status' => OrderStatus::class,
            'is_critical' => 'boolean',
            'expected_delivery_at' => 'datetime',
            'cancelled_at' => 'datetime',
            'delivered_at' => 'datetime',
        ];
    }

    protected $with = [
        'departureRoom', 'arrivalRoom',
    ];

    /** @return BelongsTo<User, $this> */
    public function creator(): BelongsTo
    {
        return $this->belongsTo(User::class, 'created_by');
    }

    /** @return BelongsTo<Room, $this> */
    public function departureRoom(): BelongsTo
    {
        return $this->belongsTo(Room::class, 'departure_room_id');
    }

    /** @return BelongsTo<Room, $this> */
    public function arrivalRoom(): BelongsTo
    {
        return $this->belongsTo(Room::class, 'arrival_room_id');
    }

    /** @return BelongsTo<User, $this> */
    public function cancelledBy(): BelongsTo
    {
        return $this->belongsTo(User::class, 'cancelled_by');
    }
}
