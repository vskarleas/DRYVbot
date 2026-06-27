<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Attributes\Fillable;

/**
 * @property int $id
 * @property string|null $salle_code_depart
 * @property string|null $salle_code_arrivee
 * @property \Illuminate\Support\Carbon|null $date_depart
 * @property \Illuminate\Support\Carbon|null $date_arrivee
 * @property int|null $order_id
 * @property int|null $duree
 * @property \Illuminate\Support\Carbon|null $created_at
 * @property \Illuminate\Support\Carbon|null $updated_at
 *
 * @property-read Order|null $order
 */
#[Fillable([
    'salle_code_depart', 'salle_code_arrivee', 'date_depart', 'date_arrivee', 'order_id', 'duree',
])]
class DtData extends Model
{
    protected function casts(): array
    {
        return [
            'date_depart' => 'datetime',
            'date_arrivee' => 'datetime',
        ];
    }

    /** @return BelongsTo<Order, $this> */
    public function order(): BelongsTo
    {
        return $this->belongsTo(Order::class, 'order_id');
    }
}
