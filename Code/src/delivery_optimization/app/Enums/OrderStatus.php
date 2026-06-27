<?php

namespace App\Enums;

enum OrderStatus: string
{
    case Pending = 'pending';
    case InTransit = 'in_transit';
    case Delivered = 'delivered';
    case Cancelled = 'cancelled';

    public function label(): string
    {
        return match ($this) {
            self::Pending => 'En attente',
            self::InTransit => 'En cours',
            self::Delivered => 'Livré',
            self::Cancelled => 'Annulé',
        };
    }

    public function color(): string
    {
        return match ($this) {
            self::Pending => 'yellow',
            self::InTransit => 'blue',
            self::Delivered => 'green',
            self::Cancelled => 'red',
        };
    }
}
