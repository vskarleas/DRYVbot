<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Support\Carbon;

/**
 * @property int $id
 * @property int|null $current_room_id
 * @property 'queued'|'active'|'completed' $status
 * @property bool $is_critical
 * @property array<int> $sequence
 * @property array<mixed>|null $estimated_times
 * @property Carbon|null $created_at
 * @property Carbon|null $updated_at
 */
#[Fillable(['current_room_id', 'status', 'is_critical', 'sequence', 'estimated_times'])]
class DeliveryPlan extends Model
{
    protected function casts(): array
    {
        return [
            'is_critical' => 'boolean',
            'sequence' => 'array',
            'estimated_times' => 'array',
        ];
    }

    /** @return BelongsTo<Room, $this> */
    public function currentRoom(): BelongsTo
    {
        return $this->belongsTo(Room::class, 'current_room_id');
    }
}
